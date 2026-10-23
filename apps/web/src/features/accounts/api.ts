import { z } from 'zod'

export const userSchema = z.object({ id: z.uuid(), email: z.email(), displayName: z.string(), role: z.enum(['analyst', 'admin']), createdAt: z.iso.datetime() }).strict()
export const sessionSchema = z.object({ user: userSchema.nullable(), csrfToken: z.string(), expiresAt: z.iso.datetime() }).strict()
export type AccountUser = z.infer<typeof userSchema>
export type AccountSession = z.infer<typeof sessionSchema>
export class AccountError extends Error {
  status: number
  code: string
  constructor(status: number, code: string, message: string) { super(message); this.status = status; this.code = code }
}
export async function accountRequest<T>(path: string, schema: z.ZodType<T>, options?: { method: string; body?: unknown; csrfToken: string }): Promise<T> {
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), 15000)
  try {
    const response = await fetch(`/platform-api${path}`, {
      credentials: 'same-origin', cache: 'no-store', signal: controller.signal,
      method: options?.method ?? 'GET',
      headers: options ? { 'Content-Type': 'application/json', 'X-CSRF-Token': options.csrfToken } : undefined,
      body: options ? JSON.stringify(options.body ?? {}) : undefined,
    })
    if (!response.ok) {
      const parsed = z.object({ error: z.object({ code: z.string(), message: z.string() }) }).safeParse(await response.json().catch(() => null))
      throw new AccountError(response.status, parsed.success ? parsed.data.error.code : 'service_error', parsed.success ? parsed.data.error.message : 'Le service de comptes est indisponible.')
    }
    return schema.parse(response.status === 204 ? undefined : await response.json())
  } catch (error) {
    if (error instanceof AccountError) throw error
    throw new AccountError(0, 'connection_error', 'Connexion interrompue. Vérifiez votre profil avant de répéter une modification.')
  } finally { window.clearTimeout(timer) }
}
let bootstrap: Promise<AccountSession> | null = null
export function loadSession() {
  if (!bootstrap) bootstrap = accountRequest('/auth/session', sessionSchema).finally(() => { bootstrap = null })
  return bootstrap
}
