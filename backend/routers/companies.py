import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from backend.auth import get_current_user, CurrentUser
from backend.session_store import get_session

router = APIRouter(prefix="/companies", tags=["Companies"])


class CompanyData(BaseModel):
    name: str
    gstin: str = ""
    tan: str = ""
    pan: str = ""
    address: str = ""
    financial_year: str = "2024-25"


def _sync_active(store: dict, company: dict) -> None:
    """Copy selected company fields into top-level session keys used by tools and PDF generators."""
    store["company_name"]    = company["name"]
    store["company_gstin"]   = company.get("gstin", "")
    store["company_tan"]     = company.get("tan", "")
    store["company_pan"]     = company.get("pan", "")
    store["company_address"] = company.get("address", "")
    store["financial_year"]  = company.get("financial_year", "2024-25")


def _clear_session_data(store: dict) -> None:
    """Wipe uploaded data and all cached analysis results when switching companies."""
    store["ledger_df"]       = None
    store["gst_df"]          = None
    store["employee_df"]     = None
    store["ledger_summary"]  = None
    store["anomalies"]       = None
    store["trial_balance"]   = None
    store["pl_statement"]    = None
    store["gst_summary_data"]= None
    store["gstr1_data"]      = None
    store["gstr3b_data"]     = None
    store["form16_data"]     = {}


@router.get("")
async def list_companies(user: CurrentUser = Depends(get_current_user)):
    store = get_session(user.session_id)
    return {
        "companies": store.get("companies", []),
        "active_company_id": store.get("active_company_id"),
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def add_company(data: CompanyData, user: CurrentUser = Depends(get_current_user)):
    store = get_session(user.session_id)
    company = {"id": str(uuid.uuid4()), **data.model_dump()}
    store.setdefault("companies", []).append(company)
    return company


@router.put("/{company_id}")
async def update_company(
    company_id: str, data: CompanyData, user: CurrentUser = Depends(get_current_user)
):
    store = get_session(user.session_id)
    companies = store.get("companies", [])
    for i, c in enumerate(companies):
        if c["id"] == company_id:
            companies[i] = {"id": company_id, **data.model_dump()}
            if store.get("active_company_id") == company_id:
                _sync_active(store, companies[i])
            return companies[i]
    raise HTTPException(status.HTTP_404_NOT_FOUND, "Company not found")


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company(company_id: str, user: CurrentUser = Depends(get_current_user)):
    store = get_session(user.session_id)
    companies = store.get("companies", [])
    new_list = [c for c in companies if c["id"] != company_id]
    if len(new_list) == len(companies):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Company not found")
    if len(new_list) == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot delete the last company")
    store["companies"] = new_list
    if store.get("active_company_id") == company_id:
        store["active_company_id"] = new_list[0]["id"]
        _sync_active(store, new_list[0])


@router.post("/{company_id}/select")
async def select_company(company_id: str, user: CurrentUser = Depends(get_current_user)):
    store = get_session(user.session_id)
    for c in store.get("companies", []):
        if c["id"] == company_id:
            if store.get("active_company_id") != company_id:
                _clear_session_data(store)
            store["active_company_id"] = company_id
            _sync_active(store, c)
            return {"message": "Company selected", "company": c}
    raise HTTPException(status.HTTP_404_NOT_FOUND, "Company not found")
