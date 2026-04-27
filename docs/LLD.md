# Low-Level Design (LLD)
## FinAudit AI — Agentic Financial Audit Platform
**Version:** 2.0 | **Date:** April 2026

---

## 1. Authentication & Session Subsystem

### 1.1 JWT Token Structure

```
Header:  { "alg": "HS256", "typ": "JWT" }
Payload: {
  "sub":        "admin",          // username
  "role":       "admin",          // admin | auditor | viewer
  "session_id": "uuid4-string",   // maps to session_store bucket
  "exp":        1234567890        // UTC epoch, 24h from login
}
Signature: HMAC-SHA256(base64(header) + "." + base64(payload), SECRET_KEY)
```

### 1.2 Login Flow

```
POST /api/v1/auth/login
  Body: application/x-www-form-urlencoded  { username, password }

authenticate_user(username, password)
  ├── Lookup username in settings.demo_users dict
  ├── Plain-text compare (bcrypt verify in production)
  └── Return { username, role } or None

If authenticated:
  session_id = uuid4()
  token = create_access_token(username, role, session_id)
  session_store.get_session(session_id)  ← creates default store bucket
  Return: { access_token, token_type, username, role, session_id }

If not authenticated:
  HTTP 401  { "detail": "Incorrect username or password" }
```

### 1.3 Request Authentication

```
Every protected endpoint has:
  user: CurrentUser = Depends(get_current_user)

get_current_user(token: str = Depends(OAuth2PasswordBearer)):
  payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
  Extracts: sub → username, role, session_id
  Returns: CurrentUser(username, role, session_id)
  On failure: HTTP 401
```

### 1.4 Session Store Operations

```python
_sessions: dict[str, dict]   # { session_id: data_store }
_lock: threading.Lock         # protects all reads/writes

get_session(session_id):
  with _lock:
    if session_id not in _sessions:
      _sessions[session_id] = _default_store()   # new user
    else:
      update _last_accessed timestamp
    return _sessions[session_id]

_default_store() keys:
  ledger_df, gst_df, employee_df      ← pandas DataFrames (None until upload)
  company_name, company_gstin, ...    ← company config from .env defaults
  openai_api_key                      ← per-session key override
  ledger_summary, anomalies, ...      ← analysis result cache (None until computed)
  form16_data: {}                     ← { employee_id: {...} } dict
  _created_at, _last_accessed         ← ISO8601 UTC timestamps

evict_expired_sessions():
  cutoff = now - session_ttl_hours (default 8h)
  Removes all sessions where _last_accessed < cutoff
  Called every 30 min by asyncio background task in lifespan()
```

---

## 2. File Upload Subsystem

### 2.1 Upload Router Logic

```
POST /api/v1/upload/{type}   (type ∈ ledger | gst | employee)

Validation:
  1. Content-Type must be text/csv or .xlsx MIME type
  2. File size ≤ 20 MB
  3. Read bytes → detect encoding via chardet if needed

Parsing (data_processor.py):
  parse_ledger(file_bytes):
    → Try read_csv / read_excel
    → Apply column alias mapping (flexible header names)
    → Normalise: lowercase column names, strip whitespace
    → Cast date, amount columns
    → Return (DataFrame, row_count)

On success:
  session_store[session_id]["ledger_df"] = df
  Clear cached results: ledger_summary = None, anomalies = None, ...
  Return: { "rows": row_count, "columns": [...], "filename": ... }

On failure:
  HTTP 422 { "detail": "Could not parse file: ..." }
```

### 2.2 Column Alias Mapping (data_processor.py)

```python
# Flexible header recognition — users can use any of these names
LEDGER_COLUMN_ALIASES = {
  "date":        ["date", "voucher_date", "txn_date", "transaction_date"],
  "voucher_no":  ["voucher_no", "voucher_number", "vch_no", "reference"],
  "narration":   ["narration", "description", "particulars", "remarks"],
  "account":     ["account", "account_name", "ledger_account", "head"],
  "debit":       ["debit", "debit_amount", "dr", "dr_amount"],
  "credit":      ["credit", "credit_amount", "cr", "cr_amount"],
}
```

---

## 3. Ledger Analysis Subsystem

### 3.1 Tool: `get_ledger_summary`

