import { ApiError, api, type ChatRequest, type ConversationApi } from '@/shared/api/client'
import { conversationSchema, responseSchema, tokenSchema, type Conversation, type Message, type PatientResponse } from '@/shared/api/schema'
import { z } from 'zod'

const SESSION_KEY = 'pharmacy.active-conversation.v1'
const COOLDOWN_KEY = 'pharmacy.inference-cooldown.v1'
const sessionSchema = z.object({ token: tokenSchema, expiresAt: z.string().refine(value => Number.isFinite(Date.parse(value))) })
const refinementLabels: Record<string, string> = { strength: 'Dosage', form: 'Forme', presentation: 'Présentation', brand_name: 'Nom commercial', page: 'Autres présentations' }

// getRandomValues also works on HTTP LAN origins, where randomUUID is unavailable.
function randomId(): string {
  return Array.from(crypto.getRandomValues(new Uint8Array(16)), byte => byte.toString(16).padStart(2, '0')).join('')
}

export interface DisplayMessage {
  key: string
  role: 'user' | 'assistant'
  outcome: 'pending' | 'answered' | 'failed'
  text: string
  response?: PatientResponse
  errorCode?: string
}
export interface Snapshot {
  messages: DisplayMessage[]
  activeKey: string | null
  response: PatientResponse | null
  token: string | null
  expiresAt: string | null
  busy: boolean
  loading: boolean
  recoveryRequired: boolean
  error: ApiError | null
  retryText: string | null
  notice: string | null
  storageWarning: boolean
  cooldownUntil: number
}

function choiceLabel(message: Message, previous: PatientResponse | null): string {
  const action = message.payload?.action as ChatRequest | undefined
  if (action?.selections?.length) return action.selections.map(selection => {
    const record = previous?.medications.find(result => result.mention_index === selection.mention_index)?.candidates
      .find(candidate => candidate.source_record_id === selection.record_id)
    return record ? `Présentation choisie : ${record.brand_name} · ${record.dosage} · ${record.presentation}` : 'Présentation sélectionnée'
  }).join('\n')
  if (action?.refinements?.length) return action.refinements.map(item => item.field === 'page' ? 'Afficher d’autres présentations' : `${refinementLabels[item.field]} : ${item.value}`).join('\n')
  if (action?.reference_index != null) {
    const item = previous?.context?.reference_options.find(option => option.mention_index === action.reference_index)?.medication
    return item ? `À propos de : ${[item.name, item.strength, item.presentation].filter(Boolean).join(' · ')}` : 'Médicament précisé'
  }
  return message.outcome === 'failed' ? 'Choix non validé' : 'Choix de présentation'
}

function displays(view: Conversation): DisplayMessage[] {
  let previous: PatientResponse | null = null
  return view.messages.map(message => {
    if (message.role === 'assistant') {
      const response = responseSchema.safeParse(message.payload)
      if (!response.success) throw new ApiError('invalid_response')
      previous = response.data
      return { key: `server-${message.sequence}`, role: 'assistant', outcome: 'answered', text: message.text ?? '', response: response.data }
    }
    return { key: `server-${message.sequence}`, role: 'user', outcome: message.outcome,
      text: message.text ?? choiceLabel(message, previous),
      errorCode: typeof message.payload?.error_code === 'string' ? message.payload.error_code : undefined }
  })
}

function asError(error: unknown): ApiError { return error instanceof ApiError ? error : new ApiError('api_unreachable') }
const recoverable = new Set(['completion_unknown', 'request_failed', 'language_unavailable', 'language_timeout',
  'provider_timeout', 'provider_unreachable', 'provider_unavailable', 'provider_rate_limited', 'local_rate_limited'])

