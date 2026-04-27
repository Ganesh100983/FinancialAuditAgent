import json
import pandas as pd
from typing import Any
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from src.models.financial_models import AnomalyType, TransactionType


ACCOUNT_CATEGORIES = {
    TransactionType.INCOME: [
        "sales", "revenue", "income", "receipts", "interest received",
        "commission received", "rent received", "dividend", "other income",
        "service income", "consulting income",
    ],
    TransactionType.EXPENSE: [
        "purchase", "expense", "salary", "wages", "rent", "electricity",
        "telephone", "internet", "repair", "maintenance", "printing",
        "stationery", "travel", "conveyance", "advertisement", "marketing",
        "insurance", "professional fees", "audit fees", "bank charges",
        "interest paid", "depreciation", "misc expense", "office expense",
    ],
    TransactionType.ASSET: [
        "cash", "bank", "hdfc", "sbi", "icici", "axis", "stock", "inventory",
        "debtors", "receivable", "advance", "prepaid", "machinery",
        "equipment", "furniture", "vehicle", "land", "building", "investment",
        "fixed deposit", "capital work",
    ],
    TransactionType.LIABILITY: [
        "creditors", "payable", "loan", "borrowing", "overdraft", "deposit received",
        "advance from customer", "outstanding", "accrued", "provision",
        "tax payable", "gst payable", "tds payable",
    ],
    TransactionType.EQUITY: [
        "capital", "owner", "proprietor", "partner", "share capital",
        "retained earnings", "reserves", "surplus", "drawing",
    ],
}


def _categorize_account(account_name: str) -> str:
    name_lower = account_name.lower()
    for category, keywords in ACCOUNT_CATEGORIES.items():
        for kw in keywords:
            if kw in name_lower:
                return category.value
    return "Uncategorized"


def _detect_anomalies_in_df(df: pd.DataFrame) -> list:
    anomalies = []
    threshold = df["debit"].replace(0, pd.NA).dropna().mean() * 5 if len(df) > 0 else 1_000_000

    for idx, row in df.iterrows():
        amount = max(row.get("debit", 0), row.get("credit", 0))

        if amount > 0 and amount % 100000 == 0 and amount >= 500000:
            anomalies.append({
                "row_index": int(idx),
                "voucher_no": str(row.get("voucher_no", "")),
                "anomaly_type": AnomalyType.ROUND_NUMBER.value,
                "description": f"Suspiciously round amount: ₹{amount:,.0f}",
                "amount": float(amount),
                "severity": "Low",
            })

        if threshold and amount > threshold:
            anomalies.append({
                "row_index": int(idx),
                "voucher_no": str(row.get("voucher_no", "")),
                "anomaly_type": AnomalyType.LARGE_AMOUNT.value,
                "description": f"Unusually large amount ₹{amount:,.0f} (>5x avg)",
                "amount": float(amount),
                "severity": "High",
            })

        narration = str(row.get("narration", "")).strip()
        if not narration or narration.lower() in ["nan", "none", "-", "n/a"]:
            anomalies.append({
                "row_index": int(idx),
                "voucher_no": str(row.get("voucher_no", "")),
                "anomaly_type": AnomalyType.MISSING_NARRATION.value,
                "description": "Transaction has no narration/description",
                "amount": float(amount),
                "severity": "Medium",
            })

    seen = set()
    for idx, row in df.iterrows():
        key = (str(row.get("narration", "")), row.get("debit", 0), row.get("credit", 0))
        if key in seen and key[0] not in ("", "nan"):
            anomalies.append({
                "row_index": int(idx),
                "voucher_no": str(row.get("voucher_no", "")),
                "anomaly_type": AnomalyType.DUPLICATE.value,
                "description": f"Possible duplicate entry: {key[0][:40]}",
                "amount": float(max(row.get("debit", 0), row.get("credit", 0))),
                "severity": "High",
            })
        seen.add(key)

    return anomalies