```
Input:  any string (ignored)
Output: JSON string

Logic:
  df = data_store["ledger_df"]
  total_transactions = len(df)
  total_debit        = df["debit"].sum()
  total_credit       = df["credit"].sum()

  monthly_breakdown:
    df["month"] = pd.to_datetime(df["date"]).dt.to_period("M")
    group by month → sum debit, credit per month

  category_breakdown:
    group by "account" → sum net amount per account

  anomaly_count:
    quick scan for obvious anomalies (see detect_ledger_anomalies)

  Cache result → session_store["ledger_summary"]
  Return JSON
```

### 3.2 Tool: `detect_ledger_anomalies`

```
Anomaly detection rules (applied in sequence):

1. DUPLICATE:
   mask = df.duplicated(subset=["date","amount","narration"], keep=False)

2. ROUND_NUMBER:
   mask = (df["debit"] % 100_000 == 0) & (df["debit"] > 0)
            OR same for credit
   threshold: > ₹1,00,000 round numbers flagged

3. LARGE_AMOUNT:
   threshold = mean + 3 * std_dev of all transaction amounts
   flag entries above threshold

4. MISSING_NARRATION:
   mask = df["narration"].isna() | (df["narration"].str.strip() == "")

5. WEEKEND_ENTRY:
   mask = pd.to_datetime(df["date"]).dt.dayofweek >= 5

6. NEGATIVE_BALANCE:
   mask = df["balance"] < 0  (if balance column present)

Each anomaly → { row_index, voucher_no, type, description, amount, severity }
Severity mapping: DUPLICATE→High, LARGE_AMOUNT→High, ROUND_NUMBER→Medium,
                  WEEKEND→Low, MISSING_NARRATION→Low
```

### 3.3 Tool: `generate_trial_balance`

```
Logic:
  For each unique account:
    total_debit  = df[df["account"]==acct]["debit"].sum()
    total_credit = df[df["account"]==acct]["credit"].sum()
    net_balance  = total_debit - total_credit
    balance_type = "Dr" if net_balance >= 0 else "Cr"

  Validation:
    grand_total_debit == grand_total_credit  → balanced
    If not: flag imbalance in response

  Return: List[TrialBalanceEntry]
```

### 3.4 Tool: `generate_pl_statement`

```
Account classification heuristics:
  INCOME accounts:   name contains "sales", "revenue", "income", "interest received"
  EXPENSE accounts:  name contains "expense", "cost", "salary", "rent", "depreciation"
  ASSET accounts:    name contains "cash", "bank", "receivable", "inventory", "fixed asset"
  LIABILITY accounts: name contains "payable", "loan", "creditor", "provision"

P&L:
  total_revenue   = sum of net INCOME account balances
  total_expenses  = sum of net EXPENSE account balances
  gross_profit    = total_revenue - COGS
  net_profit      = gross_profit - operating_expenses
  profit_margin   = net_profit / total_revenue
```

---

## 4. Form 16 Subsystem

### 4.1 Tax Computation Logic (FY 2024-25)

#### Old Regime Slabs
```
₹0          – ₹2,50,000  :  0%
₹2,50,001   – ₹5,00,000  :  5%
₹5,00,001   – ₹10,00,000 : 20%
₹10,00,001+ :             30%
```

#### New Regime Slabs (Default FY 2024-25)
```
₹0          – ₹3,00,000  :  0%
₹3,00,001   – ₹7,00,000  :  5%
₹7,00,001   – ₹10,00,000 : 10%
₹10,00,001  – ₹12,00,000 : 15%
₹12,00,001  – ₹15,00,000 : 20%
₹15,00,001+ :             30%
```

### 4.2 Tool: `compute_employee_tax`

