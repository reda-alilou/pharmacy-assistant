import { useEffect, useRef, useState, useSyncExternalStore } from 'react'
import { ArrowRight, ArrowUp, Check, Cross, Info, LoaderCircle, MapPin, MessageSquarePlus, Pill, RefreshCw, ShieldCheck, TriangleAlert } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from '@/components/ui/alert-dialog'
import { Results } from '@/components/results'
import { ConversationController } from '@/lib/conversation'

const examples = [
  { title: 'Le prix d’un médicament', question: 'Quel est le prix de ABIP ?', icon: Pill },
  { title: 'Une pharmacie à Rabat', question: 'Une pharmacie à Agdal, Rabat', icon: MapPin },
  { title: 'Une présentation précise', question: 'ABIP 15mg en boîte de 30', icon: ShieldCheck },
]

function App() {
  const [controller] = useState(() => new ConversationController())
  const state = useSyncExternalStore(controller.subscribe, controller.getSnapshot)
  const [draft, setDraft] = useState('')
  const [resetOpen, setResetOpen] = useState(false)
  const [resetFailed, setResetFailed] = useState(false)
  const [now, setNow] = useState(() => Date.now())
  const [showJump, setShowJump] = useState(false)
  const textarea = useRef<HTMLTextAreaElement>(null)
  const end = useRef<HTMLDivElement>(null)
  const form = useRef<HTMLFormElement>(null)
  const length = [...draft].length
  const cooldownSeconds = Math.max(0, Math.ceil((state.cooldownUntil - now) / 1000))
  const inputBlocked = state.busy || state.loading || state.recoveryRequired || cooldownSeconds > 0
  const canSubmit = !inputBlocked && length <= 2000 && /[^\s\p{M}]/u.test(draft)
  const hasConversation = state.messages.length > 0 || state.token !== null

  useEffect(() => { void controller.initialize() }, [controller])
  useEffect(() => { const timer = window.setInterval(() => setNow(Date.now()), 1000); return () => window.clearInterval(timer) }, [])
  useEffect(() => { if (state.expiresAt && !state.busy && Date.parse(state.expiresAt) <= now) controller.expire() }, [controller, state.expiresAt, state.busy, now])
  useEffect(() => { if (textarea.current) { textarea.current.style.height = '0px'; textarea.current.style.height = Math.min(148, Math.max(52, textarea.current.scrollHeight)) + 'px' } }, [draft])
  useEffect(() => { if (!state.loading && !state.busy) textarea.current?.focus({ preventScroll: true }) }, [state.loading, state.busy])
  useEffect(() => { const check = () => setShowJump(window.innerHeight + window.scrollY < document.documentElement.scrollHeight - 240); window.addEventListener('scroll', check, { passive: true }); check(); return () => window.removeEventListener('scroll', check) }, [])
  useEffect(() => { if (state.messages.length && !showJump) end.current?.scrollIntoView({ block: 'end', behavior: 'instant' }) }, [state.messages.length, state.busy, showJump])

  function prepare(question: string) { setDraft(question); textarea.current?.focus() }
  async function newConversation() {
    setResetFailed(false)
    if (await controller.reset()) { setResetOpen(false); setDraft(''); window.scrollTo({ top: 0 }); textarea.current?.focus() }
    else setResetFailed(true)
  }

  return <div className={state.messages.length ? 'app-shell is-chat' : 'app-shell is-welcome'}><a className="skip-link" href="#conversation">Aller à la conversation</a>
    <header className="app-header"><div className="header-inner"><a className="brand" href="#conversation" aria-label="Assistant pharmacie, accueil"><span className="brand-mark"><Cross size={22} strokeWidth={1.8} aria-hidden="true" /></span><span>Assistant<span className="brand-second"> pharmacie</span></span></a>
      <div className="header-right"><span className="header-context">Un repère, des informations sourcées.</span><AlertDialog open={resetOpen} onOpenChange={setResetOpen}><AlertDialogTrigger asChild><Button variant="outline" className="new-conversation" disabled={state.busy || state.loading || !hasConversation}><MessageSquarePlus size={16} aria-hidden="true" /><span>Nouvelle conversation</span></Button></AlertDialogTrigger>
        <AlertDialogContent><AlertDialogHeader><AlertDialogTitle>Commencer une nouvelle conversation ?</AlertDialogTitle><AlertDialogDescription>Les messages et le contexte de cette conversation temporaire seront supprimés. Cette action est définitive.</AlertDialogDescription></AlertDialogHeader>
          {resetFailed && <p role="alert" className="dialog-error">La conversation n’a pas pu être effacée. Elle est conservée ; réessayez lorsque le service est disponible.</p>}
          <AlertDialogFooter><AlertDialogCancel disabled={state.busy}>Annuler</AlertDialogCancel><AlertDialogAction disabled={state.busy} onClick={event => { event.preventDefault(); void newConversation() }}>{state.busy && <LoaderCircle className="animate-spin" size={15} aria-hidden="true" />}Nouvelle conversation</AlertDialogAction></AlertDialogFooter>
        </AlertDialogContent></AlertDialog></div></div></header>

    <main id="conversation" className={state.messages.length ? 'conversation-main has-messages' : 'conversation-main'} tabIndex={-1}>
      {state.messages.length > 0 && <h1 className="sr-only">Votre conversation avec l’assistant pharmacie</h1>}
      {state.loading ? <div className="initial-loading" role="status"><LoaderCircle className="animate-spin" aria-hidden="true" size={22} />Reprise de votre conversation…</div>
        : !state.messages.length && <section className="welcome" aria-labelledby="welcome-title"><p className="eyebrow"><span className="tiny-cross" aria-hidden="true">+</span> VOTRE ASSISTANT PHARMACIE</p><h1 id="welcome-title">Une question sur<br /><em>vos médicaments ?</em></h1>
          <p className="welcome-description">Retrouvez un prix enregistré, précisez une présentation<br className="desktop-break" /> ou trouvez les coordonnées d’une pharmacie à Rabat.</p>
          <div className="examples" aria-label="Exemples de questions">{examples.map(({ title, question, icon: Icon }) => <button key={title} className="example-card" onClick={() => prepare(question)} disabled={state.busy || state.recoveryRequired}><Icon size={20} strokeWidth={1.6} aria-hidden="true" /><span className="example-title">{title}</span><span className="example-question">{question}</span><ArrowRight className="example-arrow" size={16} aria-hidden="true" /></button>)}</div>
          <p className="welcome-footnote"><Check size={14} aria-hidden="true" />Des réponses à partir de données collectées au Maroc</p>
        </section>}

      {state.messages.length > 0 && <div className="message-list" role="log" aria-label="Conversation" aria-live="polite" aria-relevant="additions">{state.messages.map(message => message.role === 'user' ? <div className="user-message" key={message.key}><span className="sr-only">Vous</span><p dir="auto">{message.text}</p>
        {message.outcome === 'failed' && <span className="message-status"><TriangleAlert size={12} aria-hidden="true" />Demande non aboutie</span>}{message.outcome === 'pending' && !state.busy && <span className="message-status">Résultat à vérifier</span>}
      </div> : <article className="assistant-message" key={message.key} aria-label="Réponse de l’assistant"><h2 className="assistant-label"><span className="assistant-mark"><Cross size={13} aria-hidden="true" /></span>Assistant pharmacie</h2>
        {message.response && <Results response={message.response} active={message.key === state.activeKey} token={state.token} disabled={state.busy || state.recoveryRequired} onAction={(action, label) => { void controller.choose(action, label) }} />}
      </article>)}</div>}
      {state.busy && !state.loading && <div className="working" role="status"><span className="thinking-dots" aria-hidden="true"><i /><i /><i /></span>Votre demande est en cours…</div>}
      {state.notice && <div className="notice" role="status"><Info size={17} aria-hidden="true" /><p>{state.notice}</p></div>}
      {state.error && !resetOpen && <div className="error-notice" role="alert"><TriangleAlert size={18} aria-hidden="true" /><div><p>{state.error.message}</p>
        {state.recoveryRequired && <p className="error-detail">Aucune demande ne sera renvoyée automatiquement.</p>}{state.retryText && !state.recoveryRequired && !state.error.retryable && <p className="error-detail">Votre question est conservée. Vous pouvez la modifier avant un nouvel envoi.</p>}
        <div className="error-actions">{state.recoveryRequired ? <Button variant="outline" size="sm" onClick={() => { void controller.recover() }} disabled={state.busy}><RefreshCw size={14} aria-hidden="true" />Vérifier la conversation</Button>
          : state.retryText && <>{state.error.retryable && <Button variant="outline" size="sm" onClick={() => { void controller.retry() }} disabled={state.busy || cooldownSeconds > 0}>Réessayer la question</Button>}<Button variant="ghost" size="sm" disabled={state.busy} onClick={() => prepare(state.retryText!)}>Modifier la question</Button></>}
          {cooldownSeconds > 0 && <span className="cooldown">Réessai possible dans {Math.floor(cooldownSeconds / 60)} min {String(cooldownSeconds % 60).padStart(2, '0')} s</span>}
        </div></div></div>}
      {state.storageWarning && <p className="storage-notice">La reprise après actualisation n’est pas disponible dans ce navigateur. Cette conversation reste utilisable dans cet onglet.</p>}
      <div ref={end} className="conversation-end" />
    </main>

    <footer className="composer-area"><div className="composer-inner">{showJump && state.messages.length > 0 && <Button className="jump-button" variant="outline" size="sm" onClick={() => end.current?.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth', block: 'end' })}>Derniers messages<ArrowUp className="rotate-180" size={14} aria-hidden="true" /></Button>}
      <form ref={form} className="composer" aria-label="Envoyer une question" onSubmit={event => { event.preventDefault(); if (canSubmit) { const text = draft; setDraft(''); void controller.send(text) } }}><label htmlFor="question" className="sr-only">Votre question</label>
        <Textarea id="question" ref={textarea} value={draft} onChange={event => setDraft(event.target.value)} placeholder="Écrivez votre question, par exemple : quel est le prix de ABIP ?" className="question-input" dir="auto" disabled={state.loading || state.busy} rows={1} aria-describedby="composer-help question-count" aria-invalid={length > 2000}
          onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); if (canSubmit) form.current?.requestSubmit() } }} />
        <Button type="submit" size="icon" className="send-button" aria-label="Envoyer la question" disabled={!canSubmit}>{state.busy ? <LoaderCircle className="animate-spin" size={19} aria-hidden="true" /> : <ArrowUp size={21} aria-hidden="true" />}</Button>
      </form><div className="composer-meta"><p id="composer-help">{state.recoveryRequired ? 'Vérifiez la conversation avant un nouvel envoi.' : cooldownSeconds > 0 ? 'Une pause est nécessaire avant une nouvelle question. Les choix restent disponibles.' : 'Conversation temporaire · Expire après 30 min d’inactivité'}</p><span id="question-count" className={length > 2000 ? 'invalid-count' : ''}>{length > 1600 ? `${length} / 2 000` : 'Entrée pour envoyer'}</span></div>
      <p className="limitations"><Info size={13} aria-hidden="true" /><span>Prix enregistrés · Stock non vérifié · Annuaire partiel de Rabat</span></p>
    </div></footer>
  </div>
}

export default App
