import { useState, useEffect, useCallback } from 'react'
import { Receipt, Download, RefreshCw, CheckCircle, AlertCircle } from 'lucide-react'
import { uploadApi, gstApi } from '../api/client'
import FileUpload from '../components/ui/FileUpload'
import MetricCard from '../components/ui/MetricCard'
import DataTable from '../components/ui/DataTable'
import Badge from '../components/ui/Badge'
import useAppStore from '../store/useAppStore'
import toast from 'react-hot-toast'
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
} from 'recharts'

const fmtINR = n => n == null ? '—' : `₹${Number(n).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`
const TABS = ['Summary', 'GSTR-1', 'GSTR-3B', 'Liability by Rate', 'Raw Data']
const PIE_COLORS = ['#6366f1', '#22c55e', '#f59e0b', '#ef4444', '#14b8a6']

export default function GSTFiling() {
  const [tab,    setTab]    = useState('Summary')
  const [data,   setData]   = useState({})
  const [loading,setLoading]= useState({})
  const [period, setPeriod] = useState(new Date().toISOString().slice(0, 7))
  const [gstin,  setGstin]  = useState('')
  const [filingGstin, setFilingGstin] = useState('')
  const [gstinResult, setGstinResult] = useState(null)
  const { uploads, setUpload } = useAppStore()

  const load = useCallback(async (key, fn) => {
    setLoading(l => ({ ...l, [key]: true }))
    try {
      const res = await fn()
      setData(d => ({ ...d, [key]: res.data }))
    } catch { /* handled globally */ }
    finally { setLoading(l => ({ ...l, [key]: false })) }
  }, [])

  useEffect(() => {
    if (uploads.gst?.status !== 'ok') return
    load('summary', gstApi.summary)
    load('liability', gstApi.liabilityByRate)
  }, [uploads.gst, load])

  async function handleUpload(file) {
    try {
      const res = await uploadApi.gst(file)
      setUpload('gst', { status: 'ok', filename: file.name, rows: res.data.rows })
      toast.success(`Loaded ${res.data.rows} GST invoices`)
      load('summary', gstApi.summary)
      load('liability', gstApi.liabilityByRate)
    } catch (e) {
      setUpload('gst', { status: 'error', message: e.response?.data?.detail ?? e.message })
      throw e
    }
  }

  const fmtPeriod = p => p ? `${p.slice(5, 7)}-${p.slice(0, 4)}` : ''

  async function generateGSTR1() {
    setLoading(l => ({ ...l, gstr1: true }))
    try {
      const res = await gstApi.gstr1({ gstin: filingGstin, period: fmtPeriod(period) })
      setData(d => ({ ...d, gstr1: res.data }))
      toast.success('GSTR-1 generated')
    } catch (e) {
      toast.error(e.response?.data?.detail ?? 'Failed to generate GSTR-1')
    } finally { setLoading(l => ({ ...l, gstr1: false })) }
  }

  async function generateGSTR3B() {
    setLoading(l => ({ ...l, gstr3b: true }))
    try {
      const res = await gstApi.gstr3b({ gstin: filingGstin, period: fmtPeriod(period) })
      setData(d => ({ ...d, gstr3b: res.data }))
      toast.success('GSTR-3B generated')
    } catch (e) {
      toast.error(e.response?.data?.detail ?? 'Failed to generate GSTR-3B')
    } finally { setLoading(l => ({ ...l, gstr3b: false })) }
  }

  async function validateGstin() {
    if (!gstin) { toast.error('Enter GSTIN'); return }
    try {
      const res = await gstApi.validateGstin(gstin)
      setGstinResult(res.data)
    } catch (e) {
      toast.error(e.response?.data?.detail ?? 'Validation failed')
    }
  }

  const summary = data.summary ?? {}
  const liability = data.liability?.breakdown ?? []
  const pieData = liability.map(r => ({ name: `${r.tax_rate}%`, value: r.tax_amount }))

  const gstr1Cols = [
    { key: 'invoice_number', label: 'Invoice No.' },
    { key: 'invoice_date',   label: 'Date' },
    { key: 'buyer_name',     label: 'Buyer' },
    { key: 'buyer_gstin',    label: 'GSTIN' },
    { key: 'taxable_value',  label: 'Taxable',  align: 'right', render: v => fmtINR(v) },
    { key: 'cgst',           label: 'CGST',     align: 'right', render: v => fmtINR(v) },
    { key: 'sgst',           label: 'SGST',     align: 'right', render: v => fmtINR(v) },
    { key: 'igst',           label: 'IGST',     align: 'right', render: v => fmtINR(v) },
    { key: 'total_invoice_value', label: 'Total', align: 'right', render: v => fmtINR(v) },
    { key: 'supply_type',    label: 'Type', render: v => <Badge variant="blue">{v}</Badge> },
  ]

  return (
    <div className="space-y-5 max-w-7xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
            <Receipt className="w-5 h-5 text-purple-600" /> GST Filing
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">GSTR-1, GSTR-3B and GST liability analysis</p>
        </div>

        {uploads.gst?.status === 'ok' && (
          <div className="flex gap-2">
            <button onClick={() => gstApi.downloadGstr1Pdf().catch(e => toast.error(e.message))} className="btn-secondary text-xs">
              <Download className="w-3.5 h-3.5" /> GSTR-1 PDF
            </button>
            <button onClick={() => gstApi.downloadGstr1Json().catch(e => toast.error(e.message))} className="btn-secondary text-xs">
              <Download className="w-3.5 h-3.5" /> GSTR-1 JSON
            </button>
          </div>
        )}
      </div>

      <div className="card p-5">
        <FileUpload
          label="GST Invoices (CSV / XLSX)"
          onUpload={handleUpload}
          status={uploads.gst}
          sampleUrl="/api/v1/upload/sample/gst"
        />
      </div>

      {uploads.gst?.status !== 'ok' && (
        <div className="text-center py-16 text-sm text-gray-400">
          Upload GST invoice data to start analysis
        </div>
      )}

      {uploads.gst?.status === 'ok' && (
        <>
          {/* Metrics */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard title="Total Invoices"    value={summary.total_invoices?.toLocaleString()}  loading={loading.summary} color="blue" />
            <MetricCard title="Taxable Value"     value={fmtINR(summary.total_taxable_value)}       loading={loading.summary} color="green" />
            <MetricCard title="Total Tax"         value={fmtINR(summary.total_tax_liability)}       loading={loading.summary} color="purple" />
            <MetricCard title="Invoice Value"     value={fmtINR(summary.total_invoice_value)}       loading={loading.summary} color="brand" />
          </div>

          {/* Tabs */}
          <div className="border-b border-gray-200 dark:border-gray-800 flex gap-6 overflow-x-auto">
            {TABS.map(t => (
              <button key={t} onClick={() => setTab(t)}
                className={`pb-3 text-sm whitespace-nowrap ${tab === t ? 'tab-active' : 'tab-inactive'}`}>
                {t}
              </button>
            ))}
          </div>

          {/* Summary tab */}
          {tab === 'Summary' && (
            <div className="grid lg:grid-cols-2 gap-5">
              <div className="card p-5">
                <h2 className="section-title">Tax Breakdown by Rate</h2>
                {pieData.length > 0 ? (
                  <ResponsiveContainer width="100%" height={220}>
                    <PieChart>
                      <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={e => `${e.name}: ${fmtINR(e.value)}`}>
                        {pieData.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                      </Pie>
                      <Tooltip formatter={v => fmtINR(v)} />
                      <Legend />
                    </PieChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-40 flex items-center justify-center text-sm text-gray-400">No data</div>
                )}
              </div>

              <div className="card p-5 space-y-3">
                <h2 className="section-title">GSTIN Validator</h2>
                <div className="flex gap-2">
                  <input
                    className="input flex-1"
                    placeholder="Enter GSTIN (e.g. 29AAAAA0000A1Z5)"
                    value={gstin}
                    onChange={e => setGstin(e.target.value.toUpperCase())}
                    maxLength={15}
                  />
                  <button onClick={validateGstin} className="btn-primary shrink-0">Validate</button>
                </div>
                {gstinResult && (
                  <div className={`p-3 rounded-lg text-sm ${gstinResult.valid ? 'bg-green-50 dark:bg-green-900/20' : 'bg-red-50 dark:bg-red-900/20'}`}>
                    <div className="flex items-center gap-2 font-medium mb-1">
                      {gstinResult.valid
                        ? <><CheckCircle className="w-4 h-4 text-green-600" /><span className="text-green-700 dark:text-green-400">Valid GSTIN</span></>
                        : <><AlertCircle className="w-4 h-4 text-red-600" /><span className="text-red-700 dark:text-red-400">Invalid GSTIN</span></>
                      }
                    </div>
                    {gstinResult.state_code    && <p className="text-gray-600 dark:text-gray-400">State Code: <strong>{gstinResult.state_code}</strong></p>}
                    {gstinResult.pan_number    && <p className="text-gray-600 dark:text-gray-400">PAN: <strong>{gstinResult.pan_number}</strong></p>}
                    {gstinResult.entity_type   && <p className="text-gray-600 dark:text-gray-400">Entity: <strong>{gstinResult.entity_type}</strong></p>}
                    {gstinResult.error         && <p className="text-red-600 dark:text-red-400">{gstinResult.error}</p>}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* GSTR-1 tab */}
          {tab === 'GSTR-1' && (
            <div className="card p-5 space-y-4">
              <div className="flex flex-wrap items-center gap-3">
                <h2 className="section-title mb-0">GSTR-1</h2>
                <input
                  className="input w-44 text-sm"
                  placeholder="Your GSTIN (optional)"
                  value={filingGstin}
                  onChange={e => setFilingGstin(e.target.value.toUpperCase())}
                  maxLength={15}
                />
                <input type="month" value={period} onChange={e => setPeriod(e.target.value)}
                  className="input w-40 text-sm" />
                <button onClick={generateGSTR1} disabled={loading.gstr1} className="btn-primary">
                  {loading.gstr1 ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Receipt className="w-3.5 h-3.5" />}
                  Generate
                </button>
                {data.gstr1 && (
                  <button onClick={() => gstApi.downloadGstr1Json().catch(e => toast.error(e.message))} className="btn-secondary text-xs">
                    <Download className="w-3.5 h-3.5" /> JSON
                  </button>
                )}
              </div>

              {data.gstr1 && (
                <>
                  <div className="grid grid-cols-3 gap-3">
                    <InfoBox label="B2B Invoices"  value={data.gstr1.b2b?.length ?? 0} />
                    <InfoBox label="B2CS Invoices" value={data.gstr1.b2cs?.length ?? 0} />
                    <InfoBox label="B2CL Invoices" value={data.gstr1.b2cl?.length ?? 0} />
                  </div>
                  <DataTable
                    columns={gstr1Cols}
                    data={[...(data.gstr1.b2b??[]), ...(data.gstr1.b2cs??[]), ...(data.gstr1.b2cl??[])]}
                    pageSize={10}
                    emptyText="No invoice data for this period"
                  />
                </>
              )}
            </div>
          )}

          {/* GSTR-3B tab */}
          {tab === 'GSTR-3B' && (
            <div className="card p-5 space-y-4">
              <div className="flex flex-wrap items-center gap-3">
                <h2 className="section-title mb-0">GSTR-3B</h2>
                <input
                  className="input w-44 text-sm"
                  placeholder="Your GSTIN (optional)"
                  value={filingGstin}
                  onChange={e => setFilingGstin(e.target.value.toUpperCase())}
                  maxLength={15}
                />
                <input type="month" value={period} onChange={e => setPeriod(e.target.value)}
                  className="input w-40 text-sm" />
                <button onClick={generateGSTR3B} disabled={loading.gstr3b} className="btn-primary">
                  {loading.gstr3b ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Receipt className="w-3.5 h-3.5" />}
                  Generate
                </button>
              </div>

              {data.gstr3b && (
                <div className="grid lg:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">3.1 Details of outward supplies</h3>
                    {[
                      ['Total Taxable Value',  data.gstr3b.outward_taxable_supplies?.total_taxable_value],
                      ['Integrated Tax',       data.gstr3b.outward_taxable_supplies?.integrated_tax],
                      ['Central Tax',          data.gstr3b.outward_taxable_supplies?.central_tax],
                      ['State/UT Tax',         data.gstr3b.outward_taxable_supplies?.state_ut_tax],
                      ['Total Tax',            data.gstr3b.outward_taxable_supplies?.total_tax],
                    ].map(([lbl, val]) => (
                      <div key={lbl} className="flex justify-between text-sm py-0.5 border-b border-gray-50 dark:border-gray-800">
                        <span className="text-gray-600 dark:text-gray-400">{lbl}</span>
                        <span className="font-medium text-gray-800 dark:text-gray-200">{fmtINR(val)}</span>
                      </div>
                    ))}
                  </div>
                  <div className="space-y-2">
                    <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">Tax Summary</h3>
                    {[
                      ['Total CGST', data.gstr3b.tax_liability?.cgst],
                      ['Total SGST', data.gstr3b.tax_liability?.sgst],
                      ['Total IGST', data.gstr3b.tax_liability?.igst],
                      ['Net Tax Payable', data.gstr3b.tax_liability?.net_payable],
                    ].map(([lbl, val]) => (
                      <div key={lbl} className="flex justify-between text-sm py-0.5 border-b border-gray-50 dark:border-gray-800">
                        <span className="text-gray-600 dark:text-gray-400">{lbl}</span>
                        <span className={`font-medium ${lbl.includes('Net') ? 'text-red-600 dark:text-red-400' : 'text-gray-800 dark:text-gray-200'}`}>
                          {fmtINR(val)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Liability by rate */}
          {tab === 'Liability by Rate' && (
            <div className="card p-5">
              <h2 className="section-title">GST Liability by Tax Rate</h2>
              {liability.length > 0 ? (
                <>
                  <ResponsiveContainer width="100%" height={220}>
                    <BarChart data={liability}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                      <XAxis dataKey="tax_rate" tickFormatter={v => `${v}%`} tick={{ fontSize: 11 }} />
                      <YAxis tick={{ fontSize: 11 }} tickFormatter={v => `₹${(v/1e5).toFixed(0)}L`} />
                      <Tooltip formatter={v => fmtINR(v)} />
                      <Bar dataKey="tax_amount" name="Tax Amount" fill="#6366f1" radius={[3,3,0,0]} />
                    </BarChart>
                  </ResponsiveContainer>
                  <DataTable
                    columns={[
                      { key: 'tax_rate',      label: 'Rate %', render: v => `${v}%` },
                      { key: 'invoice_count', label: 'Invoices', align: 'right' },
                      { key: 'taxable_value', label: 'Taxable',  align: 'right', render: v => fmtINR(v) },
                      { key: 'cgst',          label: 'CGST',     align: 'right', render: v => fmtINR(v) },
                      { key: 'sgst',          label: 'SGST',     align: 'right', render: v => fmtINR(v) },
                      { key: 'igst',          label: 'IGST',     align: 'right', render: v => fmtINR(v) },
                      { key: 'tax_amount',    label: 'Total Tax',align: 'right', render: v => fmtINR(v) },
                    ]}
                    data={liability}
                    loading={loading.liability}
                  />
                </>
              ) : (
                <div className="h-40 flex items-center justify-center text-sm text-gray-400">
                  {loading.liability ? 'Loading…' : 'No liability data'}
                </div>
              )}
            </div>
          )}

          {/* Raw data */}
          {tab === 'Raw Data' && <RawGSTTable />}
        </>
      )}
    </div>
  )
}

function InfoBox({ label, value }) {
  return (
    <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-3 text-center">
      <p className="text-2xl font-bold text-gray-900 dark:text-white">{value}</p>
      <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{label}</p>
    </div>
  )
}

function RawGSTTable() {
  const [rows, setRows]     = useState([])
  const [page, setPage]     = useState(1)
  const [total, setTotal]   = useState(0)
  const [loading, setLoading] = useState(false)
  const PS = 50

  useEffect(() => {
    setLoading(true)
    gstApi.preview(page, PS)
      .then(r => { setRows(r.data.data); setTotal(r.data.total) })
      .finally(() => setLoading(false))
  }, [page])

  const cols = rows[0]
    ? Object.keys(rows[0]).map(k => ({ key: k, label: k.replace(/_/g,' ').toUpperCase() }))
    : []

  return (
    <div className="card p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="section-title mb-0">Raw GST Data ({total.toLocaleString()} rows)</h2>
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <button disabled={page===1} onClick={() => setPage(p=>p-1)} className="px-2 py-1 rounded hover:bg-gray-100 disabled:opacity-30">‹</button>
          <span>Page {page} / {Math.ceil(total/PS)||1}</span>
          <button disabled={page>=Math.ceil(total/PS)} onClick={() => setPage(p=>p+1)} className="px-2 py-1 rounded hover:bg-gray-100 disabled:opacity-30">›</button>
        </div>
      </div>
      <DataTable columns={cols} data={rows} loading={loading} pageSize={PS} />
    </div>
  )
}
