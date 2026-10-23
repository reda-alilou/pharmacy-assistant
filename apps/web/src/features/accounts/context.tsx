import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { type AccountSession, loadSession } from './api'
import { AccountContext } from './account-context'

export function AccountProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<AccountSession | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const refresh = useCallback(async () => {
    try { setSession(await loadSession()); setError('') }
    catch (error) { setSession(null); setError(error instanceof Error ? error.message : 'Service indisponible.') }
    finally { setLoading(false) }
  }, [])
  useEffect(() => {
    void Promise.resolve().then(refresh)
    const focus = () => { void refresh() }
    window.addEventListener('focus', focus)
    const timer = window.setInterval(focus, 60_000)
    return () => { window.removeEventListener('focus', focus); window.clearInterval(timer) }
  }, [refresh])
  return <AccountContext.Provider value={{ session, loading, error, refresh, setSession }}>{children}</AccountContext.Provider>
}
