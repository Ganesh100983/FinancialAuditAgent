import os
import json
import io
from datetime import datetime

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dotenv import load_dotenv

from src.utils.data_processor import parse_ledger, parse_gst_data, parse_employee_data, get_ledger_stats
from src.utils.pdf_generator import generate_form16_pdf, generate_gst_report_pdf, generate_ledger_report_pdf
from src.models.financial_models import Form16Data, Form16PartA, Form16PartB, GSTR1Summary

load_dotenv()

# ─── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Financial Audit AI",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Main header */
    .main-title {
        font-size: 2rem; font-weight: 800;
        background: linear-gradient(135deg, #1E3A5F, #2E86AB);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .main-subtitle { font-size: 0.95rem; color: #666; margin-bottom: 1.5rem; }

    /* Metric cards */
    .metric-card {
        background: linear-gradient(135deg, #1E3A5F, #2E86AB);
        color: white; padding: 1.2rem; border-radius: 12px;
        text-align: center; box-shadow: 0 4px 15px rgba(30,58,95,0.3);
    }
    .metric-card h3 { font-size: 1.8rem; margin: 0; font-weight: 800; }
    .metric-card p  { font-size: 0.85rem; margin: 0.2rem 0 0 0; opacity: 0.85; }

    /* Status badges */
    .badge-success { background:#d4edda; color:#155724; padding:3px 10px;
                     border-radius:12px; font-size:0.8rem; font-weight:600; }
    .badge-warning { background:#fff3cd; color:#856404; padding:3px 10px;
                     border-radius:12px; font-size:0.8rem; font-weight:600; }
    .badge-danger  { background:#f8d7da; color:#721c24; padding:3px 10px;
                     border-radius:12px; font-size:0.8rem; font-weight:600; }

    /* Section headers */
    .section-header {
        background: linear-gradient(90deg, #1E3A5F, #2E86AB);
        color: white; padding: 0.6rem 1rem; border-radius: 8px;
        font-weight: 700; font-size: 1rem; margin: 1rem 0 0.5rem 0;
    }

    /* Chat bubbles */
    .chat-user { background:#E8F4FD; padding:0.8rem 1rem; border-radius:12px 12px 2px 12px;
                 margin: 0.5rem 0; border-left: 4px solid #2E86AB; }
    .chat-ai   { background:#F0F7F0; padding:0.8rem 1rem; border-radius:12px 12px 12px 2px;
                 margin: 0.5rem 0; border-left: 4px solid #27AE60; }

    /* Upload area */
    .upload-hint { color: #888; font-size: 0.85rem; font-style: italic; }

    /* Anomaly severity */
    .sev-high   { color: #dc3545; font-weight: 700; }
    .sev-medium { color: #fd7e14; font-weight: 600; }
    .sev-low    { color: #ffc107; font-weight: 600; }

    /* Footer */
    .footer { text-align:center; color:#aaa; font-size:0.8rem; margin-top:2rem; padding-top:1rem;
              border-top: 1px solid #eee; }

    /* Hide Streamlit default elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display:none;}
</style>
""", unsafe_allow_html=True)


# ─── Session State ─────────────────────────────────────────────────────────────
def init_state():
    defaults = {
        "api_key": os.getenv("OPENAI_API_KEY", ""),
        "data_store": {
            "ledger_df": None,
            "gst_df": None,
            "employee_df": None,
            "company_name": "ABC Enterprises Pvt Ltd",
            "company_gstin": "27AABCE1234A1Z5",
            "company_tan": "MUMA12345A",
            "company_pan": "AABCE1234A",
            "company_address": "Mumbai, Maharashtra - 400001",
            "financial_year": "2024-25",
            "ledger_summary": None,
            "anomalies": None,
            "trial_balance": None,
            "pl_statement": None,
            "gst_summary_data": None,
            "gstr1_data": None,
            "gstr3b_data": None,
            "form16_data": {},
        },
        "chat_history": [],
        "current_agent": "Ledger",
        "page": "Home",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ─── Sidebar ──────────────────────────────────────────────────────────────────
def render_sidebar():
    with st.sidebar:
        st.markdown("""
        <div style='text-align:center; padding: 1rem 0;'>
            <div style='font-size:3rem;'>💼</div>
            <div style='font-size:1.2rem; font-weight:800; color:#1E3A5F;'>Financial Audit AI</div>
            <div style='font-size:0.8rem; color:#888;'>Powered by OpenAI GPT-4o & LangChain</div>
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        pages = {
            "🏠  Home": "Home",
            "📊  Ledger Screener": "Ledger",
            "📋  Form 16 Generator": "Form16",
            "🧾  GST Filing": "GST",
            "💬  AI Assistant": "Chat",
        }
        for label, page_id in pages.items():
            active = st.session_state.page == page_id
            if st.button(
                label,
                key=f"nav_{page_id}",
                use_container_width=True,
                type="primary" if active else "secondary",
            ):
                st.session_state.page = page_id
                st.rerun()

        st.divider()

        with st.expander("⚙️ Settings & Company Info", expanded=False):
            st.session_state.api_key = st.text_input(
                "OpenAI API Key",
                value=st.session_state.api_key,
                type="password",
                placeholder="sk-...",
                help="Get your key from platform.openai.com/api-keys",
            )
            if st.session_state.api_key:
                st.success("API key configured", icon="✅")

            st.divider()
            st.markdown("**Company Details**")
            ds = st.session_state.data_store
            ds["company_name"] = st.text_input("Company Name", value=ds["company_name"])
            ds["company_gstin"] = st.text_input("GSTIN", value=ds["company_gstin"])
            ds["company_tan"] = st.text_input("TAN", value=ds["company_tan"])
            ds["company_pan"] = st.text_input("PAN", value=ds["company_pan"])
            ds["financial_year"] = st.selectbox(
                "Financial Year",
                ["2024-25", "2023-24", "2022-23"],
                index=["2024-25", "2023-24", "2022-23"].index(ds["financial_year"]),
            )

        st.divider()
        loaded = []
        if st.session_state.data_store["ledger_df"] is not None:
            loaded.append("📊 Ledger")
        if st.session_state.data_store["gst_df"] is not None:
            loaded.append("🧾 GST Data")
        if st.session_state.data_store["employee_df"] is not None:
            loaded.append("👤 Employees")

        if loaded:
            st.markdown("**Loaded Data:**")
            for item in loaded:
                st.markdown(f"<span class='badge-success'>{item}</span>", unsafe_allow_html=True)
        else:
            st.markdown("<span class='badge-warning'>No data loaded</span>", unsafe_allow_html=True)

        st.markdown(
            "<div class='footer'>Financial Audit AI v1.0<br>© 2024 | Built with OpenAI & LangChain</div>",
            unsafe_allow_html=True,
        )


# ─── Home Page ────────────────────────────────────────────────────────────────
def page_home():
    st.markdown("<div class='main-title'>Financial Audit AI</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='main-subtitle'>Intelligent Accounting Auditor — Ledger Screening, Form 16 & GST Filing</div>",
        unsafe_allow_html=True,
    )

    col1, col2, col3, col4 = st.columns(4)
    ds = st.session_state.data_store

    with col1:
        n = len(ds["ledger_df"]) if ds["ledger_df"] is not None else 0
        st.markdown(f"""
        <div class='metric-card'>
            <h3>{n:,}</h3><p>Ledger Entries</p>
        </div>""", unsafe_allow_html=True)
    with col2:
        n = len(ds["employee_df"]) if ds["employee_df"] is not None else 0
        st.markdown(f"""
        <div class='metric-card'>
            <h3>{n}</h3><p>Employees</p>
        </div>""", unsafe_allow_html=True)
    with col3:
        n = len(ds["gst_df"]) if ds["gst_df"] is not None else 0
        st.markdown(f"""
        <div class='metric-card'>
            <h3>{n:,}</h3><p>GST Invoices</p>
        </div>""", unsafe_allow_html=True)
    with col4:
        n = len(ds["anomalies"]) if ds["anomalies"] is not None else 0
        st.markdown(f"""
        <div class='metric-card'>
            <h3>{n}</h3><p>Anomalies Found</p>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    col_a, col_b = st.columns([1, 1])
    with col_a:
        st.markdown("### 🚀 Quick Start")
        st.markdown("""
        **Step 1:** Configure your OpenAI API key in Settings (sidebar)

        **Step 2:** Upload your data files:
        - 📊 **Ledger** → Accounting ledger (CSV/Excel)
        - 👤 **Employees** → Salary data for Form 16
        - 🧾 **GST Invoices** → Invoice data for GSTR filing

        **Step 3:** Navigate to the relevant module:
        - **Ledger Screener** — AI-powered audit & anomaly detection
        - **Form 16 Generator** — Auto-compute TDS & generate certificates
        - **GST Filing** — Prepare GSTR-1 & GSTR-3B returns
        - **AI Assistant** — Ask any financial/tax question
        """)

    with col_b:
        st.markdown("### 📁 Quick File Upload")
        upload_tab1, upload_tab2, upload_tab3 = st.tabs(["Ledger", "Employee", "GST"])

        with upload_tab1:
            f = st.file_uploader("Upload Accounting Ledger", type=["csv", "xlsx", "xls"],
                                  key="home_ledger", label_visibility="collapsed")
            if f:
                df, msg = parse_ledger(f.read(), f.name)
                if df is not None:
                    st.session_state.data_store["ledger_df"] = df
                    st.success(msg)
                else:
                    st.error(msg)

        with upload_tab2:
            f = st.file_uploader("Upload Employee Data", type=["csv", "xlsx", "xls"],
                                  key="home_emp", label_visibility="collapsed")
            if f:
                df, msg = parse_employee_data(f.read(), f.name)
                if df is not None:
                    st.session_state.data_store["employee_df"] = df
                    st.success(msg)
                else:
                    st.error(msg)

        with upload_tab3:
            f = st.file_uploader("Upload GST Invoices", type=["csv", "xlsx", "xls"],
                                  key="home_gst", label_visibility="collapsed")
            if f:
                df, msg = parse_gst_data(f.read(), f.name)
                if df is not None:
                    st.session_state.data_store["gst_df"] = df
                    st.success(msg)
                else:
                    st.error(msg)

    st.divider()

    if ds["ledger_df"] is not None:
        st.markdown("### 📈 Ledger Overview")
        df = ds["ledger_df"]
        stats = get_ledger_stats(df)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Debit", f"₹{stats['total_debit']:,.0f}")
        c2.metric("Total Credit", f"₹{stats['total_credit']:,.0f}")
        c3.metric("Net Balance", f"₹{stats['net_balance']:,.0f}")
        c4.metric("Date Range", stats["date_range"])

        col_chart1, col_chart2 = st.columns(2)
        with col_chart1:
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=["Total Debit", "Total Credit"],
                y=[stats["total_debit"], stats["total_credit"]],
                marker_color=["#E74C3C", "#27AE60"],
                text=[f"₹{stats['total_debit']:,.0f}", f"₹{stats['total_credit']:,.0f}"],
                textposition="outside",
            ))
            fig.update_layout(title="Debit vs Credit Summary", height=300,
                              margin=dict(t=40, b=20, l=20, r=20))
            st.plotly_chart(fig, use_container_width=True)

        with col_chart2:
            if "debit" in df.columns and "credit" in df.columns:
                df_plot = df.copy()
                df_plot["month"] = pd.to_datetime(df_plot["date"], dayfirst=True, errors="coerce").dt.to_period("M").astype(str)
                monthly = df_plot.groupby("month").agg(debit=("debit","sum"), credit=("credit","sum")).reset_index()
                fig2 = go.Figure()
                fig2.add_trace(go.Scatter(x=monthly["month"], y=monthly["credit"], name="Credit", fill="tozeroy",
                                          line=dict(color="#27AE60")))
                fig2.add_trace(go.Scatter(x=monthly["month"], y=monthly["debit"], name="Debit", fill="tozeroy",
                                          line=dict(color="#E74C3C", dash="dash")))
                fig2.update_layout(title="Monthly Transaction Trend", height=300,
                                   margin=dict(t=40, b=20, l=20, r=20))
                st.plotly_chart(fig2, use_container_width=True)


# ─── Ledger Screener ──────────────────────────────────────────────────────────
def page_ledger():
    st.markdown("## 📊 Ledger Screener")
    st.markdown("Upload your accounting ledger to perform AI-powered audit, anomaly detection, and financial statement generation.")

    col_upload, col_info = st.columns([1, 1])

    with col_upload:
        st.markdown("<div class='section-header'>📁 Upload Accounting Ledger</div>", unsafe_allow_html=True)
        uploaded = st.file_uploader(
            "Supports CSV and Excel files",
            type=["csv", "xlsx", "xls"],
            key="ledger_upload",
            help="Columns needed: Date, Narration/Description, Debit, Credit. Optional: Voucher No, Account, Balance",
        )
        if uploaded:
            df, msg = parse_ledger(uploaded.read(), uploaded.name)
            if df is not None:
                st.session_state.data_store["ledger_df"] = df
                st.success(f"✅ {msg}")
            else:
                st.error(f"❌ {msg}")

        with st.expander("📋 Expected Format"):
            sample = pd.DataFrame({
                "Date": ["01-04-2024", "02-04-2024"],
                "Voucher_No": ["JV001", "JV002"],
                "Narration": ["Sales to ABC Ltd", "Rent Paid"],
                "Account": ["Sales Account", "Rent Expense"],
                "Debit": [0, 50000],
                "Credit": [150000, 0],
                "Balance": [150000, 100000],
            })
            st.dataframe(sample, use_container_width=True)
            csv_data = sample.to_csv(index=False).encode()
            st.download_button("⬇️ Download Sample Template", csv_data,
                               "sample_ledger.csv", "text/csv")

    with col_info:
        df = st.session_state.data_store.get("ledger_df")
        if df is not None:
            st.markdown("<div class='section-header'>📈 Ledger Statistics</div>", unsafe_allow_html=True)
            stats = get_ledger_stats(df)
            st.metric("Total Entries", f"{stats['total_entries']:,}")
            st.metric("Total Debit", f"₹{stats['total_debit']:,.2f}")
            st.metric("Total Credit", f"₹{stats['total_credit']:,.2f}")
            st.metric("Date Range", stats["date_range"])
            st.markdown(f"**Unique Accounts:** {stats['unique_accounts']}")

    if st.session_state.data_store.get("ledger_df") is None:
        st.info("Please upload a ledger file to proceed with analysis.")
        return

    df = st.session_state.data_store["ledger_df"]

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📋 Data Preview", "🤖 AI Audit", "⚠️ Anomalies", "📊 Trial Balance", "📉 P&L Statement"
    ])

    with tab1:
        st.dataframe(df.head(100), use_container_width=True)
        st.caption(f"Showing first 100 of {len(df)} entries")

    with tab2:
        st.markdown("### 🤖 AI-Powered Ledger Audit")
        st.markdown("The AI auditor will analyze your ledger, detect anomalies, and provide professional audit observations.")

        if not st.session_state.api_key:
            st.warning("Please configure your OpenAI API key in the sidebar settings.")
            return

        col_btn, col_q = st.columns([1, 2])
        with col_btn:
            run_full = st.button("🔍 Run Full Audit", type="primary", use_container_width=True)
        with col_q:
            custom_query = st.text_input("Or ask a specific question:", placeholder="e.g., Are the books balanced?")
            run_custom = st.button("Ask", type="secondary")

        if run_full or (run_custom and custom_query):
            from src.agents.ledger_agent import create_ledger_agent, run_full_ledger_audit
            with st.spinner("AI Auditor is analyzing your ledger... This may take a moment."):
                try:
                    if run_full:
                        result = run_full_ledger_audit(
                            st.session_state.api_key,
                            st.session_state.data_store,
                        )
                    else:
                        agent = create_ledger_agent(st.session_state.api_key, st.session_state.data_store)
                        result = agent.invoke({"messages": [("human", custom_query)]})["messages"][-1].content
                    st.markdown("### 📋 Audit Report")
                    st.markdown(result)

                    anomalies = st.session_state.data_store.get("anomalies", [])
                    summary = st.session_state.data_store.get("ledger_summary", {})
                    if summary:
                        pdf_bytes = generate_ledger_report_pdf(summary, anomalies or [])
                        st.download_button(
                            "⬇️ Download Audit Report (PDF)",
                            pdf_bytes,
                            f"audit_report_{datetime.now().strftime('%Y%m%d')}.pdf",
                            "application/pdf",
                            type="primary",
                        )
                except Exception as e:
                    st.error(f"Agent error: {str(e)}")

    with tab3:
        st.markdown("### ⚠️ Anomaly Detection")
        if not st.session_state.api_key:
            st.warning("API key required.")
            return

        if st.button("🔍 Detect Anomalies", type="primary"):
            from src.tools.ledger_tools import create_ledger_tools
            with st.spinner("Scanning for anomalies..."):
                tools = create_ledger_tools(st.session_state.data_store)
                detect_tool = next(t for t in tools if t.name == "detect_ledger_anomalies")
                result = json.loads(detect_tool.run("all"))
                anomalies = result.get("anomalies", [])

        anomalies = st.session_state.data_store.get("anomalies", [])
        if anomalies:
            high = [a for a in anomalies if a.get("severity") == "High"]
            med  = [a for a in anomalies if a.get("severity") == "Medium"]
            low  = [a for a in anomalies if a.get("severity") == "Low"]

            c1, c2, c3 = st.columns(3)
            c1.metric("🔴 High Severity", len(high))
            c2.metric("🟠 Medium Severity", len(med))
            c3.metric("🟡 Low Severity", len(low))

            anomaly_df = pd.DataFrame(anomalies)
            severity_colors = {"High": "🔴", "Medium": "🟠", "Low": "🟡"}
            anomaly_df["Severity"] = anomaly_df["severity"].map(lambda x: f"{severity_colors.get(x, '')} {x}")
            anomaly_df = anomaly_df.rename(columns={
                "row_index": "Row", "voucher_no": "Voucher", "anomaly_type": "Type",
                "description": "Description", "amount": "Amount (₹)", "Severity": "Severity"
            })
            if "Amount (₹)" in anomaly_df.columns:
                anomaly_df["Amount (₹)"] = anomaly_df["Amount (₹)"].apply(lambda x: f"₹{float(x):,.2f}")
            st.dataframe(anomaly_df[["Row", "Voucher", "Type", "Description", "Amount (₹)", "Severity"]],
                         use_container_width=True)
        else:
            st.info("Click 'Detect Anomalies' to scan your ledger.")

    with tab4:
        st.markdown("### 📊 Trial Balance")
        if st.button("Generate Trial Balance", type="primary"):
            from src.tools.ledger_tools import create_ledger_tools
            with st.spinner("Generating trial balance..."):
                tools = create_ledger_tools(st.session_state.data_store)
                tb_tool = next(t for t in tools if t.name == "generate_trial_balance")
                result = json.loads(tb_tool.run("all"))
                st.session_state.data_store["trial_balance"] = result

        tb = st.session_state.data_store.get("trial_balance")
        if tb:
            is_balanced = tb.get("is_balanced", False)
            diff = tb.get("difference", 0)
            if is_balanced:
                st.success(f"✅ Trial Balance is BALANCED — Total Dr = Total Cr")
            else:
                st.error(f"❌ Books NOT balanced — Difference: ₹{diff:,.2f}")

            st.metric("Total Debit", f"₹{tb.get('total_debit', 0):,.2f}")
            st.metric("Total Credit", f"₹{tb.get('total_credit', 0):,.2f}")

            if tb.get("trial_balance"):
                tb_df = pd.DataFrame(tb["trial_balance"])
                for col in ["total_debit", "total_credit", "closing_balance"]:
                    if col in tb_df.columns:
                        tb_df[col] = tb_df[col].apply(lambda x: f"₹{float(x):,.2f}")
                st.dataframe(tb_df, use_container_width=True)
        else:
            st.info("Click 'Generate Trial Balance' to view the trial balance.")

    with tab5:
        st.markdown("### 📉 Profit & Loss Statement")
        if st.button("Generate P&L", type="primary"):
            from src.tools.ledger_tools import create_ledger_tools
            with st.spinner("Computing P&L..."):
                tools = create_ledger_tools(st.session_state.data_store)
                pl_tool = next(t for t in tools if t.name == "generate_pl_statement")
                result = json.loads(pl_tool.run("full"))
                st.session_state.data_store["pl_statement"] = result

        pl = st.session_state.data_store.get("pl_statement")
        if pl:
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Income", f"₹{pl.get('total_income', 0):,.2f}")
            c2.metric("Total Expenses", f"₹{pl.get('total_expenses', 0):,.2f}")
            net = pl.get("net_profit", 0)
            c3.metric(
                "Net Profit/(Loss)",
                f"₹{net:,.2f}",
                delta=f"{pl.get('profit_margin', 0):.1f}% margin",
            )

            col_i, col_e = st.columns(2)
            with col_i:
                st.markdown("**Income Accounts**")
                inc = pl.get("income", {})
                if inc:
                    inc_df = pd.DataFrame(list(inc.items()), columns=["Account", "Amount (₹)"])
                    inc_df["Amount (₹)"] = inc_df["Amount (₹)"].apply(lambda x: f"₹{x:,.2f}")
                    st.dataframe(inc_df, use_container_width=True, hide_index=True)
                else:
                    st.info("No income accounts classified.")

            with col_e:
                st.markdown("**Expense Accounts**")
                exp = pl.get("expenses", {})
                if exp:
                    exp_df = pd.DataFrame(list(exp.items()), columns=["Account", "Amount (₹)"])
                    exp_df["Amount (₹)"] = exp_df["Amount (₹)"].apply(lambda x: f"₹{x:,.2f}")
                    st.dataframe(exp_df, use_container_width=True, hide_index=True)
                else:
                    st.info("No expense accounts classified.")

            if inc or exp:
                fig = go.Figure(data=[
                    go.Bar(name="Income", x=list(inc.keys())[:10], y=list(inc.values())[:10],
                           marker_color="#27AE60"),
                    go.Bar(name="Expenses", x=list(exp.keys())[:10], y=list(exp.values())[:10],
                           marker_color="#E74C3C"),
                ])
                fig.update_layout(title="Income vs Expenses by Account", barmode="group", height=350)
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Click 'Generate P&L' to view the statement.")


# ─── Form 16 Generator ────────────────────────────────────────────────────────
def page_form16():
    st.markdown("## 📋 Form 16 Generator")
    st.markdown("Upload employee salary data to compute TDS and generate Form 16 certificates.")

    col_upload, col_preview = st.columns([1, 1])

    with col_upload:
        st.markdown("<div class='section-header'>📁 Upload Employee Salary Data</div>", unsafe_allow_html=True)
        uploaded = st.file_uploader(
            "Employee data (CSV/Excel)",
            type=["csv", "xlsx", "xls"],
            key="emp_upload",
        )
        if uploaded:
            df, msg = parse_employee_data(uploaded.read(), uploaded.name)
            if df is not None:
                st.session_state.data_store["employee_df"] = df
                st.success(f"✅ {msg}")
            else:
                st.error(f"❌ {msg}")

        with st.expander("📋 Expected Format"):
            sample = pd.DataFrame({
                "Employee_ID": ["E001", "E002"],
                "Name": ["Rajesh Kumar", "Priya Sharma"],
                "PAN": ["ABCPK1234A", "XYZPS5678B"],
                "Designation": ["Manager", "Engineer"],
                "Basic_Salary": [720000, 480000],
                "HRA": [288000, 192000],
                "Special_Allowance": [144000, 96000],
                "Professional_Tax": [2400, 2400],
                "TDS_Deducted": [95000, 32000],
                "Section_80C": [150000, 100000],
                "Section_80D": [25000, 15000],
            })
            st.dataframe(sample, use_container_width=True)
            st.download_button("⬇️ Download Template", sample.to_csv(index=False).encode(),
                               "sample_employees.csv", "text/csv")

    with col_preview:
        df = st.session_state.data_store.get("employee_df")
        if df is not None:
            st.markdown("<div class='section-header'>👤 Employee Records</div>", unsafe_allow_html=True)
            st.metric("Total Employees", len(df))
            display_cols = [c for c in ["employee_id", "name", "designation", "basic_salary", "tds_deducted"] if c in df.columns]
            st.dataframe(df[display_cols].head(10), use_container_width=True, hide_index=True)

    if st.session_state.data_store.get("employee_df") is None:
        st.info("Please upload employee salary data to generate Form 16.")
        return

    if not st.session_state.api_key:
        st.warning("Please configure your OpenAI API key in the sidebar settings.")
        return

    df = st.session_state.data_store["employee_df"]

    st.divider()
    st.markdown("### 🔧 Form 16 Configuration")

    col1, col2, col3 = st.columns(3)
    with col1:
        regime = st.selectbox("Tax Regime", ["Old", "New", "Compare Both"], index=0)
    with col2:
        rent_paid = st.number_input("Annual Rent Paid (₹)", min_value=0.0, value=0.0, step=10000.0,
                                     help="For HRA exemption calculation")
    with col3:
        is_metro = st.checkbox("Metro City?", value=True, help="Metro: Mumbai, Delhi, Kolkata, Chennai")

    col_all, col_single = st.columns([1, 2])
    with col_all:
        generate_all = st.button("🚀 Generate All Form 16s", type="primary", use_container_width=True)
    with col_single:
        emp_options = df["name"].tolist() if "name" in df.columns else df["employee_id"].tolist()
        selected_emp = st.selectbox("Or select specific employee:", ["-- Select --"] + emp_options)
        generate_single = st.button("Generate Selected", type="secondary")

    if generate_all or (generate_single and selected_emp != "-- Select --"):
        from src.agents.form16_agent import create_form16_agent, generate_all_form16
        from src.tools.form16_tools import create_form16_tools

        with st.spinner("Computing tax and generating Form 16 data..."):
            try:
                if generate_all:
                    result = generate_all_form16(st.session_state.api_key, st.session_state.data_store)
                    st.markdown("### 📊 Form 16 Generation Report")
                    st.markdown(result)
                else:
                    agent = create_form16_agent(st.session_state.api_key, st.session_state.data_store)
                    emp_id = selected_emp
                    query = (
                        f"Generate Form 16 for employee '{emp_id}'. "
                        f"Use rent_paid={rent_paid}, is_metro={is_metro}. "
                        f"{'Compare both Old and New tax regimes and recommend the better one.' if regime == 'Compare Both' else f'Use {regime} tax regime.'}"
                    )
                    result = agent.invoke({"messages": [("human", query)]})["messages"][-1].content
                    st.markdown("### 📋 Tax Computation")
                    st.markdown(result)

            except Exception as e:
                st.error(f"Error: {str(e)}")

    form16_data = st.session_state.data_store.get("form16_data")
    if form16_data:
        st.divider()
        st.markdown("### ⬇️ Download Form 16 PDFs")

        for emp_id, data in form16_data.items():
            col_info, col_dl = st.columns([3, 1])
            with col_info:
                pa = data.get("part_a", {})
                pb = data.get("part_b", {})
                st.markdown(
                    f"**{pa.get('employee_name', emp_id)}** — "
                    f"PAN: {pa.get('employee_pan', 'N/A')} | "
                    f"Tax Payable: ₹{pb.get('tax_payable_or_refund', 0):,.0f} | "
                    f"Regime: {pb.get('regime', 'Old')}"
                )
            with col_dl:
                try:
                    form16_obj = Form16Data(
                        part_a=Form16PartA(**data["part_a"]),
                        part_b=Form16PartB(**data["part_b"]),
                        employee_id=data.get("employee_id", emp_id),
                        generated_on=data.get("generated_on", datetime.now().strftime("%d-%m-%Y")),
                    )
                    pdf_bytes = generate_form16_pdf(form16_obj)
                    st.download_button(
                        f"⬇️ PDF",
                        pdf_bytes,
                        f"form16_{emp_id}_{datetime.now().strftime('%Y%m%d')}.pdf",
                        "application/pdf",
                        key=f"dl_{emp_id}",
                    )
                except Exception as e:
                    st.error(f"PDF error: {e}")


# ─── GST Filing ───────────────────────────────────────────────────────────────
def page_gst():
    st.markdown("## 🧾 GST Filing")
    st.markdown("Upload invoice data to prepare GSTR-1 and GSTR-3B returns for GST filing.")

    col_upload, col_docs = st.columns([1, 1])

    with col_upload:
        st.markdown("<div class='section-header'>📁 Upload GST Invoice Data</div>", unsafe_allow_html=True)
        uploaded = st.file_uploader(
            "Invoice data (CSV/Excel)",
            type=["csv", "xlsx", "xls"],
            key="gst_upload",
        )
        if uploaded:
            df, msg = parse_gst_data(uploaded.read(), uploaded.name)
            if df is not None:
                st.session_state.data_store["gst_df"] = df
                st.success(f"✅ {msg}")
            else:
                st.error(f"❌ {msg}")

        with st.expander("📋 Expected Format"):
            sample = pd.DataFrame({
                "Invoice_Date": ["01-04-2024", "05-04-2024"],
                "Invoice_No": ["INV001", "INV002"],
                "Party_GSTIN": ["27AABCU9603R1ZX", "29AABCU9603R1ZX"],
                "Party_Name": ["ABC Pvt Ltd", "XYZ Enterprises"],
                "HSN_Code": ["998314", "8471"],
                "Taxable_Value": [100000, 50000],
                "CGST_Rate": [9, 9],
                "SGST_Rate": [9, 0],
                "IGST_Rate": [0, 18],
                "Invoice_Type": ["B2B", "B2B"],
            })
            st.dataframe(sample, use_container_width=True)
            st.download_button("⬇️ Download Template", sample.to_csv(index=False).encode(),
                               "sample_gst.csv", "text/csv")

    with col_docs:
        df = st.session_state.data_store.get("gst_df")
        if df is not None:
            st.markdown("<div class='section-header'>📊 Invoice Summary</div>", unsafe_allow_html=True)
            st.metric("Total Invoices", len(df))
            st.metric("Total Taxable Value", f"₹{df['taxable_value'].sum():,.2f}")
            total_tax = df["cgst_amount"].sum() + df["sgst_amount"].sum() + df["igst_amount"].sum()
            st.metric("Total Tax", f"₹{total_tax:,.2f}")

            if "invoice_type" in df.columns:
                type_counts = df["invoice_type"].value_counts()
                fig = px.pie(values=type_counts.values, names=type_counts.index,
                             title="Invoice Type Distribution", height=250)
                fig.update_traces(textinfo="percent+label")
                fig.update_layout(margin=dict(t=40, b=0, l=0, r=0))
                st.plotly_chart(fig, use_container_width=True)

    if st.session_state.data_store.get("gst_df") is None:
        st.info("Please upload GST invoice data to proceed.")
        return

    if not st.session_state.api_key:
        st.warning("Please configure your OpenAI API key in the sidebar settings.")
        return

    st.divider()
    st.markdown("### 🔧 GST Filing Configuration")

    col1, col2, col3 = st.columns(3)
    with col1:
        gstin = st.text_input("Your GSTIN", value=st.session_state.data_store.get("company_gstin", ""),
                               placeholder="27AABCE1234A1Z5")
    with col2:
        month = st.selectbox("Month", list(range(1, 13)),
                              format_func=lambda m: datetime(2024, m, 1).strftime("%B"),
                              index=3)
        year = st.selectbox("Year", [2024, 2025], index=0)
        period = f"{month:02d}-{year}"
    with col3:
        st.markdown("")
        st.markdown("")
        validate_btn = st.button("✅ Validate GSTIN", type="secondary", use_container_width=True)

    if validate_btn and gstin:
        from src.tools.gst_tools import create_gst_tools
        tools = create_gst_tools(st.session_state.data_store)
        val_tool = next(t for t in tools if t.name == "validate_gstin")
        result = json.loads(val_tool.run(gstin))
        if result.get("is_valid"):
            st.success(f"✅ Valid GSTIN — {', '.join(result.get('details', []))}")
        else:
            issues = [d for d in result.get("details", []) if "Invalid" in d or "must be" in d or "should" in d]
            st.error(f"❌ GSTIN Issues: {'; '.join(issues)}")

    col_gstr1, col_gstr3b, col_full = st.columns(3)
    with col_gstr1:
        gen_gstr1 = st.button("📄 Generate GSTR-1", type="primary", use_container_width=True)
    with col_gstr3b:
        gen_gstr3b = st.button("📄 Generate GSTR-3B", type="primary", use_container_width=True)
    with col_full:
        gen_full = st.button("🚀 Full GST Report (AI)", type="primary", use_container_width=True)

    if gen_gstr1 or gen_gstr3b or gen_full:
        from src.tools.gst_tools import create_gst_tools
        from src.agents.gst_agent import create_gst_agent, run_full_gst_filing

        with st.spinner("Preparing GST filing data..."):
            try:
                if gen_full:
                    result = run_full_gst_filing(
                        st.session_state.api_key,
                        st.session_state.data_store,
                        gstin or "GSTIN_NOT_PROVIDED",
                        period,
                    )
                    st.markdown("### 📊 GST Filing Report")
                    st.markdown(result)

                else:
                    tools = create_gst_tools(st.session_state.data_store)
                    if gen_gstr1:
                        gstr1_tool = next(t for t in tools if t.name == "generate_gstr1")
                        gstr1_result = json.loads(gstr1_tool.run({"gstin": gstin or "GSTIN_NOT_PROVIDED", "period": period}))
                        if "error" not in gstr1_result:
                            st.session_state.data_store["gstr1_data"] = gstr1_result
                            st.success("✅ GSTR-1 data generated!")
                        else:
                            st.error(gstr1_result["error"])
                    elif gen_gstr3b:
                        gstr3b_tool = next(t for t in tools if t.name == "generate_gstr3b")
                        gstr3b_result = json.loads(gstr3b_tool.run({"gstin": gstin or "GSTIN_NOT_PROVIDED", "period": period}))
                        if "error" not in gstr3b_result:
                            st.session_state.data_store["gstr3b_data"] = gstr3b_result
                            st.success("✅ GSTR-3B data generated!")
                        else:
                            st.error(gstr3b_result["error"])
            except Exception as e:
                st.error(f"Error: {str(e)}")

    tab1, tab2, tab3, tab4 = st.tabs(["📊 Summary", "📄 GSTR-1", "📄 GSTR-3B", "📈 Analytics"])

    df = st.session_state.data_store["gst_df"]

    with tab1:
        col_a, col_b, col_c, col_d = st.columns(4)
        total_taxable = float(df["taxable_value"].sum())
        total_cgst = float(df["cgst_amount"].sum())
        total_sgst = float(df["sgst_amount"].sum())
        total_igst = float(df["igst_amount"].sum())
        total_tax = total_cgst + total_sgst + total_igst

        col_a.metric("Taxable Value", f"₹{total_taxable:,.0f}")
        col_b.metric("CGST", f"₹{total_cgst:,.0f}")
        col_c.metric("SGST/UTGST", f"₹{total_sgst:,.0f}")
        col_d.metric("IGST", f"₹{total_igst:,.0f}")

        st.metric("Total Tax Liability", f"₹{total_tax:,.2f}")
        st.metric("Total Invoice Value", f"₹{total_taxable + total_tax:,.2f}")

        st.dataframe(df.head(50), use_container_width=True)
        st.caption(f"Showing first 50 of {len(df)} invoices")

    with tab2:
        gstr1 = st.session_state.data_store.get("gstr1_data")
        if gstr1:
            st.markdown(f"**GSTIN:** {gstr1.get('gstin')} | **Period:** {gstr1.get('period')}")
            col_a, col_b, col_c = st.columns(3)
            col_a.metric("B2B Invoices", gstr1.get("b2b_count", 0))
            col_b.metric("B2CS Invoices", gstr1.get("b2cs_count", 0))
            col_c.metric("B2CL Invoices", gstr1.get("b2cl_count", 0))

            if gstr1.get("b2b"):
                st.markdown("**B2B Invoices (Registered Parties)**")
                b2b_df = pd.DataFrame([{
                    "GSTIN": e.get("gstin"), "Party": e.get("party_name"),
                    "Invoices": len(e.get("invoices", [])),
                    "Taxable (₹)": f"₹{e.get('total_taxable_value', 0):,.0f}",
                    "CGST (₹)": f"₹{e.get('total_cgst', 0):,.0f}",
                    "SGST (₹)": f"₹{e.get('total_sgst', 0):,.0f}",
                    "IGST (₹)": f"₹{e.get('total_igst', 0):,.0f}",
                } for e in gstr1["b2b"]])
                st.dataframe(b2b_df, use_container_width=True, hide_index=True)

            json_bytes = json.dumps(gstr1, indent=2, default=str).encode()
            st.download_button("⬇️ Download GSTR-1 JSON", json_bytes,
                               f"GSTR1_{gstin}_{period}.json", "application/json", type="primary")
        else:
            st.info("Click 'Generate GSTR-1' to prepare the return data.")

    with tab3:
        gstr3b = st.session_state.data_store.get("gstr3b_data")
        if gstr3b:
            st.markdown(f"**GSTIN:** {gstr3b.get('gstin')} | **Period:** {gstr3b.get('period')}")
            outward = gstr3b.get("3.1_outward_supplies", {}).get("(a) Taxable outward supplies (other than zero-rated)", {})
            col_a, col_b, col_c = st.columns(3)
            col_a.metric("IGST Payable", f"₹{outward.get('integrated_tax', 0):,.2f}")
            col_b.metric("CGST Payable", f"₹{outward.get('central_tax', 0):,.2f}")
            col_c.metric("SGST Payable", f"₹{outward.get('state_ut_tax', 0):,.2f}")

            tax_payable = gstr3b.get("6_payment_of_tax", {}).get("tax_payable", {})
            total_payable = sum(tax_payable.values())
            st.metric("Total Tax Payable", f"₹{total_payable:,.2f}")
            st.info(gstr3b.get("filing_summary", ""))

            json_bytes = json.dumps(gstr3b, indent=2, default=str).encode()
            st.download_button("⬇️ Download GSTR-3B JSON", json_bytes,
                               f"GSTR3B_{gstin}_{period}.json", "application/json", type="primary")
        else:
            st.info("Click 'Generate GSTR-3B' to prepare the return data.")

    with tab4:
        st.markdown("### 📈 GST Analytics")

        if "cgst_rate" in df.columns:
            df["gst_rate"] = df.apply(
                lambda r: (r["cgst_rate"] + r["sgst_rate"]) if r.get("igst_rate", 0) == 0 else r.get("igst_rate", 0),
                axis=1
            )
            rate_summary = df.groupby("gst_rate").agg(
                invoices=("invoice_no", "count"),
                taxable=("taxable_value", "sum"),
            ).reset_index()

            col_r1, col_r2 = st.columns(2)
            with col_r1:
                fig = px.bar(rate_summary, x="gst_rate", y="taxable",
                             title="Taxable Value by GST Rate (%)",
                             labels={"gst_rate": "GST Rate (%)", "taxable": "Taxable Value (₹)"},
                             color="gst_rate", color_continuous_scale="Blues")
                st.plotly_chart(fig, use_container_width=True)
            with col_r2:
                fig = px.pie(rate_summary, values="invoices", names="gst_rate",
                             title="Invoice Count by GST Rate (%)")
                st.plotly_chart(fig, use_container_width=True)

        if "invoice_type" in df.columns:
            type_summary = df.groupby("invoice_type").agg(
                invoices=("invoice_no", "count"),
                taxable=("taxable_value", "sum"),
            ).reset_index()
            fig = px.bar(type_summary, x="invoice_type", y="taxable",
                         title="Taxable Value by Invoice Type",
                         color="invoice_type")
            st.plotly_chart(fig, use_container_width=True)


# ─── AI Chat Assistant ─────────────────────────────────────────────────────────
def page_chat():
    st.markdown("## 💬 AI Financial Assistant")
    st.markdown("Ask any financial, tax, or accounting question. The AI has access to your uploaded data.")

    if not st.session_state.api_key:
        st.warning("Please configure your OpenAI API key in the sidebar settings.")
        return

    col_agent, col_preset = st.columns([1, 2])
    with col_agent:
        agent_type = st.selectbox(
            "Select Agent",
            ["Ledger Auditor", "Form 16 / Tax Expert", "GST Consultant"],
            help="Choose the specialized agent for your query",
        )
    with col_preset:
        preset_queries = {
            "Ledger Auditor": [
                "Are the books balanced?",
                "What are the top 5 expenses?",
                "Find all large transactions above ₹5 lakhs",
                "Give me a complete audit summary",
            ],
            "Form 16 / Tax Expert": [
                "List all employees and their gross salary",
                "Which regime is better for all employees?",
                "Calculate TDS for employee E001",
                "What is the total TDS liability?",
            ],
            "GST Consultant": [
                "What is the total GST liability?",
                "Show me the B2B invoice summary",
                "Validate my GSTIN",
                "What is the GST breakdown by rate?",
            ],
        }
        preset = st.selectbox("Quick Questions:", ["-- Type your own --"] + preset_queries[agent_type])

    for msg in st.session_state.chat_history:
        if msg["role"] == "user":
            st.markdown(f"<div class='chat-user'>🧑 <strong>You:</strong> {msg['content']}</div>",
                        unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='chat-ai'>🤖 <strong>AI Agent:</strong>\n\n{msg['content']}</div>",
                        unsafe_allow_html=True)

    with st.form("chat_form", clear_on_submit=True):
        user_input = st.text_area(
            "Your question:",
            value="" if preset == "-- Type your own --" else preset,
            placeholder="Ask about your financial data, tax calculations, GST returns...",
            height=80,
        )
        submitted = st.form_submit_button("Send", type="primary", use_container_width=True)

    if submitted and user_input.strip():
        st.session_state.chat_history.append({"role": "user", "content": user_input})

        with st.spinner("AI is thinking..."):
            try:
                if agent_type == "Ledger Auditor":
                    from src.agents.ledger_agent import create_ledger_agent
                    agent = create_ledger_agent(st.session_state.api_key, st.session_state.data_store)
                elif agent_type == "Form 16 / Tax Expert":
                    from src.agents.form16_agent import create_form16_agent
                    agent = create_form16_agent(st.session_state.api_key, st.session_state.data_store)
                else:
                    from src.agents.gst_agent import create_gst_agent
                    agent = create_gst_agent(st.session_state.api_key, st.session_state.data_store)

                result = agent.invoke({"messages": [("human", user_input)]})
                response = result["messages"][-1].content
                st.session_state.chat_history.append({"role": "assistant", "content": response})
                st.rerun()

            except Exception as e:
                err_msg = f"Error: {str(e)}"
                st.session_state.chat_history.append({"role": "assistant", "content": err_msg})
                st.rerun()

    if st.session_state.chat_history:
        col_clear, _ = st.columns([1, 4])
        with col_clear:
            if st.button("🗑️ Clear Chat", type="secondary"):
                st.session_state.chat_history = []
                st.rerun()


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    init_state()
    render_sidebar()

    page = st.session_state.page
    if page == "Home":
        page_home()
    elif page == "Ledger":
        page_ledger()
    elif page == "Form16":
        page_form16()
    elif page == "GST":
        page_gst()
    elif page == "Chat":
        page_chat()


if __name__ == "__main__":
    main()
