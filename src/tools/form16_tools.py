import json
from datetime import datetime
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from src.models.financial_models import Form16Data, Form16PartA, Form16PartB


def _compute_hra_exemption(basic: float, hra_received: float, rent_paid: float, is_metro: bool) -> float:
    """HRA exemption is the least of three conditions u/s 10(13A)."""
    if rent_paid == 0:
        return 0.0
    metro_pct = 0.50 if is_metro else 0.40
    condition1 = hra_received
    condition2 = metro_pct * basic
    condition3 = max(0, rent_paid - 0.10 * basic)
    return min(condition1, condition2, condition3)


def _compute_tax_old_regime(taxable_income: float) -> float:
    """Compute income tax under Old Tax Regime (FY 2024-25)."""
    tax = 0.0
    slabs = [
        (250000, 0.00),
        (500000, 0.05),
        (1000000, 0.20),
        (float("inf"), 0.30),
    ]
    prev = 0
    for limit, rate in slabs:
        if taxable_income <= prev:
            break
        taxable = min(taxable_income, limit) - prev
        tax += taxable * rate
        prev = limit

    if taxable_income <= 500000:
        tax = max(0, tax - 12500)
    return tax


def _compute_tax_new_regime(taxable_income: float) -> float:
    """Compute income tax under New Tax Regime (FY 2024-25)."""
    tax = 0.0
    slabs = [
        (300000, 0.00),
        (700000, 0.05),
        (1000000, 0.10),
        (1200000, 0.15),
        (1500000, 0.20),
        (float("inf"), 0.30),
    ]
    prev = 0
    for limit, rate in slabs:
        if taxable_income <= prev:
            break
        taxable = min(taxable_income, limit) - prev
        tax += taxable * rate
        prev = limit

    if taxable_income <= 700000:
        tax = max(0, tax - 25000)
    return tax


def _compute_surcharge(income: float, tax: float) -> float:
    if income <= 5000000:
        return 0.0
    elif income <= 10000000:
        return tax * 0.10
    elif income <= 20000000:
        return tax * 0.15
    elif income <= 50000000:
        return tax * 0.25
    else:
        return tax * 0.37