/** One active tab conversation. No transcript, request payload, or permanent history in browser storage. */
export class ConversationController {
  private state: Snapshot = { messages: [], activeKey: null, response: null, token: null, expiresAt: null,
    busy: false, loading: true, recoveryRequired: false, error: null, retryText: null, notice: null, storageWarning: false, cooldownUntil: 0 }
  private listeners = new Set<() => void>()
  private initialization: Promise<void> | null = null
  private storage: Storage | null = null
  private lastSequence = -1
  private undelivered: DisplayMessage | null = null
  private service: ConversationApi
  constructor(service: ConversationApi = api) {
    this.service = service
    try { this.storage = window.sessionStorage } catch { this.state.storageWarning = true }
  }
  getSnapshot = () => this.state
  subscribe = (listener: () => void) => { this.listeners.add(listener); return () => { this.listeners.delete(listener) } }
  private update(patch: Partial<Snapshot>) { this.state = { ...this.state, ...patch }; this.listeners.forEach(listener => listener()) }
  private persist() {
    try {
      if (this.state.token && this.state.expiresAt) this.storage?.setItem(SESSION_KEY, JSON.stringify({ token: this.state.token, expiresAt: this.state.expiresAt }))
      else this.storage?.removeItem(SESSION_KEY)
      this.storage?.setItem(COOLDOWN_KEY, String(this.state.cooldownUntil))
    } catch { this.update({ storageWarning: true }) }
  }
  private accept(view: Conversation) {
    const messages = displays(view)
    this.lastSequence = view.messages.at(-1)?.sequence ?? -1
    const latest = messages.findLast(message => message.role === 'assistant')
    if (latest && view.response) latest.response = view.response
    this.update({ messages: this.undelivered ? [...messages, this.undelivered] : messages, activeKey: latest?.key ?? null,
      response: view.response, token: view.session_id, expiresAt: view.expires_at_utc })
    this.persist()
  }
  expire() {
    if (this.state.busy) return // The backend decides whether an in-flight response renewed expiry.
    this.undelivered = null
    this.update({ messages: [], activeKey: null, response: null, token: null, expiresAt: null, recoveryRequired: false,
      error: null, retryText: null, notice: 'Cette conversation a expiré après 30 minutes d’inactivité. Vous pouvez commencer une nouvelle conversation.' })
    this.persist()
  }
  initialize() {
    if (this.initialization) return this.initialization
    this.initialization = this.loadInitial()
    return this.initialization
  }
  private async loadInitial() {
    let saved: z.infer<typeof sessionSchema> | null = null
    try {
      const text = this.storage?.getItem(SESSION_KEY)
      if (text) {
        const parsed = sessionSchema.safeParse(JSON.parse(text))
        if (parsed.success) saved = parsed.data
        else this.storage?.removeItem(SESSION_KEY)
      }
      const cooldown = Number(this.storage?.getItem(COOLDOWN_KEY))
      if (Number.isFinite(cooldown) && cooldown > Date.now() && cooldown < Date.now() + 604_800_000) this.update({ cooldownUntil: cooldown })
    } catch { this.update({ storageWarning: true }) }
    if (!saved) { this.update({ loading: false }); return }
    this.update({ token: saved.token, expiresAt: saved.expiresAt, loading: false })
    if (Date.parse(saved.expiresAt) <= Date.now()) { this.expire(); return }
    await this.recover()
  }
  private failureState(view: Conversation, error?: ApiError) {
    const pending = view.messages.some(message => message.outcome === 'pending')
    const latest = view.messages.findLast(message => message.role === 'user')
    if (pending) this.update({ recoveryRequired: true, error: new ApiError('request_in_progress', 409), retryText: null })
    else if (latest?.outcome === 'failed') {
      const code = typeof latest.payload?.error_code === 'string' ? latest.payload.error_code : 'request_failed'
      const failure = error ?? new ApiError(code, 0, recoverable.has(code))
      this.update({ recoveryRequired: false, error: failure, retryText: latest.text })
    } else this.update({ recoveryRequired: false, error: null, retryText: null })
  }
  async recover() {
    if (this.state.busy || !this.state.token) return
    this.update({ busy: true, notice: null })
    try {
      const view = await this.service.restore(this.state.token)
      this.accept(view); this.failureState(view)
      if (this.undelivered) this.update({ error: new ApiError(this.undelivered.errorCode ?? 'request_failed'),
        retryText: this.undelivered.text, recoveryRequired: false })
    } catch (cause) {
      const error = asError(cause)
      if (error.expired) { this.update({ busy: false }); this.expire() }
      else this.update({ error, recoveryRequired: true })
    } finally { this.update({ busy: false, loading: false }) }
  }
  async send(text: string) {
    const value = text.trim()
    if (!value || [...value].length > 2000 || !/[^\s\p{M}]/u.test(value)) return
    if (Date.now() < this.state.cooldownUntil) return
    await this.submit({ text: value }, value)
  }
  async choose(action: Omit<ChatRequest, 'request_id'>, label: string) { await this.submit(action, label) }
  async retry() { if (this.state.retryText && this.state.error?.retryable) await this.send(this.state.retryText) }
  private async submit(action: Omit<ChatRequest, 'request_id'>, label: string) {
    if (this.state.busy || this.state.recoveryRequired) return
    this.update({ busy: true, error: null, retryText: null, notice: null })
    let token = this.state.token
    const localKey = `local-${randomId()}`
    let optimisticAdded = false
    let beforeSequence = this.lastSequence
    try {
      if (!token) {
        const fresh = await this.service.create()
        this.accept(fresh); token = fresh.session_id
      }
      beforeSequence = this.lastSequence
      this.update({ messages: [...this.state.messages, { key: localKey, role: 'user', outcome: 'pending', text: label }] })
      optimisticAdded = true
      const body: ChatRequest = { ...action, request_id: randomId(),
        ...(action.text ? { session_id: token } : {}) }
      const response = await this.service.chat(body)
      if (!response.session_id || !response.session_expires_at_utc) throw new ApiError('invalid_response')
      this.undelivered = null
      this.update({ token: response.session_id, expiresAt: response.session_expires_at_utc, response,
        activeKey: localKey + '-answer', messages: [...this.state.messages.map(message => message.key === localKey ? { ...message, outcome: 'answered' as const } : message),
          { key: localKey + '-answer', role: 'assistant', outcome: 'answered', text: response.answer, response }] })
      this.persist()
      try {
        this.accept(await this.service.restore(response.session_id))
      } catch (cause) {
        const error = asError(cause)
        this.update({ error, recoveryRequired: true, retryText: null })
      }
    } catch (cause) {
      const error = asError(cause)
      if (error.retryAfter != null) {
        this.update({ cooldownUntil: Math.max(this.state.cooldownUntil, Date.now() + error.retryAfter * 1000) }); this.persist()
      }
      if (error.expired) { this.update({ busy: false }); this.expire(); return }
      this.update({ error, retryText: action.text ?? null,
        messages: optimisticAdded ? this.state.messages.map(message => message.key === localKey ? { ...message, outcome: 'failed', errorCode: error.code } : message)
          : [...this.state.messages, { key: localKey, role: 'user', outcome: 'failed', text: label, errorCode: error.code }] })
      if (token) {
        try {
          const view = await this.service.restore(this.state.token ?? token)
          const local = this.state.messages.find(message => message.key === localKey)
          this.accept(view)
          const serverSaved = view.messages.some(message => message.role === 'user' && message.sequence > beforeSequence && message.text === (action.text ?? null))
          if (optimisticAdded && local && !serverSaved && !view.messages.some(message => message.outcome === 'pending')) {
            // A network failure before core received the request must not erase the user's text.
            this.undelivered = local
            this.update({ messages: [...this.state.messages, local], error, retryText: action.text ?? null, recoveryRequired: error.uncertain })
          } else this.failureState(view, error)
        } catch (restoreCause) {
          if (asError(restoreCause).expired) { this.update({ busy: false }); this.expire() }
          else this.update({ recoveryRequired: true })
        }
      }
    } finally { this.update({ busy: false }) }
  }
  async reset(): Promise<boolean> {
    if (this.state.busy) return false
    this.update({ busy: true })
    try {
      if (this.state.token) {
        try { await this.service.reset(this.state.token) } catch (cause) { if (!asError(cause).expired) throw cause }
      }
      this.update({ messages: [], activeKey: null, response: null, token: null, expiresAt: null,
        recoveryRequired: false, error: null, retryText: null, notice: null })
      this.undelivered = null
      this.persist(); return true
    } catch (cause) { this.update({ error: asError(cause) }); return false }
    finally { this.update({ busy: false }) }
  }
}

export { conversationSchema }
