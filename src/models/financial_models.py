from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum


class TransactionType(str, Enum):
    INCOME = "Income"
    EXPENSE = "Expense"
    ASSET = "Asset"
    LIABILITY = "Liability"
    EQUITY = "Equity"
    CONTRA = "Contra"


class AnomalyType(str, Enum):
    DUPLICATE = "Duplicate Entry"
    ROUND_NUMBER = "Suspicious Round Number"
    LARGE_AMOUNT = "Unusually Large Amount"
    MISSING_NARRATION = "Missing Narration"
    SEQUENCE_BREAK = "Voucher Sequence Break"
    NEGATIVE_BALANCE = "Negative Balance"
    WEEKEND_ENTRY = "Weekend Entry"


class LedgerEntry(BaseModel):
    date: str
    voucher_no: str
    narration: str
    account: str
    debit: float = 0.0
    credit: float = 0.0
    balance: float = 0.0


class Anomaly(BaseModel):
    row_index: int
    voucher_no: str
    anomaly_type: AnomalyType
    description: str
    amount: float = 0.0
    severity: str = "Medium"  # Low, Medium, High


class TrialBalanceEntry(BaseModel):
    account: str
    total_debit: float
    total_credit: float
    closing_balance: float
    balance_type: str  # Dr / Cr


class FinancialSummary(BaseModel):
    total_income: float = 0.0
    total_expenses: float = 0.0
    gross_profit: float = 0.0
    net_profit: float = 0.0
    total_assets: float = 0.0
    total_liabilities: float = 0.0
    total_equity: float = 0.0
    total_transactions: int = 0
    anomalies_found: int = 0
    anomalies: List[Anomaly] = Field(default_factory=list)
    trial_balance: List[TrialBalanceEntry] = Field(default_factory=list)
    category_breakdown: Dict[str, float] = Field(default_factory=dict)


class TaxSlab(BaseModel):
    min_income: float
    max_income: float
    rate: float
    description: str


class Form16PartA(BaseModel):
    employer_name: str = ""
    employer_address: str = ""
    employer_tan: str = ""
    employer_pan: str = ""
    employee_name: str = ""
    employee_pan: str = ""
    employee_designation: str = ""
    financial_year: str = "2024-25"
    assessment_year: str = "2025-26"
    period_from: str = "01-Apr-2024"
    period_to: str = "31-Mar-2025"
    total_tds_deducted: float = 0.0
    total_tds_deposited: float = 0.0
    quarters: List[Dict[str, Any]] = Field(default_factory=list)


class Form16PartB(BaseModel):
    gross_salary: float = 0.0
    basic_salary: float = 0.0
    hra_received: float = 0.0
    special_allowance: float = 0.0
    lta: float = 0.0
    medical_allowance: float = 0.0
    other_allowances: float = 0.0
    hra_exemption: float = 0.0
    lta_exemption: float = 0.0
    standard_deduction: float = 50000.0
    professional_tax: float = 0.0
    entertainment_allowance: float = 0.0
    income_from_salary: float = 0.0
    section_80c: float = 0.0
    section_80ccc: float = 0.0
    section_80ccd: float = 0.0
    section_80d: float = 0.0
    section_80e: float = 0.0
    section_80g: float = 0.0
    section_80tta: float = 0.0
    total_deductions: float = 0.0
    net_taxable_income: float = 0.0
    tax_on_income: float = 0.0
    surcharge: float = 0.0
    health_education_cess: float = 0.0
    total_tax_liability: float = 0.0
    relief_u87a: float = 0.0
    tds_deducted: float = 0.0
    tax_payable_or_refund: float = 0.0
    regime: str = "Old"  # Old or New


class Form16Data(BaseModel):
    part_a: Form16PartA = Field(default_factory=Form16PartA)
    part_b: Form16PartB = Field(default_factory=Form16PartB)
    employee_id: str = ""
    generated_on: str = ""


class GSTInvoiceType(str, Enum):
    B2B = "B2B"
    B2CS = "B2CS"
    B2CL = "B2CL"
    EXPORT = "EXP"
    NIL = "NIL"


class GSTInvoice(BaseModel):
    invoice_no: str
    invoice_date: str
    party_gstin: str = ""
    party_name: str = ""
    place_of_supply: str = ""
    hsn_code: str = ""
    description: str = ""
    quantity: float = 1.0
    unit: str = "NOS"
    taxable_value: float = 0.0
    cgst_rate: float = 0.0
    sgst_rate: float = 0.0
    igst_rate: float = 0.0
    cgst_amount: float = 0.0
    sgst_amount: float = 0.0
    igst_amount: float = 0.0
    cess_amount: float = 0.0
    total_amount: float = 0.0
    invoice_type: GSTInvoiceType = GSTInvoiceType.B2B
    is_reverse_charge: bool = False


class GSTR1B2BEntry(BaseModel):
    gstin: str
    party_name: str
    invoices: List[Dict[str, Any]] = Field(default_factory=list)
    total_taxable_value: float = 0.0
    total_igst: float = 0.0
    total_cgst: float = 0.0
    total_sgst: float = 0.0
    total_cess: float = 0.0


class GSTR1Summary(BaseModel):
    gstin: str = ""
    trade_name: str = ""
    financial_year: str = "2024-25"
    period: str = ""
    b2b: List[GSTR1B2BEntry] = Field(default_factory=list)
    b2cs: List[Dict[str, Any]] = Field(default_factory=list)
    b2cl: List[Dict[str, Any]] = Field(default_factory=list)
    exports: List[Dict[str, Any]] = Field(default_factory=list)
    nil_rated: Dict[str, float] = Field(default_factory=dict)
    hsn_summary: List[Dict[str, Any]] = Field(default_factory=list)
    total_taxable_value: float = 0.0
    total_cgst: float = 0.0
    total_sgst: float = 0.0
    total_igst: float = 0.0
    total_cess: float = 0.0
    total_tax: float = 0.0
    invoice_count: int = 0


class GSTR3BOutwardSupplies(BaseModel):
    total_taxable_value: float = 0.0
    integrated_tax: float = 0.0
    central_tax: float = 0.0
    state_ut_tax: float = 0.0
    cess: float = 0.0


class GSTR3BSummary(BaseModel):
    gstin: str = ""
    trade_name: str = ""
    period: str = ""
    taxable_outward_supplies: GSTR3BOutwardSupplies = Field(
        default_factory=GSTR3BOutwardSupplies
    )
    zero_rated_supplies: GSTR3BOutwardSupplies = Field(
        default_factory=GSTR3BOutwardSupplies
    )
    nil_exempt_non_gst: GSTR3BOutwardSupplies = Field(
        default_factory=GSTR3BOutwardSupplies
    )
    inward_supplies_reverse_charge: float = 0.0
    itc_available: Dict[str, float] = Field(default_factory=dict)
    itc_reversed: Dict[str, float] = Field(default_factory=dict)
    net_itc: Dict[str, float] = Field(default_factory=dict)
    interest_late_fee: Dict[str, float] = Field(default_factory=dict)
    tax_payable: Dict[str, float] = Field(default_factory=dict)
    tax_paid: Dict[str, float] = Field(default_factory=dict)