```
Input: { employee_id, regime="Old", rent_paid=0, is_metro=True }

Step 1 — Salary components (from employee_df row):
  gross_salary = basic + hra + special_allowance + other_allowances

Step 2 — Exemptions (Old regime only):
  HRA Exemption = min(
    hra_received,
    rent_paid - 0.1 * basic_salary,       # actual rent - 10% of basic
    0.5 * basic_salary if metro else 0.4   # 50%/40% of basic
  )
  Standard Deduction = ₹50,000 (both regimes)

Step 3 — Deductions u/s Chapter VI-A (Old regime only):
  80C  = min(investments_80c, 150_000)
  80D  = min(health_premium, 25_000)   # 50_000 if senior citizen
  80E  = education_loan_interest
  80G  = donations (as per limits)

Step 4 — Taxable Income:
  Old:  gross - hra_exemption - std_deduction - 80C - 80D - 80E
  New:  gross - std_deduction  (no other deductions)

Step 5 — Tax Computation:
  Apply slab rates → base_tax
  Surcharge:
    10%  if taxable_income > ₹50L  but ≤ ₹1Cr
    15%  if taxable_income > ₹1Cr  but ≤ ₹2Cr
    25%  if taxable_income > ₹2Cr  but ≤ ₹5Cr
    37%  if taxable_income > ₹5Cr
  Cess: 4% of (tax + surcharge)

Step 6 — Rebate u/s 87A:
  Old:  If taxable ≤ ₹5L  → rebate = min(tax, ₹12,500)
  New:  If taxable ≤ ₹7L  → rebate = min(tax, ₹25,000)

Step 7 — Final:
  total_tax_payable = tax + surcharge + cess - rebate_87a
  tax_payable_or_refund = total_tax_payable - tds_already_deducted

Store result:
  session_store["form16_data"][employee_id] = {
    "part_a": Form16PartA(...),
    "part_b": Form16PartB(...),
    "employee_id": employee_id,
    "generated_on": today_date
  }
```

### 4.3 Tool: `compare_tax_regimes`

```
Run compute_employee_tax twice (regime="Old" and regime="New")
Compare total_tax_payable between both
Return:
  {
    old_regime:    { ...tax breakdown... },
    new_regime:    { ...tax breakdown... },
    recommended:   "old" | "new",
    tax_savings:   abs(old_total - new_total),
    recommendation: "Switch to New Regime to save ₹X,XXX"
  }
```

### 4.4 Form 16 PDF Generation (ReportLab)

```
generate_form16_pdf(form16: Form16Data) → bytes

Structure:
  Page 1 — Part A (Employer/Employee details, TDS quarters summary)
    Header: Form 16 Certificate under Section 203
    Table:  Quarter | TDS Deducted | TDS Deposited | Challan No.
    Footer: Employer signature block

  Page 2 — Part B (Salary breakdown, deductions, tax computation)
    Section 1: Gross Salary Components (Basic, HRA, Allowances)
    Section 2: Exemptions (HRA u/s 10(13A), Std Deduction)
    Section 3: Chapter VI-A Deductions (80C, 80D, 80E, 80G)
    Section 4: Tax Computation (Slab-wise, Surcharge, Cess, 87A)
    Section 5: TDS reconciliation

Styles:
  _header_style(size, bold, color, align)
  _table_style(has_header=True)
  Amount formatting: Indian notation (₹ X,XX,XXX.XX)
```

---

## 5. GST Subsystem

### 5.1 Tool: `generate_gstr1`

```
Input: { gstin, period }  e.g. period = "2024-07"

Filter df: invoice_date month == period

Classify invoices:
  B2B:  buyer_gstin is not null and len == 15
  B2CL: buyer_gstin is null AND invoice_value > ₹2,50,000 (inter-state)
  B2CS: buyer_gstin is null AND invoice_value ≤ ₹2,50,000 (or intra-state)

Build GSTR1Summary:
  b2b:  Group by buyer_gstin → List[GSTR1B2BEntry]
        Each entry: gstin, party_name, invoices[], totals
  b2cs: Group by (tax_rate, place_of_supply) → aggregate
  b2cl: Each invoice as individual entry

HSN Summary:
  Group by hsn_code → { hsn, description, qty, taxable_value, tax }

Return GSTR1Summary as JSON
```

### 5.2 Tool: `generate_gstr3b`

```
Input: { gstin, period }

3.1 Outward Supplies:
  total_taxable_value = df[period].taxable_value.sum()
  integrated_tax      = df[df.supply_type == "inter-state"].igst.sum()
  central_tax         = df[df.supply_type == "intra-state"].cgst.sum()
  state_ut_tax        = df[df.supply_type == "intra-state"].sgst.sum()

4. ITC Available:
  Assumes no ITC (outward-only model)
  Production: parse purchase register / GSTR-2B

6. Tax Payable:
  cgst = total cgst from outward
  sgst = total sgst from outward
  igst = total igst from outward
  net_payable = cgst + sgst + igst - itc_available

Return GSTR3BSummary as JSON
```

### 5.3 Tool: `validate_gstin`

