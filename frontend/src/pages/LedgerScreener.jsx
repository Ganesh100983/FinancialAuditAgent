import { useState, useEffect, useCallback } from 'react'
import { BookOpen, Download, RefreshCw, AlertTriangle, TrendingUp, FileBarChart } from 'lucide-react'
import { uploadApi, ledgerApi } from '../api/client'
import FileUpload from '../components/ui/FileUpload'
import MetricCard from '../components/ui/MetricCard'
import DataTable from '../components/ui/DataTable'
import Badge from '../components/ui/Badge'
import useAppStore from '../store/useAppStore'
import toast from 'react-hot-toast'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  LineChart, Line, CartesianGrid, Legend,
} from 'recharts'

const fmtINR = n => n == null ? '—' : `₹${Number(n).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`
const TABS = ['Overview', 'Anomalies', 'Trial Balance', 'P&L Statement', 'Raw Data']

export default function LedgerScreener() {
  const [tab,    setTab]    = useState('Overview')
  const [data,   setData]   = useState({})
  const [loading,setLoading]= useState({})
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
    if (uploads.ledger?.status !== 'ok') return
    load('summary',      ledgerApi.summary)
    load('anomalies',    ledgerApi.anomalies)
    load('trialBalance', ledgerApi.trialBalance)
    load('pl',           ledgerApi.plStatement)
  }, [uploads.ledger, load])

  async function handleUpload(file) {
    try {
      const res = await uploadApi.ledger(file)
      setUpload('ledger', { status: 'ok', filename: file.name, rows: res.data.rows })
      toast.success(`Loaded ${res.data.rows} ledger entries`)
      load('summary',      ledgerApi.summary)
      load('anomalies',    ledgerApi.anomalies)
      load('trialBalance', ledgerApi.trialBalance)
      load('pl',           ledgerApi.plStatement)
    } catch (e) {
      setUpload('ledger', { status: 'error', message: e.response?.data?.detail ?? e.message })
      throw e
    }
  }

  const summary = data.summary ?? {}
  const anomalies = data.anomalies?.anomalies ?? []
  const tb = data.trialBalance?.entries ?? []
  const pl = data.pl ?? {}

  const monthlyChart = summary.monthly_breakdown?.map(m => ({
    month:  m.month?.slice(0, 7) ?? m.month,
    debit:  Math.abs(m.total_debit  ?? 0),
    credit: Math.abs(m.total_credit ?? 0),
  })) ?? []

  const anomalyCols = [
    { key: 'date',        label: 'Date' },
    { key: 'description', label: 'Description' },
    { key: 'amount',      label: 'Amount', align: 'right', render: v => fmtINR(v) },
    { key: 'type',        label: 'Type', render: v => (
      <Badge variant={v === 'credit' ? 'green' : 'red'}>{v}</Badge>
    )},
    { key: 'reason',      label: 'Reason', render: v => (
      <span className="text-xs text-yellow-700 dark:text-yellow-400">{v}</span>
    )},
  ]

  const tbCols = [
    { key: 'account',       label: 'Account' },
    { key: 'debit_total',   label: 'Debit',  align: 'right', render: v => fmtINR(v) },
    { key: 'credit_total',  label: 'Credit', align: 'right', render: v => fmtINR(v) },
    { key: 'net_balance',   label: 'Balance',align: 'right', render: v => (
      <span className={Number(v) >= 0 ? 'text-green-600' : 'text-red-600'}>{fmtINR(v)}</span>
    )},
  ]

  return (
    <div className="space-y-5 max-w-7xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-blue-600" /> Ledger Screener
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">Anomaly detection, trial balance & P&amp;L</p>
        </div>
        {uploads.ledger?.status === 'ok' && (
          <button
            onClick={() => ledgerApi.downloadReport().catch(e => toast.error(e.message))}
            className="btn-secondary text-xs"
          >
            <Download className="w-3.5 h-3.5" /> Download PDF
          </button>
        )}
      </div>

      {/* Upload */}
      <div className="card p-5">
        <FileUpload
          label="Ledger File (CSV / XLSX)"
          onUpload={handleUpload}
          status={uploads.ledger}
          sampleUrl="/api/v1/upload/sample/ledger"
        />
      </div>

      {uploads.ledger?.status !== 'ok' && (
        <div className="text-center py-16 text-sm text-gray-400 dark:text-gray-500">
          Upload a ledger file to start analysis
        </div>
      )}

      {uploads.ledger?.status === 'ok' && (
        <>
          {/* Metric cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard title="Transactions"  value={summary.total_transactions?.toLocaleString()} loading={loading.summary} color="blue" />
            <MetricCard title="Total Credit"  value={fmtINR(summary.total_credit)}  loading={loading.summary} color="green" />
            <MetricCard title="Total Debit"   value={fmtINR(summary.total_debit)}   loading={loading.summary} color="red" />
            <MetricCard title="Anomalies"
              value={anomalies.length}
              icon={anomalies.length > 0 ? AlertTriangle : undefined}
              color={anomalies.length > 0 ? 'yellow' : 'green'}
              loading={loading.anomalies}
            />
          </div>

          {/* Tabs */}
          <div className="border-b border-gray-200 dark:border-gray-800 flex gap-6 overflow-x-auto">
            {TABS.map(t => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`pb-3 text-sm whitespace-nowrap ${tab === t ? 'tab-active' : 'tab-inactive'}`}
              >
                {t}
              </button>
            ))}
          </div>

          {/* Tab content */}
          {tab === 'Overview' && (
            <div className="card p-5">
              <h2 className="section-title">Monthly Debit vs Credit</h2>
              {monthlyChart.length > 0 ? (
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={monthlyChart} barGap={4}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} tickFormatter={v => `₹${(v/1e5).toFixed(0)}L`} />
                    <Tooltip formatter={v => fmtINR(v)} />
                    <Legend />
                    <Bar dataKey="credit" name="Credit" fill="#22c55e" radius={[3,3,0,0]} />
                    <Bar dataKey="debit"  name="Debit"  fill="#ef4444" radius={[3,3,0,0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-40 flex items-center justify-center text-sm text-gray-400">No monthly data</div>
              )}
            </div>
          )}

          {tab === 'Anomalies' && (
            <div className="card p-5">
              <h2 className="section-title flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-yellow-500" />
                Anomalies Detected ({anomalies.length})
              </h2>
              <DataTable
                columns={anomalyCols}
                data={anomalies}
                loading={loading.anomalies}
                emptyText="No anomalies detected — ledger looks clean!"
              />
            </div>
          )}

          {tab === 'Trial Balance' && (
            <div className="card p-5">
              <h2 className="section-title">Trial Balance</h2>
              <DataTable columns={tbCols} data={tb} loading={loading.trialBalance} />
            </div>
          )}

          {tab === 'P&L Statement' && (
            <div className="card p-5 space-y-4">
              <h2 className="section-title">Profit &amp; Loss Statement</h2>
              {loading.pl ? (
                <div className="animate-pulse space-y-2">
                  {[...Array(6)].map((_,i) => <div key={i} className="h-4 bg-gray-200 dark:bg-gray-700 rounded" />)}
                </div>
              ) : (
                <div className="space-y-3">
                  <PLRow label="Total Revenue"       value={pl.total_revenue}       color="green" bold />
                  <PLRow label="Total Expenses"      value={pl.total_expenses}      color="red"  />
                  <PLRow label="Gross Profit"        value={pl.gross_profit}        color={pl.gross_profit >= 0 ? 'green' : 'red'} />
                  <PLRow label="Operating Expenses"  value={pl.operating_expenses}  color="red" />
                  <div className="border-t border-gray-200 dark:border-gray-700 pt-3">
                    <PLRow label="Net Profit / Loss" value={pl.net_profit}          color={pl.net_profit >= 0 ? 'green' : 'red'} bold />
                  </div>
                  {pl.profit_margin != null && (
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      Profit Margin: <strong>{(pl.profit_margin * 100).toFixed(1)}%</strong>
                    </p>
                  )}
                </div>
              )}
            </div>
          )}

          {tab === 'Raw Data' && <RawLedgerTable />}
        </>
      )}
    </div>
  )
}

