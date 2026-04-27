import axios from 'axios'
import toast from 'react-hot-toast'

const BASE = '/api/v1'

const api = axios.create({ baseURL: BASE })

export async function downloadBlob(url, filename) {
  const token = localStorage.getItem('fa_token')
  const res = await fetch(url, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Download failed' }))
    throw new Error(err.detail || 'Download failed')
  }
  const blob = await res.blob()
  const blobUrl = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = blobUrl
  a.download = filename
  a.click()
  URL.revokeObjectURL(blobUrl)
}

// Attach JWT on every request
api.interceptors.request.use(cfg => {
  const token = localStorage.getItem('fa_token')
  if (token) cfg.headers.Authorization = `Bearer ${token}`
  return cfg
})

// Global error handling
api.interceptors.response.use(
  res => res,
  err => {
    const msg = err.response?.data?.detail || err.message || 'Request failed'
    if (err.response?.status === 401) {
      localStorage.removeItem('fa_token')
      window.location.href = '/login'
    } else if (err.response?.status !== 400) {
      toast.error(msg)
    }
    return Promise.reject(err)
  }
)

// ── Auth ──────────────────────────────────────────────────────────────────────
export const authApi = {
  login: (username, password) => {
    const form = new URLSearchParams({ username, password })
    return api.post('/auth/login', form, { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } })
  },
  logout:  ()  => api.post('/auth/logout'),
  me:      ()  => api.get('/auth/me'),
}

// ── Upload ────────────────────────────────────────────────────────────────────
export const uploadApi = {
  ledger:   file => { const fd = new FormData(); fd.append('file', file); return api.post('/upload/ledger', fd) },
  gst:      file => { const fd = new FormData(); fd.append('file', file); return api.post('/upload/gst', fd) },
  employee: file => { const fd = new FormData(); fd.append('file', file); return api.post('/upload/employee', fd) },
  status:   ()   => api.get('/upload/status'),
}

// ── Ledger ────────────────────────────────────────────────────────────────────
export const ledgerApi = {
  summary:        ()    => api.get('/ledger/summary'),
  anomalies:      ()    => api.get('/ledger/anomalies'),
  trialBalance:   ()    => api.get('/ledger/trial-balance'),
  plStatement:    ()    => api.get('/ledger/pl-statement'),
  topTransactions:(n=10)=> api.get(`/ledger/top-transactions?n=${n}`),
  preview:        (p,ps)=> api.get(`/ledger/preview?page=${p}&page_size=${ps}`),
  downloadReport: ()    => downloadBlob(`${BASE}/ledger/report/pdf`, 'ledger_report.pdf'),
}

// ── Form 16 ───────────────────────────────────────────────────────────────────
export const form16Api = {
  employees:     ()    => api.get('/form16/employees'),
  compute:       body  => api.post('/form16/compute', body),
  compareRegimes:body  => api.post('/form16/compare-regimes', body),
  summary:       ()    => api.get('/form16/summary'),
  download:      (empId, empName) => downloadBlob(`${BASE}/form16/download/${empId}`, `Form16_${empName || empId}.pdf`),
}

// ── GST ───────────────────────────────────────────────────────────────────────
export const gstApi = {
  summary:       ()    => api.get('/gst/summary'),
  gstr1:         body  => api.post('/gst/gstr1', body),
  gstr3b:        body  => api.post('/gst/gstr3b', body),
  validateGstin: gstin => api.get(`/gst/validate-gstin?gstin=${gstin}`),
  liabilityByRate:()   => api.get('/gst/liability-by-rate'),
  preview:       (p,ps)=> api.get(`/gst/preview?page=${p}&page_size=${ps}`),
  downloadGstr1Json: () => downloadBlob(`${BASE}/gst/download/gstr1`,     'gstr1.json'),
  downloadGstr3bJson:() => downloadBlob(`${BASE}/gst/download/gstr3b`,    'gstr3b.json'),
  downloadGstr1Pdf:  () => downloadBlob(`${BASE}/gst/download/gstr1/pdf`, 'gstr1_report.pdf'),
}

// ── Companies ─────────────────────────────────────────────────────────────────
export const companiesApi = {
  list:   ()          => api.get('/companies'),
  add:    body        => api.post('/companies', body),
  update: (id, body)  => api.put(`/companies/${id}`, body),
  remove: id          => api.delete(`/companies/${id}`),
  select: id          => api.post(`/companies/${id}/select`),
}

// ── Chat / Settings ───────────────────────────────────────────────────────────
export const chatApi = {
  streamUrl:      ()    => `${BASE}/chat/stream`,
  getSettings:    ()    => api.get('/chat/settings'),
  updateSettings: body  => api.put('/chat/settings', body),
}

export default api