def create_form16_tools(data_store: dict) -> list:

    class Form16Input(BaseModel):
        query: str = Field(default="all", description="Employee ID or 'all' for all employees")

    class TaxCalcInput(BaseModel):
        employee_id: str = Field(description="Employee ID to compute tax for")
        regime: str = Field(default="Old", description="Tax regime: 'Old' or 'New'")
        rent_paid: float = Field(default=0.0, description="Annual rent paid for HRA calculation")
        is_metro: bool = Field(default=True, description="Is the employee in a metro city?")

    def compute_employee_tax(employee_id: str, regime: str = "Old",
                              rent_paid: float = 0.0, is_metro: bool = True) -> str:
        df = data_store.get("employee_df")
        if df is None:
            return json.dumps({"error": "No employee data loaded. Please upload employee data first."})

        emp_rows = df[df["employee_id"].astype(str) == str(employee_id)]
        if emp_rows.empty:
            emp_rows = df[df["name"].str.contains(employee_id, case=False, na=False)]
        if emp_rows.empty:
            return json.dumps({"error": f"Employee '{employee_id}' not found."})

        row = emp_rows.iloc[0]

        basic = float(row.get("basic_salary", 0))
        hra_received = float(row.get("hra", 0))
        special = float(row.get("special_allowance", 0))
        lta = float(row.get("lta", 0))
        medical = float(row.get("medical_allowance", 0))
        other = float(row.get("other_allowances", 0)) if "other_allowances" in row.index else 0.0
        prof_tax = float(row.get("professional_tax", 0))
        tds = float(row.get("tds_deducted", 0))
        s80c = min(float(row.get("section_80c", 0)), 150000)
        s80d = min(float(row.get("section_80d", 0)), 25000)
        s80ccc = float(row.get("section_80ccc", 0)) if "section_80ccc" in row.index else 0.0
        s80ccd = float(row.get("section_80ccd", 0)) if "section_80ccd" in row.index else 0.0
        s80e = float(row.get("section_80e", 0)) if "section_80e" in row.index else 0.0
        s80g = float(row.get("section_80g", 0)) if "section_80g" in row.index else 0.0

        gross = basic + hra_received + special + lta + medical + other
        hra_exemption = _compute_hra_exemption(basic, hra_received, rent_paid, is_metro)
        lta_exemption = min(lta, lta)
        std_deduction = 50000.0
        income_from_salary = gross - hra_exemption - lta_exemption - std_deduction - prof_tax

        if regime == "New":
            total_deductions = 0.0
            net_taxable = income_from_salary
        else:
            s80c_total = min(s80c + s80ccc + s80ccd, 150000)
            total_deductions = s80c_total + s80d + s80e + s80g
            net_taxable = max(0, income_from_salary - total_deductions)

        if regime == "New":
            base_tax = _compute_tax_new_regime(net_taxable)
        else:
            base_tax = _compute_tax_old_regime(net_taxable)

        surcharge = _compute_surcharge(net_taxable, base_tax)
        cess = (base_tax + surcharge) * 0.04
        total_tax = base_tax + surcharge + cess

        relief_87a = 0.0
        if regime == "Old" and net_taxable <= 500000:
            relief_87a = min(base_tax, 12500)
        elif regime == "New" and net_taxable <= 700000:
            relief_87a = min(base_tax, 25000)
        total_tax = max(0, total_tax - relief_87a)

        tax_payable = total_tax - tds

        part_a = Form16PartA(
            employer_name=data_store.get("company_name", "ABC Pvt Ltd"),
            employer_tan=data_store.get("company_tan", "MUMA00000A"),
            employer_pan=data_store.get("company_pan", "AABCA0000A"),
            employer_address=data_store.get("company_address", "Mumbai, Maharashtra"),
            employee_name=str(row.get("name", "")),
            employee_pan=str(row.get("pan", "XXXXX0000X")),
            employee_designation=str(row.get("designation", "Employee")),
            financial_year=data_store.get("financial_year", "2024-25"),
            assessment_year="2025-26",
            period_from="01-Apr-2024",
            period_to="31-Mar-2025",
            total_tds_deducted=tds,
            total_tds_deposited=tds,
        )

        part_b = Form16PartB(
            gross_salary=gross,
            basic_salary=basic,
            hra_received=hra_received,
            special_allowance=special,
            lta=lta,
            medical_allowance=medical,
            other_allowances=other,
            hra_exemption=hra_exemption,
            lta_exemption=lta_exemption,
            standard_deduction=std_deduction,
            professional_tax=prof_tax,
            income_from_salary=income_from_salary,
            section_80c=s80c,
            section_80ccc=s80ccc,
            section_80ccd=s80ccd,
            section_80d=s80d,
            section_80e=s80e,
            section_80g=s80g,
            total_deductions=total_deductions,
            net_taxable_income=net_taxable,
            tax_on_income=base_tax,
            surcharge=surcharge,
            health_education_cess=cess,
            total_tax_liability=total_tax,
            relief_u87a=relief_87a,
            tds_deducted=tds,
            tax_payable_or_refund=tax_payable,
            regime=regime,
        )

        form16 = Form16Data(
            part_a=part_a,
            part_b=part_b,
            employee_id=str(row.get("employee_id", employee_id)),
            generated_on=datetime.now().strftime("%d-%m-%Y"),
        )

        if not isinstance(data_store.get("form16_data"), dict):
            data_store["form16_data"] = {}
        data_store["form16_data"][employee_id] = form16.model_dump()

        return json.dumps({
            "employee_id": employee_id,
            "employee_name": part_a.employee_name,
            "gross_salary": gross,
            "hra_exemption": hra_exemption,
            "standard_deduction": std_deduction,
            "section_80c": s80c if regime == "Old" else 0.0,
            "section_80d": s80d if regime == "Old" else 0.0,
            "net_taxable_income": net_taxable,
            "total_deductions": total_deductions,
            "income_tax": base_tax,
            "surcharge": surcharge,
            "cess": cess,
            "rebate_87a": relief_87a,
            "total_tax_liability": total_tax,
            "tds_deducted": tds,
            "tax_payable": tax_payable,
            "regime": regime,
            "status": "Form 16 data computed and ready to generate.",
        }, indent=2)

    def list_employees(query: str = "all") -> str:
        df = data_store.get("employee_df")
        if df is None:
            return json.dumps({"error": "No employee data loaded."})

        employees = []
        for _, row in df.iterrows():
            gross = sum([
                float(row.get("basic_salary", 0)),
                float(row.get("hra", 0)),
                float(row.get("special_allowance", 0)),
                float(row.get("lta", 0)),
                float(row.get("medical_allowance", 0)),
            ])
            employees.append({
                "employee_id": str(row.get("employee_id", "")),
                "name": str(row.get("name", "")),
                "pan": str(row.get("pan", "")),
                "designation": str(row.get("designation", "")),
                "gross_salary": gross,
                "tds_deducted": float(row.get("tds_deducted", 0)),
            })

        return json.dumps({
            "total_employees": len(employees),
            "employees": employees,
        }, indent=2)

    def compare_tax_regimes(employee_id: str, regime: str = "both", rent_paid: float = 0.0, is_metro: bool = True) -> str:
        old_result = json.loads(compute_employee_tax(employee_id, "Old", rent_paid, is_metro))
        new_result = json.loads(compute_employee_tax(employee_id, "New", rent_paid, is_metro))

        if "error" in old_result:
            return json.dumps(old_result)

        old_tax = old_result.get("total_tax_liability", 0)
        new_tax = new_result.get("total_tax_liability", 0)
        saving = old_tax - new_tax
        recommended = "New Regime" if new_tax < old_tax else "Old Regime"

        return json.dumps({
            "employee_id": employee_id,
            "employee_name": old_result.get("employee_name", ""),
            "old_regime": {
                "taxable_income": old_result.get("net_taxable_income", 0),
                "total_deductions": old_result.get("total_deductions", 0),
                "tax_liability": old_tax,
                "tax_payable": old_result.get("tax_payable", 0),
            },
            "new_regime": {
                "taxable_income": new_result.get("net_taxable_income", 0),
                "total_deductions": 0,
                "tax_liability": new_tax,
                "tax_payable": new_result.get("tax_payable", 0),
            },
            "tax_saving_old_vs_new": saving,
            "recommended_regime": recommended,
            "recommendation_reason": (
                f"{recommended} saves ₹{abs(saving):,.2f} in taxes for this employee."
            ),
        }, indent=2)

    return [
        StructuredTool.from_function(
            func=list_employees,
            name="list_employees",
            description="List all employees with their salary details and TDS deducted. Use this to see available employees before generating Form 16.",
            args_schema=Form16Input,
        ),
        StructuredTool.from_function(
            func=compute_employee_tax,
            name="compute_employee_tax",
            description=(
                "Compute complete Form 16 data for a specific employee. "
                "Calculates HRA exemption, standard deduction, Chapter VI-A deductions, "
                "income tax under selected regime, surcharge, cess, and tax payable/refundable. "
                "Stores the Form 16 data for PDF generation."
            ),
            args_schema=TaxCalcInput,
        ),
        StructuredTool.from_function(
            func=compare_tax_regimes,
            name="compare_tax_regimes",
            description=(
                "Compare Old vs New tax regime for an employee and recommend the better option. "
                "Calculates tax under both regimes and shows potential savings."
            ),
            args_schema=TaxCalcInput,
        ),
    ]
