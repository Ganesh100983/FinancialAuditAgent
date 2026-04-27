import { create } from 'zustand'
import { persist } from 'zustand/middleware'

const useAppStore = create(
  persist(
    (set, get) => ({
      // Auth
      token: null,
      user: null,
      setAuth: (token, user) => {
        localStorage.setItem('fa_token', token)
        set({ token, user })
      },
      clearAuth: () => {
        localStorage.removeItem('fa_token')
        set({ token: null, user: null })
      },

      // Upload status
      uploads: { ledger: null, gst: null, employee: null },
      setUpload: (type, info) => set(s => ({ uploads: { ...s.uploads, [type]: info } })),
      clearUploads: () => set({ uploads: { ledger: null, gst: null, employee: null } }),

      // Dark mode
      darkMode: false,
      toggleDark: () => {
        const next = !get().darkMode
        document.documentElement.classList.toggle('dark', next)
        set({ darkMode: next })
      },

      // Company settings (mirrored locally for display)
      settings: {
        company_name: '',
        company_gstin: '',
        financial_year: '2024-25',
        openai_key_set: false,
      },
      setSettings: patch => set(s => ({ settings: { ...s.settings, ...patch } })),

      // Companies list & active selection
      companies: [],
      activeCompany: null,
      setCompanies: (companies, activeId) => {
        const active = companies.find(c => c.id === activeId) ?? companies[0] ?? null
        set({ companies, activeCompany: active })
      },
      setActiveCompany: company => set(s => ({
        activeCompany: company,
        settings: { ...s.settings, company_name: company?.name ?? '', company_gstin: company?.gstin ?? '' },
      })),
    }),
    {
      name: 'fa-store',
      partialize: s => ({ token: s.token, user: s.user, darkMode: s.darkMode }),
    }
  )
)

export default useAppStore
