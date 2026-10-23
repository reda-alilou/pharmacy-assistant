import { z } from 'zod'

export const email = z.string().trim().toLowerCase().max(254).pipe(z.email())
export const password = z.string().min(12).max(128)
export const displayName = z.string().trim().min(1).max(80).refine(value => !/[\u0000-\u001f\u007f]/.test(value))
export const registerBody = z.object({ email, password, displayName }).strict()
export const loginBody = z.object({ email, password: z.string().min(1).max(128) }).strict()
export const profileBody = z.object({ displayName }).strict()
export const passwordBody = z.object({ currentPassword: z.string().min(1).max(128), password }).strict()
export const userSchema = z.object({ id: z.uuid(), email, displayName, role: z.enum(['analyst', 'admin']), createdAt: z.iso.datetime() }).strict()
export type User = z.infer<typeof userSchema>
export const sessionSchema = z.object({ user: userSchema.nullable(), csrfToken: z.string(), expiresAt: z.iso.datetime() }).strict()
export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public retryAfter?: number) { super(message) }
}
export function requireUser(user: User | null): User {
  if (!user) throw new ApiError(401, 'authentication_required', 'Connectez-vous pour continuer.')
  return user
}
export function requireRole(user: User | null, role: User['role']) {
  const authenticated = requireUser(user)
  if (authenticated.role !== role) throw new ApiError(403, 'forbidden', 'Accès non autorisé.')
  return authenticated
}
export function requireOwner(user: User | null, ownerId: string) {
  const authenticated = requireUser(user)
  if (authenticated.id !== ownerId) throw new ApiError(403, 'forbidden', 'Accès non autorisé.')
  return authenticated
}