```
GSTIN format: 29AAAAA0000A1Z5  (15 chars)
Regex: ^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$

Fields decoded:
  State Code:  digits[0:2] → state name lookup (28 states + UTs)
  PAN:         chars[2:12]
  Entity Type: char[12]  (1=Individual, 2=HUF, ... 7=LLP, etc.)
  Check Digit: char[14]  (validated via checksum algorithm)

Return: { valid, state_code, state_name, pan_number, entity_type, error? }
```

### 5.4 Tool: `compute_gst_liability_by_rate`

```
Group df by tax_rate (0%, 5%, 12%, 18%, 28%):
  For each rate:
    invoice_count  = count
    taxable_value  = sum(taxable_value)
    cgst           = sum(cgst_amount)
    sgst           = sum(sgst_amount)
    igst           = sum(igst_amount)
    tax_amount     = cgst + sgst + igst

Return: { breakdown: [...], grand_total_tax, grand_total_taxable }
```

---

## 6. AI Assistant Subsystem

### 6.1 Agent Instantiation

```python
create_ledger_agent(api_key, data_store):
  llm = ChatOpenAI(
    model       = "gpt-4o-mini",
    openai_api_key = api_key,
    temperature = 0,           # deterministic output
    max_tokens  = 4096,
  )
  tools = create_ledger_tools(data_store)  # closure over session data
  agent = create_react_agent(
    llm,
    tools,
    prompt = SystemMessage(content = LEDGER_SYSTEM_PROMPT)
  )
  return agent
```

Three agent types — same pattern:

| Agent | System Prompt Persona | Tools |
|---|---|---|
| `ledger_agent` | CA / Financial Auditor (Ind AS) | get_ledger_summary, detect_anomalies, trial_balance, pl_statement, top_transactions |
| `form16_agent` | Tax Expert (IT Act 1961) | list_employees, compute_employee_tax, compare_tax_regimes |
| `gst_agent` | GST Practitioner (CGST Act) | get_gst_summary, generate_gstr1, generate_gstr3b, validate_gstin, liability_by_rate |

### 6.2 SSE Streaming Pipeline

```
Client                          FastAPI                     LangGraph / OpenAI
  │                                │                               │
  │ POST /chat/stream              │                               │
  │ { message, agent_type }        │                               │
  ├───────────────────────────────►│                               │
  │                                │ _build_agent(type,key,store)  │
  │                                │ agent.astream_events(v2)      │
  │                                ├──────────────────────────────►│
  │                                │                         tool_start event
  │ data: {"type":"tool_start"}    │◄──────────────────────────────┤
  │◄───────────────────────────────┤                               │
  │                                │                         on_chat_model_stream
  │ data: {"type":"token","content":"₹"}                           │
  │◄───────────────────────────────┤◄──────────────────────────────┤
  │ data: {"type":"token","content":"1"}                           │
  │◄───────────────────────────────┤                         (repeats per token)
  │          ...                   │                               │
  │ data: {"type":"tool_end"}      │◄──────────────────────────────┤
  │◄───────────────────────────────┤                               │
  │ data: {"type":"done"}          │                               │
  │◄───────────────────────────────┤                               │

SSE Event Types:
  token      → { type: "token",      content: "..." }    — append to output
  tool_start → { type: "tool_start", tool: "fn_name" }   — show spinner badge
  tool_end   → { type: "tool_end",   tool: "fn_name" }   — show ✓ badge
  error      → { type: "error",      content: "msg" }    — show error banner
  done       → { type: "done" }                          — setStreaming(false)
```

### 6.3 useSSE Hook State Machine

```
States: idle → streaming → (done | error)

stream(url, body):
  abortRef.current?.abort()           // cancel any in-flight request
  setOutput(''); setToolCalls([]); setError(null); setStreaming(true)
  fetch(url, { method: POST, body, signal: controller.signal })

  while reader.read():
    buf += decode(chunk)
    lines = buf.split('\n')
    buf = lines.pop()                 // keep partial line in buffer
    for line in lines:
      if not line.startswith('data: '): continue
      evt = JSON.parse(line[6:])
      switch evt.type:
        token:      setOutput(prev => prev + evt.content)
        tool_start: setToolCalls(prev => [...prev, { name, status:'running' }])
        tool_end:   setToolCalls(prev => map status 'running'→'done')
        error:      setError(evt.content)
        done:       setStreaming(false)

cancel():
  abortRef.current.abort()
  setStreaming(false)
```

---

## 7. Frontend State Management

### 7.1 Zustand Store (`useAppStore`)

