import { useEffect, useRef, useState } from 'react'
import { Menu, Sun, Moon, LogOut, User, Building2, ChevronDown, Check } from 'lucide-react'
import useAppStore from '../../store/useAppStore'
import { authApi, companiesApi } from '../../api/client'
import toast from 'react-hot-toast'
import { useNavigate } from 'react-router-dom'

export default function Header({ onMenuClick }) {
  const { user, darkMode, toggleDark, clearAuth, clearUploads, companies, activeCompany, setCompanies, setActiveCompany } = useAppStore()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const dropRef = useRef(null)

  useEffect(() => {
    companiesApi.list()
      .then(({ data }) => setCompanies(data.companies, data.active_company_id))
      .catch(() => {})
  }, [])

  useEffect(() => {
    function handleClick(e) {
      if (dropRef.current && !dropRef.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  async function handleSelect(company) {
    if (company.id === activeCompany?.id) { setOpen(false); return }
    try {
      await companiesApi.select(company.id)
      setActiveCompany(company)
      clearUploads()
      toast.success(`Switched to ${company.name} — please re-upload data`)
    } catch {
      toast.error('Failed to switch company')
    }
    setOpen(false)
  }

  async function handleLogout() {
    try { await authApi.logout() } catch { /* ignore */ }
    clearAuth()
    navigate('/login')
    toast.success('Logged out')
  }

  return (
    <header className="h-16 flex items-center justify-between px-4 border-b border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900 shrink-0">
      <button
        onClick={onMenuClick}
        className="lg:hidden p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800"
      >
        <Menu className="w-5 h-5 text-gray-600 dark:text-gray-400" />
      </button>

      <div className="flex-1 lg:flex-none" />

      <div className="flex items-center gap-2">
        {/* Company selector */}
        {companies.length > 0 && (
          <div className="relative" ref={dropRef}>
            <button
              onClick={() => setOpen(v => !v)}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-brand-50 dark:bg-brand-900/20 hover:bg-brand-100 dark:hover:bg-brand-800/30 transition-colors max-w-[220px]"
              title="Switch company"
            >
              <Building2 className="w-4 h-4 text-brand-600 dark:text-brand-400 shrink-0" />
              <span className="text-sm font-medium text-brand-700 dark:text-brand-300 truncate">
                {activeCompany?.name ?? 'Select Company'}
              </span>
              <ChevronDown className={`w-3.5 h-3.5 text-brand-500 shrink-0 transition-transform ${open ? 'rotate-180' : ''}`} />
            </button>

            {open && (
              <div className="absolute right-0 mt-1.5 w-64 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-xl shadow-lg z-50 py-1 overflow-hidden">
                <p className="text-xs font-medium text-gray-400 dark:text-gray-500 px-3 pt-2 pb-1 uppercase tracking-wide">
                  Companies
                </p>
                {companies.map(c => (
                  <button
                    key={c.id}
                    onClick={() => handleSelect(c)}
                    className="w-full flex items-center gap-2.5 px-3 py-2.5 hover:bg-gray-50 dark:hover:bg-gray-800 text-left transition-colors"
                  >
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-800 dark:text-gray-200 truncate">{c.name}</p>
                      {c.gstin && <p className="text-xs text-gray-400 font-mono">{c.gstin}</p>}
                    </div>
                    {activeCompany?.id === c.id && (
                      <Check className="w-4 h-4 text-brand-600 dark:text-brand-400 shrink-0" />
                    )}
                  </button>
                ))}
                <div className="border-t border-gray-100 dark:border-gray-800 mt-1 pt-1">
                  <button
                    onClick={() => { navigate('/settings'); setOpen(false) }}
                    className="w-full text-left px-3 py-2 text-xs text-brand-600 dark:text-brand-400 hover:bg-gray-50 dark:hover:bg-gray-800"
                  >
                    Manage companies →
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        <button
          onClick={toggleDark}
          className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
          title="Toggle dark mode"
        >
          {darkMode
            ? <Sun  className="w-4 h-4 text-gray-500 dark:text-gray-400" />
            : <Moon className="w-4 h-4 text-gray-500" />
          }
        </button>

        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-50 dark:bg-gray-800">
          <User className="w-4 h-4 text-gray-500 dark:text-gray-400" />
          <span className="text-sm text-gray-700 dark:text-gray-300 font-medium">
            {user?.username ?? 'User'}
          </span>
          <span className="text-xs text-gray-400 capitalize">({user?.role ?? 'user'})</span>
        </div>

        <button
          onClick={handleLogout}
          className="p-2 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 text-gray-500 hover:text-red-600 transition-colors"
          title="Logout"
        >
          <LogOut className="w-4 h-4" />
        </button>
      </div>
    </header>
  )
}
