from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage
from langgraph.prebuilt import create_react_agent

from src.tools.form16_tools import create_form16_tools

FORM16_SYSTEM_PROMPT = """You are an expert Income Tax Consultant specializing in Indian income tax compliance,
TDS (Tax Deducted at Source), and Form 16 generation under the Income Tax Act, 1961.

Your expertise covers:
- Salary income computation under Section 17
- HRA Exemption under Section 10(13A) and Rule 2A
- Standard Deduction of ₹50,000 under Section 16(ia)
- Chapter VI-A deductions (80C, 80D, 80E, 80G, 80TTA, etc.)
- Old vs New Tax Regime comparison (Finance Act 2020, amended 2023)
- TDS computation and Form 16 generation
- Assessment Year 2025-26 (FY 2024-25) tax slabs

Tax Slabs for FY 2024-25:
OLD REGIME:
- Up to ₹2,50,000: Nil | ₹2.5L–₹5L: 5% | ₹5L–₹10L: 20% | Above ₹10L: 30%
- Rebate u/s 87A: ₹12,500 if income ≤ ₹5,00,000

NEW REGIME (default from FY 2024-25):
- Up to ₹3,00,000: Nil | ₹3L–₹7L: 5% | ₹7L–₹10L: 10%
- ₹10L–₹12L: 15% | ₹12L–₹15L: 20% | Above ₹15L: 30%
- Rebate u/s 87A: ₹25,000 if income ≤ ₹7,00,000

Surcharge: 10% for income >₹50L, 15% for >₹1Cr
Cess: 4% Health & Education Cess on total tax

When processing Form 16 requests:
1. List all employees first with `list_employees`
2. Compare tax regimes using `compare_tax_regimes` to recommend the best option
3. Compute Form 16 data with `compute_employee_tax`
4. Present a clear summary: Gross → Exemptions → Salary Income → Deductions → Net Taxable → Tax → Cess → Total"""


def create_form16_agent(api_key: str, data_store: dict):
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        openai_api_key=api_key,
        temperature=0,
        max_tokens=4096,
    )
    tools = create_form16_tools(data_store)
    return create_react_agent(llm, tools, prompt=SystemMessage(content=FORM16_SYSTEM_PROMPT))


def generate_all_form16(api_key: str, data_store: dict) -> str:
    agent = create_form16_agent(api_key, data_store)
    result = agent.invoke({
        "messages": [(
            "human",
            "Generate Form 16 for all employees. For each employee: "
            "1) List all employees, "
            "2) Compare Old vs New tax regime and recommend the better option, "
            "3) Compute Form 16 data using the recommended regime, "
            "4) Provide a summary table with each employee's name, gross salary, "
            "   net taxable income, total tax, TDS deducted, and recommended regime."
        )]
    })
    return result["messages"][-1].content
