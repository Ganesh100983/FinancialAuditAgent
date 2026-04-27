import json
from collections import defaultdict
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from src.models.financial_models import GSTR1Summary, GSTR1B2BEntry, GSTR3BSummary, GSTR3BOutwardSupplies


GST_HSN_RATES = {
    "0401": 0, "0402": 5, "1001": 0, "1006": 0, "2201": 18,
    "3004": 12, "4901": 0, "6101": 12, "7108": 3, "8471": 18,
    "8517": 18, "8703": 28, "9403": 18, "9989": 18, "9983": 18,
    "998314": 18, "996111": 18,
}

PLACE_OF_SUPPLY_CODES = {
    "01": "Jammu & Kashmir", "02": "Himachal Pradesh", "03": "Punjab",
    "04": "Chandigarh", "05": "Uttarakhand", "06": "Haryana",
    "07": "Delhi", "08": "Rajasthan", "09": "Uttar Pradesh",
    "10": "Bihar", "11": "Sikkim", "12": "Arunachal Pradesh",
    "13": "Nagaland", "14": "Manipur", "15": "Mizoram",
    "16": "Tripura", "17": "Meghalaya", "18": "Assam",
    "19": "West Bengal", "20": "Jharkhand", "21": "Odisha",
    "22": "Chhattisgarh", "23": "Madhya Pradesh", "24": "Gujarat",
    "25": "Daman & Diu", "26": "D & N Haveli", "27": "Maharashtra",
    "28": "Andhra Pradesh (old)", "29": "Karnataka", "30": "Goa",
    "31": "Lakshadweep", "32": "Kerala", "33": "Tamil Nadu",
    "34": "Puducherry", "35": "Andaman & Nicobar", "36": "Telangana",
    "37": "Andhra Pradesh", "38": "Ladakh",
}


def _get_supplier_state(gstin: str) -> str:
    if gstin and len(gstin) >= 2:
        return gstin[:2]
    return ""


