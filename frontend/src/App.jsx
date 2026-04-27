import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/layout/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import LedgerScreener from './pages/LedgerScreener'
import Form16Generator from './pages/Form16Generator'
import GSTFiling from './pages/GSTFiling'
import AIAssistant from './pages/AIAssistant'
import Settings from './pages/Settings'
import useAppStore from './store/useAppStore'

function ProtectedRoute({ children }) {
  const token = useAppStore(s => s.token)
  return token ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard"   element={<Dashboard />} />
          <Route path="ledger"      element={<LedgerScreener />} />
          <Route path="form16"      element={<Form16Generator />} />
          <Route path="gst"         element={<GSTFiling />} />
          <Route path="assistant"   element={<AIAssistant />} />
          <Route path="settings"    element={<Settings />} />
        </Route>
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