def create_ledger_tools(data_store: dict) -> list:

    class AnalysisInput(BaseModel):
        query: str = Field(default="full", description="Type of analysis")

    def get_ledger_summary(query: str = "full") -> str:
        df = data_store.get("ledger_df")
        if df is None:
            return json.dumps({"error": "No ledger data loaded. Please upload a ledger file first."})

        total_debit = float(df["debit"].sum())
        total_credit = float(df["credit"].sum())

        category_totals: dict = {}
        for _, row in df.iterrows():
            cat = _categorize_account(str(row.get("account", row.get("narration", ""))))
            amount = float(row.get("credit", 0)) if row.get("credit", 0) > 0 else float(row.get("debit", 0))
            category_totals[cat] = category_totals.get(cat, 0) + amount

        result = {
            "total_entries": len(df),
            "total_debit": total_debit,
            "total_credit": total_credit,
            "net_balance": total_credit - total_debit,
            "date_range": f"{df['date'].iloc[0]} to {df['date'].iloc[-1]}" if len(df) > 0 else "N/A",
            "unique_accounts": int(df["account"].nunique()) if "account" in df.columns else 0,
            "category_breakdown": category_totals,
        }
        data_store["ledger_summary"] = result
        return json.dumps(result, indent=2)

    def detect_ledger_anomalies(query: str = "all") -> str:
        df = data_store.get("ledger_df")
        if df is None:
            return json.dumps({"error": "No ledger data loaded."})

        anomalies = _detect_anomalies_in_df(df)
        data_store["anomalies"] = anomalies

        high = [a for a in anomalies if a["severity"] == "High"]
        medium = [a for a in anomalies if a["severity"] == "Medium"]
        low = [a for a in anomalies if a["severity"] == "Low"]

        return json.dumps({
            "total_anomalies": len(anomalies),
            "high_severity": len(high),
            "medium_severity": len(medium),
            "low_severity": len(low),
            "anomalies": anomalies[:30],
            "summary": f"Found {len(anomalies)} anomalies: {len(high)} high, {len(medium)} medium, {len(low)} low severity.",
        }, indent=2)

    def generate_trial_balance(query: str = "all") -> str:
        df = data_store.get("ledger_df")
        if df is None:
            return json.dumps({"error": "No ledger data loaded."})

        if "account" not in df.columns:
            df["account"] = df["narration"].apply(
                lambda x: str(x).split()[0] if pd.notna(x) else "General"
            )

        trial = df.groupby("account").agg(
            total_debit=("debit", "sum"),
            total_credit=("credit", "sum")
        ).reset_index()

        trial["closing_balance"] = trial["total_credit"] - trial["total_debit"]
        trial["balance_type"] = trial["closing_balance"].apply(lambda x: "Cr" if x >= 0 else "Dr")
        trial["closing_balance"] = trial["closing_balance"].abs()

        rows = trial.to_dict("records")
        total_dr = float(trial["total_debit"].sum())
        total_cr = float(trial["total_credit"].sum())

        result = {
            "trial_balance": rows,
            "total_debit": total_dr,
            "total_credit": total_cr,
            "is_balanced": abs(total_dr - total_cr) < 0.01,
            "difference": abs(total_dr - total_cr),
        }
        data_store["trial_balance"] = result
        return json.dumps(result, indent=2, default=str)

    def generate_pl_statement(query: str = "full") -> str:
        df = data_store.get("ledger_df")
        if df is None:
            return json.dumps({"error": "No ledger data loaded."})

        income_accounts = {}
        expense_accounts = {}

        for _, row in df.iterrows():
            acct = str(row.get("account", row.get("narration", "General")))
            cat = _categorize_account(acct)
            if cat == TransactionType.INCOME.value:
                income_accounts[acct] = income_accounts.get(acct, 0) + float(row.get("credit", 0))
            elif cat == TransactionType.EXPENSE.value:
                expense_accounts[acct] = expense_accounts.get(acct, 0) + float(row.get("debit", 0))

        total_income = sum(income_accounts.values())
        total_expenses = sum(expense_accounts.values())
        net_profit = total_income - total_expenses

        result = {
            "income": income_accounts,
            "expenses": expense_accounts,
            "total_income": total_income,
            "total_expenses": total_expenses,
            "net_profit": net_profit,
            "profit_margin": (net_profit / total_income * 100) if total_income > 0 else 0,
            "analysis": (
                f"Net {'Profit' if net_profit >= 0 else 'Loss'}: ₹{abs(net_profit):,.2f}. "
                f"Profit margin: {(net_profit / total_income * 100) if total_income > 0 else 0:.1f}%"
            ),
        }
        data_store["pl_statement"] = result
        return json.dumps(result, indent=2)

    def get_top_transactions(query: str = "10") -> str:
        df = data_store.get("ledger_df")
        if df is None:
            return json.dumps({"error": "No ledger data loaded."})

        n = int(query) if query.isdigit() else 10
        df_copy = df.copy()
        df_copy["max_amount"] = df_copy[["debit", "credit"]].max(axis=1)
        top = df_copy.nlargest(n, "max_amount")[
            ["date", "voucher_no", "narration", "account", "debit", "credit", "balance"]
        ].to_dict("records")

        return json.dumps({
            "top_transactions": top,
            "count": len(top),
        }, indent=2, default=str)

    tools = [
        StructuredTool.from_function(
            func=get_ledger_summary,
            name="get_ledger_summary",
            description=(
                "Get a complete financial summary of the accounting ledger including "
                "total debits, credits, net balance, category breakdown, and date range. "
                "Use this first to understand the overall ledger structure."
            ),
            args_schema=AnalysisInput,
        ),
        StructuredTool.from_function(
            func=detect_ledger_anomalies,
            name="detect_ledger_anomalies",
            description=(
                "Detect anomalies and irregularities in the accounting ledger. "
                "Identifies: duplicate entries, round-number transactions, unusually large amounts, "
                "missing narrations, and weekend entries. Returns severity-classified findings."
            ),
            args_schema=AnalysisInput,
        ),
        StructuredTool.from_function(
            func=generate_trial_balance,
            name="generate_trial_balance",
            description=(
                "Generate a trial balance from the ledger data showing all accounts with "
                "their total debits, total credits, and closing balance. "
                "Also checks if the books are balanced (total Dr = total Cr)."
            ),
            args_schema=AnalysisInput,
        ),
        StructuredTool.from_function(
            func=generate_pl_statement,
            name="generate_pl_statement",
            description=(
                "Generate a Profit & Loss (Income Statement) from the ledger. "
                "Categorizes accounts into income and expenses, calculates net profit/loss, "
                "and provides profit margin analysis."
            ),
            args_schema=AnalysisInput,
        ),
        StructuredTool.from_function(
            func=get_top_transactions,
            name="get_top_transactions",
            description=(
                "Get the top N transactions by amount from the ledger. "
                "Pass the number as a string (e.g., '10' for top 10 transactions). "
                "Useful for identifying the most significant transactions."
            ),
            args_schema=AnalysisInput,
        ),
    ]
    return tools
