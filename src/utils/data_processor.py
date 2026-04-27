import pandas as pd
import io
from pathlib import Path
from typing import Optional, Tuple
import re


LEDGER_COLUMN_ALIASES = {
    "date": ["date", "transaction_date", "txn_date", "posting_date", "value_date"],
    "voucher_no": ["voucher_no", "voucher", "vch_no", "ref_no", "reference", "txn_id", "trans_no"],
    "narration": ["narration", "description", "particulars", "remarks", "details", "memo"],
    "account": ["account", "account_name", "ledger", "ledger_name", "head", "gl_account"],
    "debit": ["debit", "dr", "debit_amount", "withdrawal", "outflow"],
    "credit": ["credit", "cr", "credit_amount", "deposit", "inflow"],
    "balance": ["balance", "closing_balance", "running_balance", "net_balance"],
}

GST_COLUMN_ALIASES = {
    "invoice_no": ["invoice_no", "invoice_number", "inv_no", "bill_no"],
    "invoice_date": ["invoice_date", "date", "bill_date", "inv_date"],
    "party_gstin": ["party_gstin", "gstin", "customer_gstin", "buyer_gstin", "supplier_gstin"],
    "party_name": ["party_name", "customer_name", "buyer_name", "supplier_name", "name"],
    "hsn_code": ["hsn_code", "hsn", "sac_code", "hsn_sac"],
    "taxable_value": ["taxable_value", "taxable_amount", "assessable_value", "base_amount"],
    "cgst_rate": ["cgst_rate", "cgst_%", "cgst_pct"],
    "sgst_rate": ["sgst_rate", "sgst_%", "sgst_pct", "utgst_rate"],
    "igst_rate": ["igst_rate", "igst_%", "igst_pct"],
    "cgst_amount": ["cgst_amount", "cgst_amt", "cgst"],
    "sgst_amount": ["sgst_amount", "sgst_amt", "sgst", "utgst_amount"],
    "igst_amount": ["igst_amount", "igst_amt", "igst"],
    "invoice_type": ["invoice_type", "type", "supply_type"],
}

EMPLOYEE_COLUMN_ALIASES = {
    "employee_id": ["employee_id", "emp_id", "staff_id", "id"],
    "name": ["name", "employee_name", "emp_name", "full_name"],
    "pan": ["pan", "pan_no", "pan_number"],
    "designation": ["designation", "position", "title", "role"],
    "basic_salary": ["basic_salary", "basic", "basic_pay"],
    "hra": ["hra", "house_rent_allowance"],
    "special_allowance": ["special_allowance", "special_all", "spl_allowance"],
    "lta": ["lta", "leave_travel_allowance", "travel_allowance"],
    "medical_allowance": ["medical_allowance", "medical", "medical_all"],
    "professional_tax": ["professional_tax", "prof_tax", "pt"],
    "tds_deducted": ["tds_deducted", "tds", "income_tax", "it_deducted"],
    "section_80c": ["section_80c", "80c", "80c_investments"],
    "section_80d": ["section_80d", "80d", "health_insurance"],
}


def _normalize_columns(df: pd.DataFrame, aliases: dict) -> pd.DataFrame:
    col_map = {}
    df_cols_lower = {c.lower().strip().replace(" ", "_"): c for c in df.columns}

    for target, variants in aliases.items():
        for variant in variants:
            if variant in df_cols_lower:
                col_map[df_cols_lower[variant]] = target
                break

    return df.rename(columns=col_map)


