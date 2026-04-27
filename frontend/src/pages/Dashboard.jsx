import { useEffect, useState } from 'react'
import { BookOpen, FileText, Receipt, AlertTriangle, TrendingUp, Bot, Building2 } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { uploadApi, ledgerApi, gstApi, form16Api } from '../api/client'
import MetricCard from '../components/ui/MetricCard'
import useAppStore from '../store/useAppStore'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import toast from 'react-hot-toast'

const fmtINR = n => n == null ? '—' : `₹${Number(n).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`

export default function Dashboard() {
  const [status,  setStatus]  = useState(null)
  const [summary, setSummary] = useState(null)
  const [gst,     setGst]     = useState(null)
  const [f16,     setF16]     = useState(null)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()
  const user = useAppStore(s => s.user)
  const activeCompany = useAppStore(s => s.activeCompany)

  useEffect(() => {
    async function load() {
      setLoading(true)
      try {
        const [st, sum, gs, f] = await Promise.allSettled([
          uploadApi.status(),
          ledgerApi.summary(),
          gstApi.summary(),
          form16Api.summary(),
        ])
        if (st.status === 'fulfilled')  setStatus(st.value.data)
        if (sum.status === 'fulfilled') setSummary(sum.value.data)
        if (gs.status === 'fulfilled')  setGst(gs.value.data)
        if (f.status === 'fulfilled')   setF16(f.value.data)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const chartData = summary?.monthly_breakdown?.map(m => ({
    month: m.month?.slice(0, 7) ?? m.month,
    debit:  Math.abs(m.total_debit  ?? 0),
    credit: Math.abs(m.total_credit ?? 0),
  })) ?? []

  const QUICK = [
    { label: 'Ledger Screener', icon: BookOpen,  to: '/ledger',    color: 'text-blue-600',   bg: 'bg-blue-50 dark:bg-blue-900/20',   desc: 'Anomaly detection & P&L' },
    { label: 'Form 16',         icon: FileText,   to: '/form16',    color: 'text-green-600',  bg: 'bg-green-50 dark:bg-green-900/20', desc: 'TDS certificate generation' },
    { label: 'GST Filing',      icon: Receipt,    to: '/gst',       color: 'text-purple-600', bg: 'bg-purple-50 dark:bg-purple-900/20', desc: 'GSTR-1 & GSTR-3B' },
    { label: 'AI Assistant',    icon: Bot,        to: '/assistant', color: 'text-brand-600',  bg: 'bg-brand-50 dark:bg-brand-900/20', desc: 'Ask anything about your data' },
  ]

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Welcome */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900 dark:text-white">
            Good {greeting()}, {user?.username ?? 'User'} 👋
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
            Here's your financial audit overview
          </p>
        </div>
        {activeCompany && (
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-brand-50 dark:bg-brand-900/20 border border-brand-100 dark:border-brand-800">
            <Building2 className="w-4 h-4 text-brand-600 dark:text-brand-400 shrink-0" />
            <div className="text-right">
              <p className="text-sm font-semibold text-brand-700 dark:text-brand-300 leading-tight">{activeCompany.name}</p>
              {activeCompany.gstin && <p className="text-xs text-brand-500 dark:text-brand-500 font-mono">{activeCompany.gstin}</p>}
            </div>
          </div>
        )}
      </div>

      {/* Upload status banner */}
      {status && !allUploaded(status) && (
        <div className="flex items-start gap-3 p-4 rounded-xl bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800">
          <AlertTriangle className="w-5 h-5 text-yellow-600 dark:text-yellow-400 shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-yellow-800 dark:text-yellow-300">Data not uploaded yet</p>
            <p className="text-xs text-yellow-600 dark:text-yellow-400 mt-0.5">
              Upload ledger, GST, and employee files to unlock all features. Go to any module to upload.
            </p>
          </div>
        </div>
      )}

      {/* Metric cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Total Revenue"
          value={fmtINR(summary?.total_credit)}
          sub={`${summary?.total_transactions ?? '—'} transactions`}
          icon={TrendingUp}
          color="green"
          loading={loading}
        />
        <MetricCard
          title="Total Expenses"
          value={fmtINR(summary?.total_debit)}
          sub="Debit entries"
          icon={BookOpen}
          color="red"
          loading={loading}
        />
        <MetricCard
          title="GST Liability"
          value={fmtINR(gst?.total_tax_liability)}
          sub={`${gst?.total_invoices ?? '—'} invoices`}
          icon={Receipt}
          color="purple"
          loading={loading}
        />
        <MetricCard
          title="Employees (TDS)"
          value={f16?.total_employees ?? '—'}
          sub={`Total TDS: ${fmtINR(f16?.total_tds_deducted)}`}
          icon={FileText}
          color="blue"
          loading={loading}
        />
      </div>

      {/* Chart + Quick links */}
      <div className="grid lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 card p-5">
          <h2 className="section-title">Monthly Activity</h2>
          {chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={chartData} barGap={4}>
                <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} tickFormatter={v => `₹${(v/1e5).toFixed(0)}L`} />
                <Tooltip formatter={v => fmtINR(v)} />
                <Bar dataKey="credit" name="Credit" fill="#22c55e" radius={[3,3,0,0]} />
                <Bar dataKey="debit"  name="Debit"  fill="#ef4444" radius={[3,3,0,0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[220px] flex items-center justify-center text-sm text-gray-400">
              {loading ? 'Loading chart…' : 'Upload ledger data to see chart'}
            </div>
          )}
        </div>

        <div className="card p-5">
          <h2 className="section-title">Quick Access</h2>
          <div className="space-y-2">
            {QUICK.map(({ label, icon: Icon, to, color, bg, desc }) => (
              <button
                key={to}
                onClick={() => navigate(to)}
                className="w-full flex items-center gap-3 p-3 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors text-left"
              >
                <div className={`p-2 rounded-lg shrink-0 ${bg}`}>
                  <Icon className={`w-4 h-4 ${color}`} />
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-gray-900 dark:text-white">{label}</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400 truncate">{desc}</p>
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Anomaly teaser */}
      {summary?.anomaly_count > 0 && (
        <div
          className="card p-5 border-l-4 border-l-red-500 cursor-pointer hover:shadow-md transition-shadow"
          onClick={() => navigate('/ledger')}
        >
          <div className="flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 text-red-500" />
            <div>
              <p className="text-sm font-semibold text-gray-900 dark:text-white">
                {summary.anomaly_count} Anomalies Detected
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Click to review flagged ledger entries
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function greeting() {
  const h = new Date().getHours()
  if (h < 12) return 'morning'
  if (h < 17) return 'afternoon'
  return 'evening'
}

function allUploaded(s) {
  return s?.ledger?.status === 'ok' && s?.gst?.status === 'ok' && s?.employee?.status === 'ok'
}
