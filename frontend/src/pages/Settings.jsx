import { useState, useEffect } from 'react'
import { Settings as SettingsIcon, Key, Building2, Save, Eye, EyeOff, Loader2, CheckCircle, Plus, Pencil, Trash2, X, Check } from 'lucide-react'
import { chatApi, companiesApi } from '../api/client'
import useAppStore from '../store/useAppStore'
import toast from 'react-hot-toast'

const EMPTY_COMPANY = { name: '', gstin: '', tan: '', pan: '', address: '', financial_year: '2024-25' }
const FY_OPTIONS = ['2023-24', '2024-25', '2025-26']

export default function Settings() {
  const { settings, setSettings, user, companies, activeCompany, setCompanies, setActiveCompany, clearUploads } = useAppStore()

  const [form, setForm] = useState({
    openai_api_key: '',
  })
  const [showKey,  setShowKey]  = useState(false)
  const [saving,   setSaving]   = useState(false)
  const [loading,  setLoading]  = useState(true)

  // Company editor state
  const [editId,   setEditId]   = useState(null)   // null = not editing, 'new' = adding, else company id
  const [editForm, setEditForm] = useState(EMPTY_COMPANY)
  const [savingCo, setSavingCo] = useState(false)

  useEffect(() => {
    Promise.all([chatApi.getSettings(), companiesApi.list()])
      .then(([{ data: s }, { data: c }]) => {
        setForm(f => ({ ...f, openai_api_key: '' }))
        setSettings({
          company_name:   s.company_name,
          company_gstin:  s.company_gstin,
          financial_year: s.financial_year,
          openai_key_set: s.openai_api_key_set,
        })
        setCompanies(c.companies, c.active_company_id)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  async function handleSaveKey(e) {
    e.preventDefault()
    if (!form.openai_api_key) return
    setSaving(true)
    try {
      const { data } = await chatApi.updateSettings({ openai_api_key: form.openai_api_key })
      setSettings({ openai_key_set: data.openai_api_key_set ?? true })
      setForm(f => ({ ...f, openai_api_key: '' }))
      toast.success('API key saved')
    } catch (e) {
      toast.error(e.response?.data?.detail ?? 'Save failed')
    } finally { setSaving(false) }
  }

  function startEdit(company) {
    setEditId(company.id)
    setEditForm({
      name:           company.name ?? '',
      gstin:          company.gstin ?? '',
      tan:            company.tan ?? '',
      pan:            company.pan ?? '',
      address:        company.address ?? '',
      financial_year: company.financial_year ?? '2024-25',
    })
  }

  function startAdd() {
    setEditId('new')
    setEditForm(EMPTY_COMPANY)
  }

  function cancelEdit() {
    setEditId(null)
    setEditForm(EMPTY_COMPANY)
  }

  async function saveCompany() {
    if (!editForm.name.trim()) { toast.error('Company name is required'); return }
    setSavingCo(true)
    try {
      if (editId === 'new') {
        const { data: newCo } = await companiesApi.add(editForm)
        const updated = [...companies, newCo]
        setCompanies(updated, activeCompany?.id)
        toast.success('Company added')
      } else {
        const { data: updated } = await companiesApi.update(editId, editForm)
        const updatedList = companies.map(c => c.id === editId ? updated : c)
        setCompanies(updatedList, activeCompany?.id)
        if (activeCompany?.id === editId) setActiveCompany(updated)
        toast.success('Company updated')
      }
      cancelEdit()
    } catch (e) {
      toast.error(e.response?.data?.detail ?? 'Save failed')
    } finally { setSavingCo(false) }
  }

  async function removeCompany(id) {
    if (companies.length <= 1) { toast.error('Cannot delete the last company'); return }
    try {
      await companiesApi.remove(id)
      const updated = companies.filter(c => c.id !== id)
      const newActiveId = activeCompany?.id === id ? updated[0]?.id : activeCompany?.id
      setCompanies(updated, newActiveId)
      if (activeCompany?.id === id) setActiveCompany(updated[0] ?? null)
      toast.success('Company removed')
    } catch (e) {
      toast.error(e.response?.data?.detail ?? 'Delete failed')
    }
  }

  async function selectCompany(company) {
    if (company.id === activeCompany?.id) return
    try {
      await companiesApi.select(company.id)
      setActiveCompany(company)
      clearUploads()
      toast.success(`Switched to ${company.name} — please re-upload data`)
    } catch (e) {
      toast.error(e.response?.data?.detail ?? 'Switch failed')
    }
  }

  const patchEdit = k => e => setEditForm(f => ({ ...f, [k]: e.target.value }))

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
          <SettingsIcon className="w-5 h-5 text-gray-600" /> Settings
        </h1>
        <p className="text-sm text-gray-500 dark:text-gray-400">Configure API keys, companies and preferences</p>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16 text-sm text-gray-400">
          <Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading…
        </div>
      ) : (
        <div className="space-y-5">

          {/* Companies */}
          <div className="card p-5 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                <Building2 className="w-4 h-4 text-brand-600" /> Companies
              </h2>
              {editId !== 'new' && (
                <button onClick={startAdd} className="btn-secondary text-xs gap-1">
                  <Plus className="w-3.5 h-3.5" /> Add Company
                </button>
              )}
            </div>

            {/* Add form */}
            {editId === 'new' && (
              <CompanyForm
                form={editForm}
                patch={patchEdit}
                onSave={saveCompany}
                onCancel={cancelEdit}
                saving={savingCo}
                title="New Company"
              />
            )}

            {/* Company list */}
            <div className="space-y-2">
              {companies.map(c => (
                <div key={c.id}>
                  {editId === c.id ? (
                    <CompanyForm
                      form={editForm}
                      patch={patchEdit}
                      onSave={saveCompany}
                      onCancel={cancelEdit}
                      saving={savingCo}
                      title="Edit Company"
                    />
                  ) : (
                    <div className={`flex items-center gap-3 p-3 rounded-lg border transition-colors ${
                      activeCompany?.id === c.id
                        ? 'border-brand-300 dark:border-brand-600 bg-brand-50 dark:bg-brand-900/20'
                        : 'border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50'
                    }`}>
                      <button
                        onClick={() => selectCompany(c)}
                        className="flex-1 text-left min-w-0"
                        title="Set as active company"
                      >
                        <div className="flex items-center gap-2">
                          {activeCompany?.id === c.id && (
                            <Check className="w-3.5 h-3.5 text-brand-600 dark:text-brand-400 shrink-0" />
                          )}
                          <p className="text-sm font-medium text-gray-900 dark:text-white truncate">{c.name}</p>
                          {activeCompany?.id === c.id && (
                            <span className="text-xs bg-brand-100 dark:bg-brand-800 text-brand-700 dark:text-brand-300 px-1.5 py-0.5 rounded font-medium shrink-0">
                              Active
                            </span>
                          )}
                        </div>
                        <div className="flex gap-3 mt-0.5">
                          {c.gstin && <p className="text-xs text-gray-400 font-mono">{c.gstin}</p>}
                          {c.financial_year && <p className="text-xs text-gray-400">FY {c.financial_year}</p>}
                        </div>
                      </button>
                      <div className="flex gap-1 shrink-0">
                        <button
                          onClick={() => startEdit(c)}
                          className="p-1.5 rounded hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
                          title="Edit"
                        >
                          <Pencil className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => removeCompany(c.id)}
                          disabled={companies.length <= 1}
                          className="p-1.5 rounded hover:bg-red-50 dark:hover:bg-red-900/20 text-gray-400 hover:text-red-600 disabled:opacity-30 disabled:cursor-not-allowed"
                          title="Delete"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
            <p className="text-xs text-gray-400">Click a company to set it as active. All PDFs and reports will use the active company's details.</p>
          </div>

          {/* API Key */}
          <form onSubmit={handleSaveKey} className="card p-5 space-y-4">
            <h2 className="text-sm font-semibold text-gray-900 dark:text-white flex items-center gap-2">
              <Key className="w-4 h-4 text-brand-600" /> OpenAI API Key
            </h2>

            <div className="flex items-center gap-2 text-sm">
              {settings.openai_key_set ? (
                <span className="flex items-center gap-1.5 text-green-600 dark:text-green-400">
                  <CheckCircle className="w-4 h-4" /> API key is configured
                </span>
              ) : (
                <span className="text-yellow-600 dark:text-yellow-400">No API key set — AI Assistant will not work</span>
              )}
            </div>

            <div>
              <label className="label">{settings.openai_key_set ? 'Replace API Key' : 'Enter API Key'}</label>
              <div className="relative">
                <input
                  className="input pr-10 font-mono"
                  type={showKey ? 'text' : 'password'}
                  placeholder="sk-..."
                  value={form.openai_api_key}
                  onChange={e => setForm(f => ({ ...f, openai_api_key: e.target.value }))}
                  autoComplete="off"
                />
                <button
                  type="button"
                  onClick={() => setShowKey(v => !v)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 text-gray-400 hover:text-gray-600"
                >
                  {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              <p className="text-xs text-gray-400 mt-1">
                Key is stored server-side and never exposed to the browser after saving.
              </p>
            </div>
            <div className="flex justify-end">
              <button type="submit" disabled={saving || !form.openai_api_key} className="btn-primary">
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                {saving ? 'Saving…' : 'Save Key'}
              </button>
            </div>
          </form>

          {/* Account info */}
          <div className="card p-5 space-y-3">
            <h2 className="text-sm font-semibold text-gray-900 dark:text-white">Account</h2>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <p className="text-gray-500 dark:text-gray-400">Username</p>
                <p className="font-medium text-gray-800 dark:text-gray-200">{user?.username ?? '—'}</p>
              </div>
              <div>
                <p className="text-gray-500 dark:text-gray-400">Role</p>
                <p className="font-medium text-gray-800 dark:text-gray-200 capitalize">{user?.role ?? '—'}</p>
              </div>
            </div>
          </div>

        </div>
      )}
    </div>
  )
}

function CompanyForm({ form, patch, onSave, onCancel, saving, title }) {
  return (
    <div className="border border-brand-200 dark:border-brand-700 rounded-lg p-4 space-y-3 bg-brand-50/50 dark:bg-brand-900/10">
      <p className="text-xs font-semibold text-brand-700 dark:text-brand-400 uppercase tracking-wide">{title}</p>
      <div className="grid grid-cols-2 gap-3">
        <div className="col-span-2">
          <label className="label">Company Name *</label>
          <input className="input" placeholder="Acme Pvt. Ltd." value={form.name} onChange={patch('name')} />
        </div>
        <div>
          <label className="label">GSTIN</label>
          <input
            className="input font-mono"
            placeholder="29AAAAA0000A1Z5"
            value={form.gstin}
            onChange={e => patch('gstin')({ target: { value: e.target.value.toUpperCase() } })}
            maxLength={15}
          />
        </div>
        <div>
          <label className="label">Financial Year</label>
          <select className="input" value={form.financial_year} onChange={patch('financial_year')}>
            {['2023-24', '2024-25', '2025-26'].map(y => <option key={y} value={y}>{y}</option>)}
          </select>
        </div>
        <div>
          <label className="label">TAN</label>
          <input className="input font-mono" placeholder="MUMA12345A" value={form.tan} onChange={patch('tan')} />
        </div>
        <div>
          <label className="label">PAN</label>
          <input className="input font-mono" placeholder="AABCE1234A" value={form.pan} onChange={patch('pan')} />
        </div>
        <div className="col-span-2">
          <label className="label">Address</label>
          <input className="input" placeholder="Mumbai, Maharashtra - 400001" value={form.address} onChange={patch('address')} />
        </div>
      </div>
      <div className="flex justify-end gap-2 pt-1">
        <button type="button" onClick={onCancel} className="btn-secondary text-xs gap-1">
          <X className="w-3.5 h-3.5" /> Cancel
        </button>
        <button type="button" onClick={onSave} disabled={saving} className="btn-primary text-xs gap-1">
          {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
          {saving ? 'Saving…' : 'Save'}
        </button>
      </div>
    </div>
  )
}
