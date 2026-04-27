import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, BookOpen, FileText, Receipt,
  Bot, Settings, TrendingUp, X
} from 'lucide-react'
import clsx from 'clsx'
import useAppStore from '../../store/useAppStore'

const NAV = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/ledger',    icon: BookOpen,         label: 'Ledger Screener' },
  { to: '/form16',    icon: FileText,          label: 'Form 16' },
  { to: '/gst',       icon: Receipt,           label: 'GST Filing' },
  { to: '/assistant', icon: Bot,               label: 'AI Assistant' },
  { to: '/settings',  icon: Settings,          label: 'Settings' },
]

export default function Sidebar({ open, onClose }) {
  const darkMode = useAppStore(s => s.darkMode)

  return (
    <>
      {/* Mobile backdrop */}
      {open && (
        <div
          className="fixed inset-0 z-20 bg-black/40 lg:hidden"
          onClick={onClose}
        />
      )}

      <aside className={clsx(
        'fixed inset-y-0 left-0 z-30 flex flex-col w-64 bg-white dark:bg-gray-900',
        'border-r border-gray-100 dark:border-gray-800 transition-transform duration-200',
        'lg:translate-x-0 lg:static lg:z-auto',
        open ? 'translate-x-0' : '-translate-x-full'
      )}>
        {/* Logo */}
        <div className="flex items-center justify-between h-16 px-5 border-b border-gray-100 dark:border-gray-800">
          <div className="flex items-center gap-2">
            <TrendingUp className="w-6 h-6 text-brand-600" />
            <span className="font-semibold text-gray-900 dark:text-white text-sm">
              FinAudit AI
            </span>
          </div>
          <button onClick={onClose} className="lg:hidden p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800">
            <X className="w-4 h-4 text-gray-500" />
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-0.5">
          {NAV.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              onClick={onClose}
              className={({ isActive }) => clsx(
                'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all',
                isActive
                  ? 'bg-brand-50 text-brand-700 font-medium dark:bg-brand-900/30 dark:text-brand-400'
                  : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-white'
              )}
            >
              <Icon className="w-4 h-4 shrink-0" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="p-4 border-t border-gray-100 dark:border-gray-800">
          <p className="text-xs text-gray-400 text-center">v2.0 · Powered by GPT-4o mini</p>
        </div>
      </aside>
    </>
  )
}
