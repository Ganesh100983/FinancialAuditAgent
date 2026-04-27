import { useState, useEffect } from 'react'
import { Settings as SettingsIcon, Key, Building2, Save, Eye, EyeOff, Loader2, CheckCircle } from 'lucide-react'
import { chatApi } from '../api/client'
import useAppStore from '../store/useAppStore'
import toast from 'react-hot-toast'

export default function Settings() {
  const { settings, setSettings, user } = useAppStore()

  const [form, setForm] = useState({
    company_name:    settings.company_name    ?? '',
    company_gstin:   settings.company_gstin   ?? '',
    financial_year:  settings.financial_year  ?? '2024-25',
    openai_api_key:  '',
  })
  const [showKey,  setShowKey]  = useState(false)
  const [saving,   setSaving]   = useState(false)
  const [loading,  setLoading]  = useState(true)

  useEffect(() => {
    chatApi.getSettings()
      .then(({ data }) => {
        setForm(f => ({
          ...f,
          company_name:   data.company_name   ?? '',
          company_gstin:  data.company_gstin  ?? '',
          financial_year: data.financial_year ?? '2024-25',
          openai_api_key: '',
        }))
        setSettings({
          company_name:   data.company_name,
          company_gstin:  data.company_gstin,
          financial_year: data.financial_year,
          openai_key_set: data.openai_api_key_set,
        })
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const patch = k => e => setForm(f => ({ ...f, [k]: e.target.value }))

  async function handleSave(e) {
    e.preventDefault()
    setSaving(true)
    try {
      const body = {
        company_name:   form.company_name,
        company_gstin:  form.company_gstin,
        financial_year: form.financial_year,
        ...(form.openai_api_key ? { openai_api_key: form.openai_api_key } : {}),
      }
      const { data } = await chatApi.updateSettings(body)
      setSettings({
        company_name:   data.company_name,
        company_gstin:  data.company_gstin,
        financial_year: data.financial_year,
        openai_key_set: data.openai_api_key_set,
      })
      setForm(f => ({ ...f, openai_api_key: '' }))
      toast.success('Settings saved')
    } catch (e) {
      toast.error(e.response?.data?.detail ?? 'Save failed')
    } finally { setSaving(false) }
  }

  const FY_OPTIONS = ['2023-24', '2024-25', '2025-26']

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
          <SettingsIcon className="w-5 h-5 text-gray-600" /> Settings
        </h1>
        <p className="text-sm text-gray-500 dark:text-gray-400">Configure API keys, company details and preferences</p>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16 text-sm text-gray-400">
          <Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading settings…
        </div>
      ) : (
        <form onSubmit={handleSave} className="space-y-5">

          {/* Company details */}
          <div className="card p-5 space-y-4">
            <h2 className="text-sm font-semibold text-gray-900 dark:text-white flex items-center gap-2">
              <Building2 className="w-4 h-4 text-brand-600" /> Company Details
            </h2>

            <div>
              <label className="label">Company Name</label>
              <input className="input" placeholder="Acme Pvt. Ltd." value={form.company_name} onChange={patch('company_name')} />
            </div>

            <div>
              <label className="label">Company GSTIN</label>
              <input
                className="input font-mono"
                placeholder="29AAAAA0000A1Z5"
                value={form.company_gstin}
                onChange={e => setForm(f => ({ ...f, company_gstin: e.target.value.toUpperCase() }))}
                maxLength={15}
              />
              <p className="text-xs text-gray-400 mt-1">15-character GST Identification Number</p>
            </div>

            <div>
              <label className="label">Financial Year</label>
              <select className="input" value={form.financial_year} onChange={patch('financial_year')}>
                {FY_OPTIONS.map(y => <option key={y} value={y}>{y}</option>)}
              </select>
            </div>
          </div>

          {/* API Key */}
          <div className="card p-5 space-y-4">
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
                  onChange={patch('openai_api_key')}
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
                Get yours at <span className="text-brand-600">platform.openai.com/api-keys</span>
              </p>
            </div>
          </div>

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

          <div className="flex justify-end">
            <button type="submit" disabled={saving} className="btn-primary">
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
              {saving ? 'Saving…' : 'Save Settings'}
            </button>
          </div>
        </form>
      )}
    </div>
  )
}