def _parse_amount(value) -> float:
    if pd.isna(value):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = re.sub(r"[₹,\s]", "", str(value))
    cleaned = cleaned.replace("(", "-").replace(")", "")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def parse_ledger(file_content: bytes, filename: str) -> Tuple[Optional[pd.DataFrame], str]:
    try:
        ext = Path(filename).suffix.lower()
        if ext in [".xlsx", ".xls"]:
            df = pd.read_excel(io.BytesIO(file_content))
        elif ext == ".csv":
            df = pd.read_csv(io.BytesIO(file_content))
        else:
            return None, f"Unsupported file format: {ext}. Use CSV or Excel."

        df = _normalize_columns(df, LEDGER_COLUMN_ALIASES)

        required = ["date", "narration", "debit", "credit"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            return None, f"Missing required columns: {missing}. Found: {list(df.columns)}"

        for col in ["debit", "credit", "balance"]:
            if col in df.columns:
                df[col] = df[col].apply(_parse_amount)

        if "balance" not in df.columns:
            df["balance"] = (df["credit"].cumsum() - df["debit"].cumsum())

        if "voucher_no" not in df.columns:
            df["voucher_no"] = [f"JV{str(i+1).zfill(4)}" for i in range(len(df))]

        if "account" not in df.columns:
            df["account"] = "General"

        df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce").dt.strftime("%d-%m-%Y")
        df = df.dropna(subset=["date"])
        df = df.reset_index(drop=True)

        return df, f"Successfully loaded {len(df)} ledger entries."

    except Exception as e:
        return None, f"Error parsing ledger: {str(e)}"


def parse_gst_data(file_content: bytes, filename: str) -> Tuple[Optional[pd.DataFrame], str]:
    try:
        ext = Path(filename).suffix.lower()
        if ext in [".xlsx", ".xls"]:
            df = pd.read_excel(io.BytesIO(file_content))
        elif ext == ".csv":
            df = pd.read_csv(io.BytesIO(file_content))
        else:
            return None, f"Unsupported format: {ext}"

        df = _normalize_columns(df, GST_COLUMN_ALIASES)

        required = ["invoice_no", "invoice_date", "taxable_value"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            return None, f"Missing columns: {missing}. Found: {list(df.columns)}"

        for col in ["taxable_value", "cgst_rate", "sgst_rate", "igst_rate",
                    "cgst_amount", "sgst_amount", "igst_amount"]:
            if col in df.columns:
                df[col] = df[col].apply(_parse_amount)

        if "cgst_amount" not in df.columns or df["cgst_amount"].sum() == 0:
            if "cgst_rate" in df.columns:
                df["cgst_amount"] = df["taxable_value"] * df["cgst_rate"] / 100
        if "sgst_amount" not in df.columns or df["sgst_amount"].sum() == 0:
            if "sgst_rate" in df.columns:
                df["sgst_amount"] = df["taxable_value"] * df["sgst_rate"] / 100
        if "igst_amount" not in df.columns or df["igst_amount"].sum() == 0:
            if "igst_rate" in df.columns:
                df["igst_amount"] = df["taxable_value"] * df["igst_rate"] / 100

        for col in ["cgst_rate", "sgst_rate", "igst_rate", "cgst_amount", "sgst_amount", "igst_amount"]:
            if col not in df.columns:
                df[col] = 0.0

        df["total_tax"] = df["cgst_amount"] + df["sgst_amount"] + df["igst_amount"]
        df["total_amount"] = df["taxable_value"] + df["total_tax"]

        if "invoice_type" not in df.columns:
            df["invoice_type"] = df.apply(
                lambda r: "B2B" if pd.notna(r.get("party_gstin", "")) and str(r.get("party_gstin", "")).strip() else "B2C",
                axis=1
            )

        if "party_gstin" not in df.columns:
            df["party_gstin"] = ""
        if "party_name" not in df.columns:
            df["party_name"] = "Unknown Party"
        if "hsn_code" not in df.columns:
            df["hsn_code"] = ""
        if "place_of_supply" not in df.columns:
            df["place_of_supply"] = ""

        df["invoice_date"] = pd.to_datetime(df["invoice_date"], dayfirst=True, errors="coerce").dt.strftime("%d-%m-%Y")

        return df, f"Successfully loaded {len(df)} GST invoices."

    except Exception as e:
        return None, f"Error parsing GST data: {str(e)}"


def parse_employee_data(file_content: bytes, filename: str) -> Tuple[Optional[pd.DataFrame], str]:
    try:
        ext = Path(filename).suffix.lower()
        if ext in [".xlsx", ".xls"]:
            df = pd.read_excel(io.BytesIO(file_content))
        elif ext == ".csv":
            df = pd.read_csv(io.BytesIO(file_content))
        else:
            return None, f"Unsupported format: {ext}"

        df = _normalize_columns(df, EMPLOYEE_COLUMN_ALIASES)

        required = ["name"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            return None, f"Missing columns: {missing}. Found: {list(df.columns)}"

        salary_cols = ["basic_salary", "hra", "special_allowance", "lta",
                       "medical_allowance", "professional_tax", "tds_deducted",
                       "section_80c", "section_80d"]
        for col in salary_cols:
            if col in df.columns:
                df[col] = df[col].apply(_parse_amount)
            else:
                df[col] = 0.0

        if "employee_id" not in df.columns:
            df["employee_id"] = [f"E{str(i+1).zfill(3)}" for i in range(len(df))]
        if "pan" not in df.columns:
            df["pan"] = "XXXXX0000X"
        if "designation" not in df.columns:
            df["designation"] = "Employee"

        return df, f"Successfully loaded {len(df)} employee records."

    except Exception as e:
        return None, f"Error parsing employee data: {str(e)}"


def get_ledger_stats(df: pd.DataFrame) -> dict:
    return {
        "total_entries": len(df),
        "total_debit": float(df["debit"].sum()),
        "total_credit": float(df["credit"].sum()),
        "net_balance": float(df["credit"].sum() - df["debit"].sum()),
        "unique_accounts": int(df["account"].nunique()) if "account" in df.columns else 0,
        "date_range": f"{df['date'].iloc[0]} to {df['date'].iloc[-1]}" if len(df) > 0 else "N/A",
    }
