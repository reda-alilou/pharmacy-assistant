import { useEffect, useRef, useState } from 'react'
import { useBlocker, useLocation, useNavigate, type BlockerFunction } from 'react-router'
import { AccountError } from '@/features/accounts/api'
import { DiscardDialog } from './editing-feedback'

type Options = {
  dirty: boolean
  pending?: boolean
  label: string
  shouldBlock?: BlockerFunction
}

/** Warning only: all values stay in their existing editor, never in storage. */
export function useUnsavedChanges({ dirty, pending = false, label, shouldBlock }: Options) {
  const bypass = useRef(false)
  const mounted = useRef(true)
  const [action, setAction] = useState<(() => void) | null>(null)
  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])
  const blocker = useBlocker(args => !bypass.current && (dirty || pending) && (
    shouldBlock ? shouldBlock(args) : args.currentLocation.pathname !== args.nextLocation.pathname || args.currentLocation.search !== args.nextLocation.search
  ))

  useEffect(() => {
    if (!dirty && !pending) return
    const unload = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = '' }
    const logout = (event: Event) => {
      if (!(event instanceof CustomEvent) || typeof event.detail?.proceed !== 'function') return
      event.preventDefault()
      setAction(() => event.detail.proceed)
    }
    window.addEventListener('beforeunload', unload)
    window.addEventListener('platform:before-logout', logout)
    return () => {
      window.removeEventListener('beforeunload', unload)
      window.removeEventListener('platform:before-logout', logout)
    }
  }, [dirty, pending])

  function allowNavigation(navigate: () => void) {
    if (!mounted.current) return
    bypass.current = true
    try { navigate() } finally { bypass.current = false }
  }
  function confirmDiscard(next: () => void) {
    if (dirty || pending) setAction(() => next)
    else next()
  }
  function stay() {
    if (blocker.state === 'blocked') blocker.reset()
    setAction(null)
  }
  function discard() {
    if (blocker.state === 'blocked') blocker.proceed()
    else if (action) allowNavigation(action)
    setAction(null)
  }

  return {
    allowNavigation, confirmDiscard, isActive: () => mounted.current,
    dialog: <DiscardDialog open={blocker.state === 'blocked' || action !== null} label={label} dirty={dirty} pending={pending} stay={stay} discard={discard} />,
  }
}

/** Preserve the server's message, while distinguishing conflict and uncertainty. */
export function mutationMessage(error: unknown) {
  const message = error instanceof Error ? error.message : 'Le service est indisponible.'
  if (error instanceof AccountError && error.status === 409) return message + ' Vos saisies restent dans cet éditeur. Vérifiez la version enregistrée avant de corriger ou de réessayer ; aucune modification n’a été écrasée automatiquement.'
  if (error instanceof AccountError && error.status === 0) return 'Résultat de l’opération incertain. Vos saisies restent dans cet éditeur. Vérifiez l’état enregistré avant une nouvelle tentative. Aucune demande ne sera renvoyée automatiquement.'
  return message
}

/** A successful create redirects to its saved resource; carry feedback, never input. */
export function useSaveNotice() {
  const location = useLocation(), navigate = useNavigate()
  const savedNotice = typeof location.state?.savedNotice === 'string' ? location.state.savedNotice : ''
  const [notice, setNotice] = useState(savedNotice)
  useEffect(() => {
    if (savedNotice) void navigate(location.pathname + location.search + location.hash, { replace: true, state: { ...location.state, savedNotice: undefined } })
  }, [savedNotice, location, navigate])
  return [notice, setNotice] as const
}
