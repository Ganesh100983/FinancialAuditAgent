import { useState, useEffect, useCallback } from 'react'
import { FileText, Download, RefreshCw, ChevronDown, ChevronUp, User } from 'lucide-react'
import { uploadApi, form16Api } from '../api/client'
import FileUpload from '../components/ui/FileUpload'
import MetricCard from '../components/ui/MetricCard'
import DataTable from '../components/ui/DataTable'
import Badge from '../components/ui/Badge'
import useAppStore from '../store/useAppStore'
import toast from 'react-hot-toast'

const fmtINR = n => n == null ? '—' : `₹${Number(n).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`

export default function Form16Generator() {
  const [employees, setEmployees]  = useState([])
  const [summary,   setSummary]    = useState(null)
  const [selected,  setSelected]   = useState(null)
  const [result,    setResult]     = useState(null)
  const [compare,   setCompare]    = useState(null)
  const [computing, setComputing]  = useState(false)
  const [loading,   setLoading]    = useState(false)
  const { uploads, setUpload } = useAppStore()

  const loadEmployees = useCallback(async () => {
    setLoading(true)
    try {
      const [emp, sum] = await Promise.allSettled([form16Api.employees(), form16Api.summary()])
      if (emp.status === 'fulfilled') setEmployees(emp.value.data?.employees ?? [])
      if (sum.status === 'fulfilled') setSummary(sum.value.data)
    } finally { setLoading(false) }
  }, [])

  useEffect(() => {
    if (uploads.employee?.status === 'ok') loadEmployees()
  }, [uploads.employee, loadEmployees])

  async function handleUpload(file) {
    try {
      const res = await uploadApi.employee(file)
      setUpload('employee', { status: 'ok', filename: file.name, rows: res.data.rows })
      toast.success(`Loaded ${res.data.rows} employee records`)
      loadEmployees()
    } catch (e) {
      setUpload('employee', { status: 'error', message: e.response?.data?.detail ?? e.message })
      throw e
    }
  }

  async function computeTax(employee_id) {
    setComputing(true)
    setResult(null)
    setCompare(null)
    try {
      const [tax, cmp] = await Promise.all([
        form16Api.compute({ employee_id }),
        form16Api.compareRegimes({ employee_id }),
      ])
      setResult(tax.data)
      setCompare(cmp.data)
    } catch (e) {
      toast.error(e.response?.data?.detail ?? 'Computation failed')
    } finally { setComputing(false) }
  }

  const empCols = [
    { key: 'employee_id',   label: 'ID' },
    { key: 'name',          label: 'Name' },
    { key: 'designation',   label: 'Designation' },
    { key: 'basic_salary',  label: 'Basic Salary', align: 'right', render: v => fmtINR(v) },
    { key: 'gross_salary',  label: 'Gross Salary', align: 'right', render: v => fmtINR(v) },
    { key: 'tds_deducted',  label: 'TDS Deducted', align: 'right', render: v => fmtINR(v) },
    {
      key: 'employee_id', label: 'Action',
      render: (id, row) => (
        <div className="flex gap-2">
          <button
            onClick={() => { setSelected(id); computeTax(id) }}
            className="text-xs px-2 py-1 rounded bg-brand-50 text-brand-700 hover:bg-brand-100 dark:bg-brand-900/20 dark:text-brand-400 font-medium"
          >
            Compute
          </button>
          <button
            onClick={() => form16Api.download(id, row.name).catch(e => toast.error(e.message))}
            className="text-xs px-2 py-1 rounded bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-400 font-medium"
          >
            PDF
          </button>
        </div>
      ),
    },
  ]

  return (
    <div className="space-y-5 max-w-7xl mx-auto">
      <div>
        <h1 className="text-xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
          <FileText className="w-5 h-5 text-green-600" /> Form 16 Generator
        </h1>
        <p className="text-sm text-gray-500 dark:text-gray-400">TDS certificate & tax computation for FY 2024-25</p>
      </div>

      <div className="card p-5">
        <FileUpload
          label="Employee Data (CSV / XLSX)"
          onUpload={handleUpload}
          status={uploads.employee}
          sampleUrl="/api/v1/upload/sample/employee"
        />
      </div>

      {uploads.employee?.status !== 'ok' && (
        <div className="text-center py-16 text-sm text-gray-400">
          Upload employee data to generate Form 16
        </div>
      )}

      {uploads.employee?.status === 'ok' && (
        <>
          {/* Summary metrics */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard title="Total Employees" value={summary?.total_employees} loading={loading} color="blue" />
            <MetricCard title="Total Gross Salary" value={fmtINR(summary?.total_gross_salary)} loading={loading} color="green" />
            <MetricCard title="Total TDS" value={fmtINR(summary?.total_tds_deducted)} loading={loading} color="red" />
            <MetricCard title="Avg Salary" value={fmtINR(summary?.average_salary)} loading={loading} color="purple" />
          </div>

          {/* Employee table */}
          <div className="card p-5">
            <h2 className="section-title">Employees ({employees.length})</h2>
            <DataTable columns={empCols} data={employees} loading={loading} pageSize={10} />
          </div>

          {/* Tax result panel */}
          {(computing || result) && (
            <div className="card p-5">
              <h2 className="section-title flex items-center gap-2">
                <User className="w-4 h-4" />
                Tax Computation — {selected}
              </h2>

              {computing && (
                <div className="flex items-center gap-2 text-sm text-gray-500 py-6 justify-center">
                  <RefreshCw className="w-4 h-4 animate-spin" /> Computing…
                </div>
              )}

              {result && !computing && (
                <div className="grid lg:grid-cols-2 gap-6">
                  {/* Old regime */}
                  <RegimeCard label="Old Regime" data={result.old_regime} recommended={compare?.recommended === 'old'} />
                  {/* New regime */}
                  <RegimeCard label="New Regime (Default)" data={result.new_regime} recommended={compare?.recommended === 'new'} />
                </div>
              )}

              {compare && !computing && (
                <div className="mt-4 p-4 rounded-xl bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 text-sm text-blue-700 dark:text-blue-400">
                  <strong>Recommendation:</strong> {compare.recommendation}
                  {compare.tax_savings > 0 && (
                    <span className="ml-2 font-semibold text-green-600 dark:text-green-400">
                      (Save {fmtINR(compare.tax_savings)})
                    </span>
                  )}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}

function RegimeCard({ label, data, recommended }) {
  const [open, setOpen] = useState(true)
  if (!data) return null

  const rows = [
    ['Gross Salary',        data.gross_salary],
    ['HRA Exemption',      -data.hra_exemption],
    ['Standard Deduction', -data.standard_deduction],
    ['80C Deductions',     -data.section_80c],
    ['80D Deductions',     -data.section_80d],
    ['Taxable Income',      data.taxable_income],
    ['Income Tax',          data.income_tax],
    ['Surcharge',           data.surcharge],
    ['Cess (4%)',           data.cess],
    ['Rebate 87A',         -data.rebate_87a],
  ]

  return (
    <div className={`rounded-xl border ${recommended ? 'border-green-400 dark:border-green-600' : 'border-gray-200 dark:border-gray-700'} overflow-hidden`}>
      <button
        className={`w-full flex items-center justify-between px-4 py-3 text-sm font-semibold ${recommended ? 'bg-green-50 dark:bg-green-900/20 text-green-800 dark:text-green-300' : 'bg-gray-50 dark:bg-gray-800 text-gray-700 dark:text-gray-300'}`}
        onClick={() => setOpen(o => !o)}
      >
        <span>{label} {recommended && <Badge variant="green" className="ml-2">Recommended</Badge>}</span>
        {open ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
      </button>
      {open && (
        <div className="px-4 py-3 space-y-1.5">
          {rows.map(([lbl, val]) => val != null && (
            <div key={lbl} className="flex justify-between text-sm">
              <span className="text-gray-600 dark:text-gray-400">{lbl}</span>
              <span className={`font-medium ${Number(val) < 0 ? 'text-green-600 dark:text-green-400' : 'text-gray-800 dark:text-gray-200'}`}>
                {Number(val) < 0 ? `(${fmtINR(Math.abs(val))})` : fmtINR(val)}
              </span>
            </div>
          ))}
          <div className="border-t border-gray-100 dark:border-gray-800 pt-2 mt-2 flex justify-between font-semibold text-sm">
            <span>Total Tax Payable</span>
            <span className="text-red-600 dark:text-red-400">{fmtINR(data.total_tax_payable)}</span>
          </div>
        </div>
      )}
    </div>
  )
}