```
Persisted to localStorage (key: 'fa-store'):
  token:    string | null       — JWT access token
  user:     { username, role }  — from /auth/me
  darkMode: boolean

Session-only (cleared on page refresh):
  uploads:  {
    ledger:   { status: 'ok'|'error', filename, rows } | null
    gst:      same
    employee: same
  }
  settings: {
    company_name, company_gstin, financial_year, openai_key_set
  }

Actions:
  setAuth(token, user)  → saves token to localStorage + state
  clearAuth()           → removes from localStorage + state
  setUpload(type, info) → patch uploads[type]
  toggleDark()          → flip darkMode, toggle .dark class on <html>
  setSettings(patch)    → shallow merge into settings
```

### 7.2 Route & Auth Guard

```
App.jsx:
  ProtectedRoute:
    token = useAppStore(s => s.token)
    return token ? <Outlet /> : <Navigate to="/login" />

Routes:
  /login        → Login (public)
  /             → ProtectedRoute → Layout
    /dashboard  → Dashboard
    /ledger     → LedgerScreener
    /form16     → Form16Generator
    /gst        → GSTFiling
    /assistant  → AIAssistant
    /settings   → Settings
  /*            → Navigate to /dashboard
```

---

## 8. API Contract

### 8.1 Auth

```
POST /api/v1/auth/login
  Body: form-urlencoded { username, password }
  200:  { access_token, token_type, username, role, session_id }
  401:  { detail: "Incorrect username or password" }

GET  /api/v1/auth/me
  Header: Authorization: Bearer <token>
  200:  { username, role, session_id }

POST /api/v1/auth/logout
  200:  { message: "Logged out" }
```

### 8.2 Upload

```
POST /api/v1/upload/ledger    (multipart, field: "file")
POST /api/v1/upload/gst
POST /api/v1/upload/employee
  200: { rows, columns, filename, message }
  400: { detail: "Unsupported file type" }
  413: { detail: "File too large (max 20 MB)" }
  422: { detail: "Could not parse file: ..." }

GET  /api/v1/upload/status
  200: { ledger: { status, rows, filename }, gst: {...}, employee: {...} }
```

### 8.3 Ledger

```
GET /api/v1/ledger/summary
  200: { total_transactions, total_debit, total_credit,
         monthly_breakdown:[{month,total_debit,total_credit}],
         anomaly_count, category_breakdown:{...} }

GET /api/v1/ledger/anomalies
  200: { anomalies:[{date,voucher_no,description,amount,type,reason,severity}],
         total_count, severity_summary:{High,Medium,Low} }

GET /api/v1/ledger/trial-balance
  200: { entries:[{account,debit_total,credit_total,net_balance,balance_type}],
         is_balanced, total_debit, total_credit }

GET /api/v1/ledger/pl-statement
  200: { total_revenue, total_expenses, gross_profit, operating_expenses,
         net_profit, profit_margin }

GET /api/v1/ledger/top-transactions?n=10
  200: [ { date, narration, amount, type, account } ]

GET /api/v1/ledger/preview?page=1&page_size=50
  200: { rows:[...], total, page, page_size }

GET /api/v1/ledger/report/pdf
  200: application/pdf  (Form 16-style audit report)
```

### 8.4 Form 16

```
GET  /api/v1/form16/employees
  200: { employees:[{employee_id, name, designation, basic_salary,
                     gross_salary, tds_deducted, pan}] }

POST /api/v1/form16/compute
  Body: { employee_id, regime="Old", rent_paid=0, is_metro=true }
  200: { old_regime:{...}, new_regime:{...} }
  422: { detail: "Employee not found" }

POST /api/v1/form16/compare-regimes
  Body: { employee_id, ... }
  200: { old_regime:{...}, new_regime:{...},
         recommended:"old"|"new", tax_savings, recommendation }

GET  /api/v1/form16/download/{employee_id}
  200: application/pdf  (Form 16 Part A + Part B)
  404: { detail: "Form 16 not generated for employee '...'" }

GET  /api/v1/form16/summary
  200: { total_employees, total_gross_salary, total_tds_deducted,
         average_salary, employees:[...] }
```

### 8.5 GST

