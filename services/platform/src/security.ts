import { createHash, createHmac, randomBytes, scrypt, timingSafeEqual } from 'node:crypto'

export const digest = (value: string) => createHash('sha256').update(value).digest('hex')
export const newToken = () => randomBytes(32).toString('base64url')
export const csrfFor = (token: string) => createHmac('sha256', token).update('platform-csrf-v1').digest('base64url')
export function equalSecret(a: string, b: string) {
  const first = Buffer.from(a), second = Buffer.from(b)
  return first.length === second.length && timingSafeEqual(first, second)
}
function derive(password: string, salt: string) {
  return new Promise<Buffer>((resolve, reject) => scrypt(password, salt, 64,
    { N: 131072, r: 8, p: 1, maxmem: 160 * 1024 * 1024 }, (error, key) => error ? reject(error) : resolve(key)))
}
export async function hashPassword(password: string) {
  const salt = randomBytes(16).toString('hex')
  return `scrypt-v1$${salt}$${(await derive(password, salt)).toString('hex')}`
}
export async function verifyPassword(password: string, encoded: string) {
  const [version, salt, expected] = encoded.split('$')
  if (version !== 'scrypt-v1' || !salt || !expected || !/^[a-f0-9]{128}$/.test(expected)) return false
  return equalSecret((await derive(password, salt)).toString('hex'), expected)
}
// Equal-cost verification for unknown accounts, without hashing during startup.
export const dummyHash = `scrypt-v1$00000000000000000000000000000000$${'0'.repeat(128)}`