function PLRow({ label, value, color, bold }) {
  const cls = color === 'green' ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
  return (
    <div className="flex justify-between items-center py-1">
      <span className={`text-sm ${bold ? 'font-semibold text-gray-900 dark:text-white' : 'text-gray-600 dark:text-gray-400'}`}>{label}</span>
      <span className={`text-sm font-medium ${cls}`}>
        {value != null ? `₹${Number(value).toLocaleString('en-IN', { maximumFractionDigits: 0 })}` : '—'}
      </span>
    </div>
  )
}

function RawLedgerTable() {
  const [rows,    setRows]    = useState([])
  const [page,    setPage]    = useState(1)
  const [total,   setTotal]   = useState(0)
  const [loading, setLoading] = useState(false)
  const PS = 50

  useEffect(() => {
    setLoading(true)
    ledgerApi.preview(page, PS)
      .then(r => { setRows(r.data.data); setTotal(r.data.total) })
      .finally(() => setLoading(false))
  }, [page])

  const cols = rows[0]
    ? Object.keys(rows[0]).map(k => ({ key: k, label: k.replace(/_/g,' ').toUpperCase() }))
    : []

  return (
    <div className="card p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="section-title mb-0">Raw Ledger Data ({total.toLocaleString()} rows)</h2>
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <button disabled={page === 1} onClick={() => setPage(p=>p-1)} className="px-2 py-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-30">‹</button>
          <span>Page {page} / {Math.ceil(total/PS) || 1}</span>
          <button disabled={page >= Math.ceil(total/PS)} onClick={() => setPage(p=>p+1)} className="px-2 py-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-30">›</button>
        </div>
      </div>
      <DataTable columns={cols} data={rows} loading={loading} pageSize={PS} />
    </div>
  )
}