```
GET  /api/v1/gst/summary
  200: { total_invoices, total_taxable_value, total_tax_liability,
         total_invoice_value, b2b_count, b2cs_count, b2cl_count }

POST /api/v1/gst/gstr1
  Body: { gstin, period }  e.g. { "period": "2024-07" }
  200: GSTR1Summary JSON

POST /api/v1/gst/gstr3b
  Body: { gstin, period }
  200: GSTR3BSummary JSON

GET  /api/v1/gst/validate-gstin?gstin=29AAAAA0000A1Z5
  200: { valid, state_code, state_name, pan_number, entity_type, error? }

GET  /api/v1/gst/liability-by-rate
  200: { breakdown:[{tax_rate,invoice_count,taxable_value,cgst,sgst,igst,
                     tax_amount}], grand_total_tax, grand_total_taxable }

GET  /api/v1/gst/preview?page=1&page_size=50
  200: { rows:[...], total, page, page_size }

GET  /api/v1/gst/download/gstr1       → application/json
GET  /api/v1/gst/download/gstr3b      → application/json
GET  /api/v1/gst/download/gstr1/pdf   → application/pdf
```

### 8.6 Chat

```
POST /api/v1/chat/stream
  Rate: 10/minute per IP
  Body: { message: str, agent_type: "ledger"|"form16"|"gst" }
  200:  text/event-stream
        data: {"type":"tool_start","tool":"fn_name"}\n\n
        data: {"type":"token","content":"..."}\n\n
        data: {"type":"tool_end","tool":"fn_name"}\n\n
        data: {"type":"error","content":"..."}\n\n
        data: {"type":"done"}\n\n
  400:  { detail: "OpenAI API key not configured in Settings." }

GET /api/v1/chat/settings
  200: { openai_api_key_set, company_name, company_gstin,
         company_tan, company_pan, financial_year }

PUT /api/v1/chat/settings
  Body: { openai_api_key?, company_name?, company_gstin?,
          company_tan?, company_pan?, financial_year? }
  200: { message: "Settings updated successfully" }
```

---

## 9. Pydantic Domain Models

```
LedgerEntry        date, voucher_no, narration, account, debit, credit, balance
Anomaly            row_index, voucher_no, anomaly_type(Enum), description, amount, severity
TrialBalanceEntry  account, total_debit, total_credit, closing_balance, balance_type
FinancialSummary   totals, anomalies[], trial_balance[], category_breakdown{}

Form16PartA        employer details, employee details, TDS quarters[]
Form16PartB        salary components, exemptions, deductions, tax computation
Form16Data         part_a, part_b, employee_id, generated_on

GSTInvoice         invoice fields, cgst/sgst/igst rates+amounts, invoice_type(Enum)
GSTR1B2BEntry      gstin, invoices[], totals
GSTR1Summary       b2b[], b2cs[], b2cl[], exports[], hsn_summary[], totals
GSTR3BOutwardSupplies  taxable_value, integrated_tax, central_tax, state_ut_tax
GSTR3BSummary      outward_supplies, itc, tax_payable, tax_paid

AnomalyType (Enum)      DUPLICATE | ROUND_NUMBER | LARGE_AMOUNT | MISSING_NARRATION
                        SEQUENCE_BREAK | NEGATIVE_BALANCE | WEEKEND_ENTRY
TransactionType (Enum)  INCOME | EXPENSE | ASSET | LIABILITY | EQUITY | CONTRA
GSTInvoiceType (Enum)   B2B | B2CS | B2CL | EXPORT | NIL
```

---

## 10. Error Handling Matrix

| Scenario | HTTP Code | Response |
|---|---|---|
| Invalid / expired JWT | 401 | `{ detail: "Invalid or expired token" }` |
| Insufficient role | 403 | `{ detail: "Insufficient permissions" }` |
| Data not uploaded | 400 | `{ detail: "No ledger uploaded. Please upload first." }` |
| Employee not found | 422 | `{ detail: "Employee EMP001 not found" }` |
| No OpenAI key | 400 | `{ detail: "OpenAI API key not configured in Settings." }` |
| File too large | 413 | `{ detail: "File too large (max 20 MB)" }` |
| Unsupported file type | 400 | `{ detail: "Unsupported file type. Please upload CSV or XLSX." }` |
| Rate limit exceeded | 429 | `{ detail: "Rate limit exceeded" }` |
| Unhandled exception | 500 | `{ detail: "An internal server error occurred." }` |
| Agent streaming error | SSE `error` event | `data: {"type":"error","content":"..."}` |
| Form 16 not computed | 404 | `{ detail: "Form 16 not generated for employee '...'. Run compute first." }` |
