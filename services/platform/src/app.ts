import express, { type ErrorRequestHandler, type Request } from 'express'
import helmet from 'helmet'
import { ZodError } from 'zod'
import { ApiError, loginBody, passwordBody, profileBody, registerBody, requireOwner, requireRole, requireUser, sessionSchema } from './contracts.js'
import { csrfFor, dummyHash, equalSecret, hashPassword, newToken, verifyPassword } from './security.js'
import { ABSOLUTE_MS, type AccountStore, type Session } from './store.js'
import { datasetRoutes } from './datasets/routes.js'
import type { DatasetService } from './datasets/service.js'
import { AnalyticsService } from './analytics/service.js'
import { analyticsRoutes } from './analytics/routes.js'
import { DashboardService } from './dashboards/service.js'
import { dashboardRoutes } from './dashboards/routes.js'
import { SharingService } from './sharing/service.js'
import { sharingRoutes } from './sharing/routes.js'
import { AdminService } from './admin/service.js'
import { adminRoutes } from './admin/routes.js'

export type AppConfig = { origin: string; secureCookie: boolean; trustProxy: boolean }
type Context = { token: string | null; session: Session | null }
function cookieToken(req: Request) {
  const cookies = (req.headers.cookie ?? '').split(';').map(part => part.trim()).filter(part => part.startsWith('platform_session='))
  if (cookies.length !== 1) return null
  const value = cookies[0]!.slice('platform_session='.length)
  return /^[A-Za-z0-9_-]{43}$/.test(value) ? value : null
}
export function createApp(store: AccountStore, config: AppConfig, datasets?:DatasetService) {
  const app = express()
  const analytics=datasets?new AnalyticsService(datasets.pool):undefined
  const dashboards=datasets&&analytics?new DashboardService(datasets.pool,analytics):undefined
  app.disable('x-powered-by')
  if (config.trustProxy) app.set('trust proxy', 1) // Only the private Nginx hop; it replaces forwarded headers.
  app.use(helmet())
  app.use((_req, res, next) => { res.setHeader('Cache-Control', 'no-store'); next() })
  app.get('/health', (_req, res) => { res.json({ service: 'platform', status: 'ok' }) })
  app.get('/ready', async (_req, res) => { await store.ready();await datasets?.ready();await analytics?.ready();await dashboards?.ready(); res.json({ status: 'ready' }) })
  const accountJson=express.json({limit:'16kb',strict:true})
  const datasetJson=express.json({limit:'128kb',strict:true})
  app.use((req,res,next)=>/^\/(datasets|imports|analytics|analyses|dashboards|admin)(\/|$)/.test(req.path)?datasetJson(req,res,next):accountJson(req,res,next))
  const cookieOptions = { httpOnly: true, secure: config.secureCookie, sameSite: 'lax' as const, path: '/platform-api' }
  app.use(async (req, res, next) => {
    const token = cookieToken(req)
    const session = token ? await store.session(token) : null
    res.locals.auth = { token: session ? token : null, session } satisfies Context
    if (!['GET', 'HEAD', 'OPTIONS'].includes(req.method)) {
      if (req.get('Origin') !== config.origin || req.get('Sec-Fetch-Site') === 'cross-site')
        throw new ApiError(403, 'csrf_rejected', 'Origine de la demande non autorisée.')
      const upload=req.method==='POST' && req.path==='/imports' && req.is('application/octet-stream')
      if (!req.is('application/json') && !upload) throw new ApiError(415, 'json_required', 'Une demande JSON est requise (ou un fichier CSV sur la route d’import).')
      if (!session || !token || !equalSecret(req.get('X-CSRF-Token') ?? '', csrfFor(token)))
        throw new ApiError(403, 'csrf_rejected', 'La session a expiré. Actualisez la page avant de réessayer.')
    }
    next()
  })
  const context = (res: express.Response): Context => res.locals.auth
  const respondSession = (res: express.Response, token: string, session: Session) => {
    res.cookie('platform_session', token, { ...cookieOptions, maxAge: ABSOLUTE_MS })
    res.json(sessionSchema.parse({ ...session, csrfToken: csrfFor(token) }))
  }
  let passwordWork = 0
  async function boundedPasswordWork<T>(work: () => Promise<T>) {
    if (passwordWork >= 2) throw new ApiError(503, 'auth_busy', 'Authentification occupée. Réessayez dans un instant.', 1)
    passwordWork++
    try { return await work() } finally { passwordWork-- }
  }
  app.get('/auth/session', async (req, res) => {
    const auth = context(res)
    if (auth.session && auth.token) {
      res.json(sessionSchema.parse({ ...auth.session, csrfToken: csrfFor(auth.token) }))
      return
    }
    await store.throttle(`bootstrap:${req.ip}`, 120)
    const token = newToken()
    respondSession(res, token, await store.issue(token, null))
  })
  app.post('/auth/register', async (req, res) => {
    await store.throttle(`register:${req.ip}`, 10)
    const body = registerBody.parse(req.body)
    const encoded = await boundedPasswordWork(() => hashPassword(body.password))
    const user = await store.register(body.email, body.displayName, encoded)
    const token = newToken()
    res.status(201)
    respondSession(res, token, await store.issue(token, user.id, context(res).token!))
  })
  app.post('/auth/login', async (req, res) => {
    await store.throttle(`login-ip:${req.ip}`, 30)
    const body = loginBody.parse(req.body)
    await store.throttle(`login-account:${body.email}`, 10)
    const account = await store.account(body.email)
    const matches = await boundedPasswordWork(() => verifyPassword(body.password, account?.passwordHash ?? dummyHash))
    if (!matches || !account?.active) throw new ApiError(401, 'invalid_credentials', 'Adresse ou mot de passe incorrect.')
    const token = newToken()
    respondSession(res, token, await store.issue(token, account.user.id, context(res).token!, account.passwordHash))
  })
  app.post('/auth/logout', async (_req, res) => {
    await store.revoke(context(res).token!)
    res.clearCookie('platform_session', cookieOptions)
    res.status(204).end()
  })
  app.get('/users/:id', (req, res) => {
    const user = requireOwner(context(res).session?.user ?? null, req.params.id as string)
    res.json({ user })
  })
  app.patch('/users/:id', async (req, res) => {
    const user = requireOwner(context(res).session?.user ?? null, req.params.id as string)
    const body = profileBody.parse(req.body)
    res.json({ user: await store.profile(user.id, body.displayName) })
  })
  app.post('/auth/password', async (req, res) => {
    const user = requireUser(context(res).session?.user ?? null)
    await store.throttle(`password:${user.id}`, 10)
    const body = passwordBody.parse(req.body)
    const account = await store.account(user.email)
    const replacement = await boundedPasswordWork(async () => {
      if (!account?.active || !await verifyPassword(body.currentPassword, account.passwordHash))
        throw new ApiError(401, 'invalid_credentials', 'Mot de passe actuel incorrect.')
      return hashPassword(body.password)
    })
    await store.password(user.id, account!.passwordHash, replacement)
    res.clearCookie('platform_session', cookieOptions)
    res.status(204).end() // All sessions revoked; require a fresh login.
  })
  app.get('/admin/access', (_req, res) => {
    requireRole(context(res).session?.user ?? null, 'admin')
    res.json({ role: 'admin', administrationAvailable: Boolean(datasets) })
  })
  if(datasets) app.use(datasetRoutes(datasets,store))
  if(analytics)app.use(analyticsRoutes(analytics,store))
  if(dashboards)app.use(dashboardRoutes(dashboards,store))
  if(datasets)app.use(sharingRoutes(new SharingService(datasets.pool),store))
  if(datasets)app.use(adminRoutes(new AdminService(datasets.pool),store))
  app.use((_req, _res, next) => next(new ApiError(404, 'not_found', 'Ressource introuvable.')))
  const errors: ErrorRequestHandler = (error: unknown, req, res, _next) => {
    let safe: ApiError
    if (error instanceof ApiError) safe = error
    else if (error instanceof ZodError) safe = new ApiError(422, 'invalid_input', /^\/(datasets|imports|analytics|analyses|dashboards|admin)(\/|$)/.test(req.path)?'Champs invalides. Vérifiez les métadonnées, la configuration et les limites de filtre.':'Champs invalides. Vérifiez le nom, l’adresse et les règles de mot de passe.')
    else if (error && typeof error === 'object' && 'code' in error && error.code === '23505')
      safe = new ApiError(409, 'registration_unavailable', 'Inscription indisponible pour cette adresse. Essayez de vous connecter.')
    else if (error && typeof error === 'object' && 'type' in error && error.type === 'entity.too.large')
      safe = new ApiError(413, 'body_too_large', 'Demande trop volumineuse.')
    else if (error instanceof SyntaxError) safe = new ApiError(400, 'invalid_json', 'JSON invalide.')
    else safe = new ApiError(503, 'platform_unavailable', 'Le service est temporairement indisponible. Vérifiez l’état avant de répéter une modification.')
    if (safe.retryAfter) res.setHeader('Retry-After', safe.retryAfter)
    res.status(safe.status).json({ error: { code: safe.code, message: safe.message } })
  }
  app.use(errors)
  return app
}
