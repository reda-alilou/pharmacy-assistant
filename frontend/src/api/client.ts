import { z } from 'zod'
import type { components } from './generated'
import { conversationSchema, responseSchema } from './schema'

export type ChatRequest = components['schemas']['ChatRequest']

export const errorMessages: Record<string, string> = {
  api_unreachable: 'Le service est inaccessible. Vérifiez votre connexion, puis vérifiez l’état de la conversation.',
  api_timeout: 'Le délai de réponse est dépassé. La demande a pu être traitée : vérifiez la conversation avant de la renvoyer.',
  invalid_response: 'La réponse du service ne peut pas être affichée. Vérifiez l’état de la conversation.',
  core_unavailable: 'Le service est temporairement indisponible. Votre demande a pu être traitée ; vérifiez la conversation avant de la renvoyer.',
  storage_unavailable: 'La base de données est temporairement indisponible. La demande n’a pas pu être terminée.',
  language_unavailable: 'Le service de compréhension est temporairement indisponible. Les choix déjà proposés restent utilisables.',
  language_timeout: 'La compréhension de votre demande a dépassé le délai autorisé. Elle a pu être comptabilisée.',
  language_invalid_response: 'La demande n’a pas pu être comprise correctement. Aucune information n’a été inventée.',
  provider_invalid_response: 'La demande n’a pas pu être comprise correctement. Vous pouvez la reformuler.',
  provider_generation_failed: 'La demande n’a pas pu être comprise correctement. Vous pouvez la reformuler.',
  provider_timeout: 'Le délai du service de compréhension est dépassé. La demande a pu être comptabilisée.',
  provider_unreachable: 'Le service de compréhension est inaccessible pour le moment.',
  provider_unavailable: 'Le service de compréhension est temporairement indisponible.',
  provider_rate_limited: 'La limite de demandes est atteinte. Attendez le délai indiqué avant de renvoyer une question.',
  local_rate_limited: 'Les demandes sont espacées. Attendez le délai indiqué avant de réessayer.',
  provider_daily_quota_exhausted: 'La limite quotidienne est atteinte. Les choix déjà proposés restent utilisables.',
  quota_state_unavailable: 'Le suivi des demandes est indisponible. Les nouvelles questions sont temporairement bloquées.',
  provider_refused: 'Cette demande n’a pas pu être traitée. Reformulez votre question.',
  session_expired: 'Cette conversation a expiré. Commencez une nouvelle conversation.',
  clarification_expired: 'Ce choix a expiré. Reprenez votre question dans une nouvelle conversation.',
  invalid_selection: 'Ce choix n’est plus valide. Actualisez la conversation pour retrouver les choix disponibles.',
  invalid_refinement: 'Cette précision ne fait pas partie des choix proposés.',
  invalid_reference: 'Choisissez un médicament proposé pour cette précision.',
  request_in_progress: 'Cette demande est encore en cours. Vérifiez son état avant un nouvel envoi.',
  request_conflict: 'L’état de cette demande a changé. Vérifiez la conversation avant de poursuivre.',
  conversation_conflict: 'La conversation a été modifiée. Son dernier état doit être rechargé.',
  invalid_request: 'Saisissez une question entre 1 et 2 000 caractères.',
  model_not_configured: 'Le service de compréhension n’est pas encore configuré.',
  service_configuration: 'Le service de compréhension doit être vérifié. Les choix déjà proposés restent utilisables.',
  request_failed: 'La demande n’a pas abouti. Vous pouvez vérifier son état puis la reformuler.',
  completion_unknown: 'Le résultat de cette demande est incertain. Elle a pu être comptabilisée ; aucun renvoi automatique n’a été effectué.',
}

export class ApiError extends Error {
  readonly code: string
  readonly status: number
  readonly retryable: boolean
  readonly retryAfter: number | null
  constructor(code: string, status = 0, retryable = true, retryAfter: number | null = null) {
    super(Object.hasOwn(errorMessages, code) ? errorMessages[code] : errorMessages.service_configuration)
    this.code = code; this.status = status; this.retryable = retryable; this.retryAfter = retryAfter
  }
  get expired() { return this.status === 410 || this.status === 401 }
  get uncertain() { return this.status === 0 || this.code === 'invalid_response' || this.code === 'core_unavailable' || this.code === 'request_in_progress' || this.code === 'request_conflict' || this.code === 'conversation_conflict' }
}

const errorSchema = z.object({ detail: z.object({ code: z.string(), retryable: z.boolean().optional(),
  retry_after_seconds: z.number().finite().nonnegative().nullable().optional() }) })

async function request<T>(method: string, path: string, schema: z.ZodType<T> | null, body?: ChatRequest, token?: string): Promise<T> {
  let response: Response
  try {
    response = await fetch('/api' + path, { method, cache: 'no-store', referrerPolicy: 'no-referrer',
      signal: AbortSignal.timeout(method === 'POST' && path === '/chat' ? 175_000 : 20_000),
      headers: { ...(body ? { 'Content-Type': 'application/json' } : {}), ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: body ? JSON.stringify(body) : undefined })
  } catch (error) {
    throw new ApiError(error instanceof DOMException && ['TimeoutError', 'AbortError'].includes(error.name) ? 'api_timeout' : 'api_unreachable')
  }
  if (response.status === 204 && response.ok && !schema) return undefined as T
  let value: unknown
  try {
    const text = await response.text()
    if (text.length > 8_000_000) throw new Error('Response too large')
    value = JSON.parse(text)
  } catch { throw new ApiError('invalid_response', response.status) }
  if (!response.ok) {
    const parsed = errorSchema.safeParse(value)
    const detail = parsed.success ? parsed.data.detail : null
    const headerDelay = Number(response.headers.get('Retry-After'))
    const delay = detail?.retry_after_seconds ?? (Number.isFinite(headerDelay) && headerDelay > 0 ? headerDelay : null)
    throw new ApiError(detail?.code ?? (response.status === 422 ? 'invalid_request' : 'core_unavailable'), response.status,
      detail?.retryable ?? [409, 429, 502, 503, 504].includes(response.status), delay)
  }
  const parsed = schema?.safeParse(value)
  if (!parsed?.success) throw new ApiError('invalid_response', response.status)
  return parsed.data
}

export const api = {
  create: () => request('POST', '/conversation', conversationSchema),
  restore: (token: string) => request('GET', '/conversation', conversationSchema, undefined, token),
  reset: (token: string) => request<void>('DELETE', '/conversation', null, undefined, token),
  chat: (body: ChatRequest) => request('POST', '/chat', responseSchema, body),
}
export type ConversationApi = typeof api
