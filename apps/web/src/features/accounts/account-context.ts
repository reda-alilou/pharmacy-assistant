import { createContext, useContext } from 'react'
import type { AccountSession } from './api'

type Accounts = { session: AccountSession | null; loading: boolean; error: string; refresh: () => Promise<void>; setSession: (session: AccountSession | null) => void }
export const AccountContext = createContext<Accounts | null>(null)
export function useAccounts() {
  const context = useContext(AccountContext)
  if (!context) throw new Error('Account provider missing')
  return context
}
