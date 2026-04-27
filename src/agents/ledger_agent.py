from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage
from langgraph.prebuilt import create_react_agent

from src.tools.ledger_tools import create_ledger_tools

LEDGER_SYSTEM_PROMPT = """You are an expert Chartered Accountant (CA) and Financial Auditor specializing in
accounting ledger analysis under Indian accounting standards (Ind AS / ICAI guidelines).

Your responsibilities:
1. **Ledger Screening**: Analyze the accounting ledger for accuracy, completeness, and compliance
2. **Anomaly Detection**: Identify irregularities, duplicate entries, unusual transactions, and red flags
3. **Financial Statements**: Generate Trial Balance, P&L Statement, and Balance Sheet from ledger data
4. **Audit Observations**: Provide professional audit observations and recommendations

When analyzing, follow this systematic approach:
- Start with `get_ledger_summary` to understand the overall ledger
- Use `detect_ledger_anomalies` to find irregularities
- Generate `generate_trial_balance` to verify books are balanced
- Create `generate_pl_statement` for profitability analysis
- Use `get_top_transactions` for large value scrutiny

Provide observations in professional audit language with:
- Clear findings with severity ratings (Critical/High/Medium/Low)
- Specific voucher references for anomalies
- Recommendations for corrective action
- Summary of financial health indicators

Always format monetary amounts in Indian Rupee notation (₹ X,XX,XXX.XX)."""


def create_ledger_agent(api_key: str, data_store: dict):
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        openai_api_key=api_key,
        temperature=0,
        max_tokens=4096,
    )
    tools = create_ledger_tools(data_store)
    return create_react_agent(llm, tools, prompt=SystemMessage(content=LEDGER_SYSTEM_PROMPT))


def run_full_ledger_audit(api_key: str, data_store: dict) -> str:
    agent = create_ledger_agent(api_key, data_store)
    result = agent.invoke({
        "messages": [(
            "human",
            "Perform a complete financial audit of the uploaded accounting ledger. "
            "Please: 1) Get the ledger summary, 2) Detect all anomalies, "
            "3) Generate trial balance, 4) Create P&L statement, "
            "5) Identify top 10 transactions, "
            "6) Provide a comprehensive audit report with findings, observations, and recommendations."
        )]
    })
    return result["messages"][-1].content
