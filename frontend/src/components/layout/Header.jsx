import { Menu, Sun, Moon, LogOut, User } from 'lucide-react'
import useAppStore from '../../store/useAppStore'
import { authApi } from '../../api/client'
import toast from 'react-hot-toast'
import { useNavigate } from 'react-router-dom'

export default function Header({ onMenuClick }) {
  const { user, darkMode, toggleDark, clearAuth } = useAppStore()
  const navigate = useNavigate()

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