def create_gst_tools(data_store: dict) -> list:

    class GSTInput(BaseModel):
        query: str = Field(default="all", description="Period or filter query")

    class GSTINInput(BaseModel):
        gstin: str = Field(description="Your GSTIN (15-character GST Identification Number)")
        period: str = Field(default="", description="Period in MM-YYYY format (e.g., '04-2024')")

    def get_gst_summary(query: str = "all") -> str:
        df = data_store.get("gst_df")
        if df is None:
            return json.dumps({"error": "No GST data loaded. Please upload invoice data first."})

        summary = {
            "total_invoices": len(df),
            "total_taxable_value": float(df["taxable_value"].sum()),
            "total_cgst": float(df["cgst_amount"].sum()),
            "total_sgst": float(df["sgst_amount"].sum()),
            "total_igst": float(df["igst_amount"].sum()),
            "total_tax": float(df["cgst_amount"].sum() + df["sgst_amount"].sum() + df["igst_amount"].sum()),
            "total_invoice_value": float(df["total_amount"].sum()) if "total_amount" in df.columns else 0,
        }

        by_type = df.groupby("invoice_type").agg(
            count=("invoice_no", "count"),
            taxable_value=("taxable_value", "sum"),
        ).reset_index().to_dict("records")
        summary["by_invoice_type"] = by_type

        if "cgst_rate" in df.columns:
            by_rate = df[df["cgst_rate"] > 0].groupby("cgst_rate").agg(
                count=("invoice_no", "count"),
                taxable_value=("taxable_value", "sum"),
                tax=("cgst_amount", "sum"),
            ).reset_index()
            by_rate["gst_rate"] = by_rate["cgst_rate"] * 2
            summary["by_gst_rate"] = by_rate.to_dict("records")

        data_store["gst_summary_data"] = summary
        return json.dumps(summary, indent=2, default=str)

    def generate_gstr1(gstin: str, period: str = "") -> str:
        df = data_store.get("gst_df")
        if df is None:
            return json.dumps({"error": "No GST invoice data loaded."})

        supplier_state = _get_supplier_state(gstin)

        b2b_groups: dict = defaultdict(lambda: {
            "gstin": "",
            "party_name": "",
            "invoices": [],
            "total_taxable_value": 0.0,
            "total_cgst": 0.0,
            "total_sgst": 0.0,
            "total_igst": 0.0,
            "total_cess": 0.0,
        })

        b2cs_list = []
        b2cl_list = []

        for _, row in df.iterrows():
            inv_type = str(row.get("invoice_type", "B2C")).upper()
            party_gstin = str(row.get("party_gstin", "")).strip()
            taxable = float(row.get("taxable_value", 0))
            cgst = float(row.get("cgst_amount", 0))
            sgst = float(row.get("sgst_amount", 0))
            igst = float(row.get("igst_amount", 0))
            total = float(row.get("total_amount", taxable + cgst + sgst + igst))

            invoice_item = {
                "invoice_no": str(row.get("invoice_no", "")),
                "invoice_date": str(row.get("invoice_date", "")),
                "invoice_value": total,
                "pos": str(row.get("place_of_supply", "")),
                "reverse_charge": "N",
                "invoice_type": "Regular",
                "taxable_value": taxable,
                "igst": igst,
                "cgst": cgst,
                "sgst": sgst,
                "cess": 0.0,
            }

            if inv_type == "B2B" and party_gstin:
                g = b2b_groups[party_gstin]
                g["gstin"] = party_gstin
                g["party_name"] = str(row.get("party_name", ""))
                g["invoices"].append(invoice_item)
                g["total_taxable_value"] += taxable
                g["total_cgst"] += cgst
                g["total_sgst"] += sgst
                g["total_igst"] += igst
            else:
                if taxable > 250000:
                    b2cl_list.append({
                        **invoice_item,
                        "party_name": str(row.get("party_name", "Consumer")),
                    })
                else:
                    b2cs_list.append({
                        "supply_type": "INTRA" if igst == 0 else "INTER",
                        "pos": str(row.get("place_of_supply", "")),
                        "rate": float(row.get("cgst_rate", 0)) * 2 if igst == 0 else float(row.get("igst_rate", 0)),
                        "taxable_value": taxable,
                        "igst": igst,
                        "cgst": cgst,
                        "sgst": sgst,
                    })

        hsn_summary = _compute_hsn_summary(df)

        b2b_list = list(b2b_groups.values())
        total_taxable = float(df["taxable_value"].sum())
        total_cgst = float(df["cgst_amount"].sum())
        total_sgst = float(df["sgst_amount"].sum())
        total_igst = float(df["igst_amount"].sum())

        gstr1 = {
            "gstin": gstin,
            "period": period or "2024-25",
            "b2b": b2b_list,
            "b2cs": b2cs_list,
            "b2cl": b2cl_list,
            "hsn_summary": hsn_summary,
            "total_taxable_value": total_taxable,
            "total_cgst": total_cgst,
            "total_sgst": total_sgst,
            "total_igst": total_igst,
            "total_tax": total_cgst + total_sgst + total_igst,
            "invoice_count": len(df),
            "b2b_count": len(b2b_list),
            "b2cs_count": len(b2cs_list),
            "b2cl_count": len(b2cl_list),
        }
        data_store["gstr1_data"] = gstr1
        return json.dumps(gstr1, indent=2, default=str)

    def generate_gstr3b(gstin: str, period: str = "") -> str:
        df = data_store.get("gst_df")
        if df is None:
            return json.dumps({"error": "No GST data loaded."})

        total_taxable = float(df["taxable_value"].sum())
        total_cgst = float(df["cgst_amount"].sum())
        total_sgst = float(df["sgst_amount"].sum())
        total_igst = float(df["igst_amount"].sum())
        total_tax = total_cgst + total_sgst + total_igst

        nil_df = df[df["taxable_value"] > 0]
        nil_supplies = float(df[df["cgst_amount"] + df["sgst_amount"] + df["igst_amount"] == 0]["taxable_value"].sum())

        gstr3b = {
            "gstin": gstin,
            "period": period or "2024-25",
            "3.1_outward_supplies": {
                "(a) Taxable outward supplies (other than zero-rated)": {
                    "total_taxable_value": total_taxable,
                    "integrated_tax": total_igst,
                    "central_tax": total_cgst,
                    "state_ut_tax": total_sgst,
                    "cess": 0.0,
                },
                "(b) Zero rated supplies": {
                    "total_taxable_value": 0.0,
                    "integrated_tax": 0.0,
                    "central_tax": 0.0,
                    "state_ut_tax": 0.0,
                    "cess": 0.0,
                },
                "(c) Nil-rated, Exempt, Non-GST supplies": {
                    "inter_state": nil_supplies,
                    "intra_state": 0.0,
                },
                "(d) Inward supplies on reverse charge": {
                    "integrated_tax": 0.0,
                    "central_tax": 0.0,
                    "state_ut_tax": 0.0,
                    "cess": 0.0,
                },
            },
            "4_ITC_details": {
                "(A) ITC Available": {
                    "(1) Import of goods": {"igst": 0.0, "cgst": 0.0, "sgst": 0.0, "cess": 0.0},
                    "(2) Import of services": {"igst": 0.0, "cgst": 0.0, "sgst": 0.0, "cess": 0.0},
                    "(3) Inward supplies liable to reverse charge": {"igst": 0.0, "cgst": 0.0, "sgst": 0.0, "cess": 0.0},
                    "(4) Inward supplies from ISD": {"igst": 0.0, "cgst": 0.0, "sgst": 0.0, "cess": 0.0},
                    "(5) All other ITC": {"igst": 0.0, "cgst": 0.0, "sgst": 0.0, "cess": 0.0},
                },
                "(B) ITC Reversed": {
                    "(1) As per Rule 42 & 43": {"igst": 0.0, "cgst": 0.0, "sgst": 0.0, "cess": 0.0},
                    "(2) Others": {"igst": 0.0, "cgst": 0.0, "sgst": 0.0, "cess": 0.0},
                },
                "(C) Net ITC Available": {"igst": 0.0, "cgst": 0.0, "sgst": 0.0, "cess": 0.0},
            },
            "5_interest_late_fee": {
                "interest": {"cgst": 0.0, "sgst": 0.0, "igst": 0.0, "cess": 0.0},
                "late_fee": {"cgst": 0.0, "sgst": 0.0},
            },
            "6_payment_of_tax": {
                "tax_payable": {
                    "integrated_tax": total_igst,
                    "central_tax": total_cgst,
                    "state_ut_tax": total_sgst,
                    "cess": 0.0,
                },
                "paid_through_itc": {
                    "integrated_tax": 0.0,
                    "central_tax": 0.0,
                    "state_ut_tax": 0.0,
                    "cess": 0.0,
                },
                "paid_through_cash": {
                    "integrated_tax": total_igst,
                    "central_tax": total_cgst,
                    "state_ut_tax": total_sgst,
                    "cess": 0.0,
                },
                "interest": {"igst": 0.0, "cgst": 0.0, "sgst": 0.0, "cess": 0.0},
                "late_fee": {"cgst": 0.0, "sgst": 0.0},
            },
            "total_tax_payable": total_tax,
            "filing_summary": (
                f"GSTR-3B for {period}: Total outward supply ₹{total_taxable:,.2f}. "
                f"Total GST payable: CGST ₹{total_cgst:,.2f} + SGST ₹{total_sgst:,.2f} + "
                f"IGST ₹{total_igst:,.2f} = ₹{total_tax:,.2f}"
            ),
        }
        data_store["gstr3b_data"] = gstr3b
        return json.dumps(gstr3b, indent=2, default=str)

    def validate_gstin(query: str) -> str:
        gstin = query.strip().upper()
        issues = []

        if len(gstin) != 15:
            issues.append(f"GSTIN must be 15 characters, got {len(gstin)}")
        else:
            state_code = gstin[:2]
            if state_code not in PLACE_OF_SUPPLY_CODES:
                issues.append(f"Invalid state code: {state_code}")
            else:
                issues.append(f"State: {PLACE_OF_SUPPLY_CODES[state_code]}")

            pan = gstin[2:12]
            if not (pan[:5].isalpha() and pan[5:9].isdigit() and pan[9].isalpha()):
                issues.append("Embedded PAN format invalid (should be AAAAA0000A)")

            entity_code = gstin[12]
            if not entity_code.isdigit() or entity_code == "0":
                issues.append(f"Entity code {entity_code} may be invalid (should be 1-9)")

            if gstin[13] != "Z":
                issues.append(f"14th character should be 'Z', got '{gstin[13]}'")

        return json.dumps({
            "gstin": gstin,
            "is_valid": len([i for i in issues if "Invalid" in i or "invalid" in i or "must be" in i]) == 0,
            "details": issues,
        }, indent=2)

    def compute_gst_liability_by_rate(query: str = "all") -> str:
        df = data_store.get("gst_df")
        if df is None:
            return json.dumps({"error": "No GST data loaded."})

        if "cgst_rate" not in df.columns:
            return json.dumps({"error": "GST rates not found in data."})

        df["effective_gst_rate"] = df.apply(
            lambda r: (r["cgst_rate"] + r["sgst_rate"]) if r["igst_rate"] == 0 else r["igst_rate"],
            axis=1
        )

        by_rate = {}
        for rate in sorted(df["effective_gst_rate"].unique()):
            subset = df[df["effective_gst_rate"] == rate]
            by_rate[f"{rate}%"] = {
                "invoice_count": len(subset),
                "taxable_value": float(subset["taxable_value"].sum()),
                "cgst": float(subset["cgst_amount"].sum()),
                "sgst": float(subset["sgst_amount"].sum()),
                "igst": float(subset["igst_amount"].sum()),
                "total_tax": float(subset["cgst_amount"].sum() + subset["sgst_amount"].sum() + subset["igst_amount"].sum()),
            }

        return json.dumps({
            "gst_liability_by_rate": by_rate,
            "total_tax": sum(v["total_tax"] for v in by_rate.values()),
        }, indent=2)

    return [
        StructuredTool.from_function(
            func=get_gst_summary,
            name="get_gst_summary",
            description=(
                "Get a complete summary of GST invoices including total taxable value, "
                "CGST, SGST, IGST amounts, invoice counts by type (B2B/B2C), and breakdown by GST rate."
            ),
            args_schema=GSTInput,
        ),
        StructuredTool.from_function(
            func=generate_gstr1,
            name="generate_gstr1",
            description=(
                "Generate GSTR-1 (Outward Supplies Return) data for filing. "
                "Organizes invoices into B2B, B2CS, B2CL categories, and generates HSN summary. "
                "Requires GSTIN and period (MM-YYYY)."
            ),
            args_schema=GSTINInput,
        ),
        StructuredTool.from_function(
            func=generate_gstr3b,
            name="generate_gstr3b",
            description=(
                "Generate GSTR-3B (Monthly Summary Return) data for filing. "
                "Includes outward supply summary, ITC details, and tax payment schedule. "
                "Requires GSTIN and period."
            ),
            args_schema=GSTINInput,
        ),
        StructuredTool.from_function(
            func=validate_gstin,
            name="validate_gstin",
            description="Validate a GSTIN number format, check state code, and verify embedded PAN structure.",
            args_schema=GSTInput,
        ),
        StructuredTool.from_function(
            func=compute_gst_liability_by_rate,
            name="compute_gst_liability_by_rate",
            description="Compute GST liability broken down by tax rate (0%, 5%, 12%, 18%, 28%).",
            args_schema=GSTInput,
        ),
    ]


def _compute_hsn_summary(df) -> list:
    if "hsn_code" not in df.columns:
        return []

    hsn_groups = df[df["hsn_code"].notna() & (df["hsn_code"] != "")].groupby("hsn_code").agg(
        uqc=("unit" if "unit" in df.columns else "invoice_no", "first"),
        total_quantity=("quantity" if "quantity" in df.columns else "taxable_value", "count"),
        total_value=("taxable_value", "sum"),
        total_igst=("igst_amount", "sum"),
        total_cgst=("cgst_amount", "sum"),
        total_sgst=("sgst_amount", "sum"),
    ).reset_index()

    return hsn_groups.to_dict("records")
