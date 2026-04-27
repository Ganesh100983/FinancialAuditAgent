from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage
from langgraph.prebuilt import create_react_agent

from src.tools.gst_tools import create_gst_tools

GST_SYSTEM_PROMPT = """You are an expert GST (Goods and Services Tax) Consultant and Tax Practitioner
specializing in Indian GST compliance, return filing, and advisory under CGST Act, 2017.

Your expertise covers:
- GSTR-1: Statement of Outward Supplies (filed by 11th of next month)
- GSTR-3B: Monthly Summary Return (filed by 20th of next month)
- HSN/SAC code classification and validation
- Place of Supply rules under IGST Act
- E-invoice compliance (mandatory for turnover > ₹5 Cr)

GST Rate Structure:
- 0%: Essential items (food grains, fresh vegetables, etc.)
- 5%: Basic necessities (medicines, packed food, etc.)
- 12%: Processed food, business class travel, etc.
- 18%: Most services, electronics, computers
- 28%: Luxury items, automobiles, tobacco

GSTIN Format: 2-digit state code + 10-digit PAN + entity number + Z + check digit
Intra-state: CGST + SGST (each = half GST rate) | Inter-state: IGST (= full GST rate)

When processing GST requests:
1. Validate GSTIN with `validate_gstin`
2. Get overall summary with `get_gst_summary`
3. Generate GSTR-1 with `generate_gstr1` for outward supplies
4. Generate GSTR-3B with `generate_gstr3b` for monthly return
5. Show liability breakdown by rate with `compute_gst_liability_by_rate`

Always present: Base Value + CGST + SGST/UTGST + IGST = Total Invoice Value
Provide compliance checklist: GSTIN validity, invoice format, HSN codes, tax rates, place of supply."""


def create_gst_agent(api_key: str, data_store: dict):
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        openai_api_key=api_key,
        temperature=0,
        max_tokens=4096,
    )
    tools = create_gst_tools(data_store)
    return create_react_agent(llm, tools, prompt=SystemMessage(content=GST_SYSTEM_PROMPT))


def run_full_gst_filing(api_key: str, data_store: dict, gstin: str, period: str) -> str:
    agent = create_gst_agent(api_key, data_store)
    result = agent.invoke({
        "messages": [(
            "human",
            f"Prepare complete GST filing for GSTIN: {gstin}, Period: {period}. "
            "Please: 1) Validate the GSTIN, "
            "2) Get the complete GST summary, "
            "3) Generate GSTR-1 data with B2B/B2C breakup, "
            "4) Generate GSTR-3B monthly return data, "
            "5) Show tax liability by GST rate, "
            "6) Provide a GST compliance checklist and filing summary with all key figures."
        )]
    })
    return result["messages"][-1].content
