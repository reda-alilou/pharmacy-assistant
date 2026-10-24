import { useEffect, useState, type FormEvent } from 'react'
import { Link, Navigate, Outlet, useLocation, useNavigate } from 'react-router'
import { z } from 'zod'
import { AccountError, accountRequest, sessionSchema, userSchema } from './api'
import { useAccounts } from './account-context'

function message(error: unknown) { return error instanceof Error ? error.message : 'Le service est indisponible.' }
export function PlatformLayout() {
  const { session, loading, error, refresh, setSession } = useAccounts()
  const [logoutError, setLogoutError] = useState('')
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  useEffect(() => { document.title = 'Pharma Analyse'; window.scrollTo(0, 0) }, [location.pathname])
  async function logout() {
    if (!session) return
    // Editors can warn before session invalidation removes their protected view.
    if(!window.dispatchEvent(new Event('platform:before-logout',{cancelable:true})))return
    setBusy(true); setLogoutError('')
    try {
      await accountRequest('/auth/logout', z.undefined(), { method: 'POST', csrfToken: session.csrfToken })
      setSession(null)
      navigate('/connexion')
      await refresh()
    } catch (error) { setLogoutError(message(error)); await refresh() }
    finally { setBusy(false) }
  }
  return <div className="platform-shell"><a className="skip-link" href="#platform-main">Aller au contenu</a>
    <header className="platform-header"><Link className="platform-brand" to="/">Pharma Analyse</Link>
      <nav aria-label="Navigation principale"><Link to="/assistant">Assistant pharmacie</Link>
        {session?.user ? <><Link to="/espace">Mon espace</Link><Link to="/donnees">Mes données</Link><Link to="/analyses">Mes analyses</Link><Link to="/tableaux">Mes tableaux de bord</Link><Link to="/profil">Mon profil</Link>{session.user.role === 'admin' && <Link to="/administration">Administration</Link>}<button type="button" onClick={() => { void logout() }} disabled={busy}>{busy ? 'Déconnexion…' : 'Se déconnecter'}</button></>
          : <><Link to="/connexion">Connexion</Link><Link to="/inscription">Créer un compte</Link></>}
      </nav></header>
    <main id="platform-main" className="platform-main" tabIndex={-1}>
      {logoutError && <p role="alert" className="platform-error">{logoutError}</p>}
      {loading ? <p role="status">Vérification de la session…</p> : error ? <div role="alert"><p>{error}</p><button onClick={() => { void refresh() }}>Réessayer la connexion au service</button><p><Link to="/assistant">Ouvrir l’assistant pharmacie</Link></p></div> : <Outlet />}
    </main>
  </div>
}
export function Introduction() {
  const { session } = useAccounts()
  return <><p className="platform-eyebrow">Données pharmaceutiques · Observations sourcées</p><h1>Des données aux analyses, avec leur contexte.</h1>
    <p className="platform-lead">Un espace pour importer, explorer et comprendre les données pharmaceutiques. Les comptes, les CSV privés, l’exploration et les analyses reproductibles sont disponibles dès maintenant.</p>
    <div className="platform-actions"><Link className="platform-primary" to={session?.user ? '/espace' : '/inscription'}>{session?.user ? 'Accéder à mon espace' : 'Créer mon compte'}</Link><Link to="/assistant">Consulter l’assistant pharmacie</Link></div>
    <section className="platform-panel"><h2>Disponible aujourd’hui</h2><p>Créez un compte, gérez votre profil, importez un CSV privé et créez des analyses avec agrégations, graphiques et quatre fonctions avancées. L’assistant pharmacie reste accessible à tous, avec des conversations temporaires indépendantes des comptes.</p></section>
    <section className="platform-panel"><h2>Tableaux de bord et collaboration</h2><p>Les tableaux de bord interactifs et le partage en lecture seule sont disponibles avec un compte. Les administrateurs disposent d’un espace de supervision des comptes, datasets et activités.</p><p>Les prix de l’assistant sont des observations datées. Le stock n’est pas vérifié ; l’annuaire de Rabat est partiel.</p></section>
  </>
}
export function Protected({ admin = false }: { admin?: boolean }) {
  const { session } = useAccounts()
  const location = useLocation()
  if (!session?.user) return <Navigate to="/connexion" state={{ from: location.pathname+location.search }} replace />
  if (admin && session.user.role !== 'admin') return <><h1>Accès non autorisé</h1><p>Cette page est réservée aux administrateurs.</p><Link to="/espace">Retour à mon espace</Link></>
  return <Outlet />
}
export function AuthPage({ register = false }: { register?: boolean }) {
  const { session, setSession, refresh } = useAccounts()
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const requested:unknown=location.state?.from
  const next=typeof requested==='string'&&/^\/(?:espace|profil|administration|donnees(?:\/(?:importer|[a-f0-9-]{36}|imports\/[a-f0-9-]{36}))?|analyses(?:\/(?:nouvelle|[a-f0-9-]{36}))?|tableaux(?:\/(?:nouveau|[a-f0-9-]{36}))?)(?:\?[^#]*)?$/i.test(requested)?requested:'/espace'
  if (session?.user) return <Navigate to={next} replace />
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!session) { await refresh(); return }
    const form = new FormData(event.currentTarget)
    const body = { email: form.get('email'), password: form.get('password'), ...(register ? { displayName: form.get('displayName') } : {}) }
    setBusy(true); setError('')
    try {
      const result = await accountRequest(register ? '/auth/register' : '/auth/login', sessionSchema, { method: 'POST', body, csrfToken: session.csrfToken })
      setSession(result); navigate(next, { replace: true })
    } catch (error) { setError(message(error)); if (error instanceof AccountError && error.code === 'csrf_rejected') await refresh() }
    finally { setBusy(false) }
  }
  return <section className="platform-form-card"><h1>{register ? 'Créer un compte' : 'Connexion'}</h1>{location.state?.passwordChanged && <p role="status">Mot de passe modifié. Reconnectez-vous avec le nouveau mot de passe.</p>}<p>{register ? 'Votre compte analyste vous donne accès à votre espace personnel.' : 'Retrouvez votre espace personnel.'}</p>
    <form onSubmit={event => { void submit(event) }} aria-label={register ? 'Inscription' : 'Connexion'}>
      {register && <label>Nom affiché<input name="displayName" autoComplete="name" required maxLength={80} /></label>}
      <label>Adresse e-mail<input name="email" type="email" autoComplete="email" required maxLength={254} /></label>
      <label>Mot de passe<input name="password" type="password" autoComplete={register ? 'new-password' : 'current-password'} required minLength={register ? 12 : 1} maxLength={128} aria-describedby={register ? 'password-help' : undefined} /></label>
      {register && <p id="password-help">12 à 128 caractères. Utilisez un mot de passe unique.</p>}
      {error && <p role="alert" className="platform-error">{error}</p>}
      <button className="platform-primary" type="submit" disabled={busy || !session}>{busy ? 'En cours…' : register ? 'Créer mon compte' : 'Se connecter'}</button>
    </form><p>{register ? <Link to="/connexion">J’ai déjà un compte</Link> : <Link to="/inscription">Créer un compte</Link>}</p>
  </section>
}
export function Workspace() {
  const { session } = useAccounts()
  return <><p className="platform-eyebrow">Espace personnel</p><h1>Bonjour, {session?.user?.displayName}</h1><p>Votre compte {session?.user?.role === 'admin' ? 'administrateur' : 'analyste'} est actif.</p>
    <section className="platform-panel"><h2>Votre profil</h2><p>Modifiez votre nom affiché ou votre mot de passe.</p><Link to="/profil">Gérer mon profil</Link></section>
    <section className="platform-panel"><h2>Mes jeux de données</h2><p>Importez un CSV privé, validez les types et consultez ses lignes et versions.</p><Link to="/donnees">Ouvrir mes données</Link></section><section className="platform-panel"><h2>Mes analyses</h2><p>Calculez des indicateurs, inspectez les valeurs manquantes et atypiques, comparez des versions et enregistrez vos configurations privées.</p><Link to="/analyses">Ouvrir mes analyses</Link></section><section className="platform-panel"><h2>Mes tableaux de bord</h2><p>Regroupez vos visualisations, configurez des filtres explicites et partagez des résultats en lecture seule.</p><Link to="/tableaux">Ouvrir mes tableaux de bord</Link></section>
  </>
}
export function Profile() {
  const { session, setSession, refresh } = useAccounts()
  const user = session!.user!
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()
  async function submit(event: FormEvent<HTMLFormElement>, changePassword: boolean) {
    event.preventDefault(); const form = new FormData(event.currentTarget)
    const element = event.currentTarget
    setBusy(true); setNotice(''); setError('')
    try {
      if (changePassword) {
        await accountRequest('/auth/password', z.undefined(), { method: 'POST', csrfToken: session!.csrfToken, body: { currentPassword: form.get('currentPassword'), password: form.get('password') } })
        element.reset(); setSession(null); await refresh()
        navigate('/connexion', { state: { passwordChanged: true } })
      } else {
        const result = await accountRequest(`/users/${user.id}`, z.object({ user: userSchema }).strict(), { method: 'PATCH', csrfToken: session!.csrfToken, body: { displayName: form.get('displayName') } })
        setSession({ ...session!, user: result.user }); setNotice('Profil enregistré.')
      }
    } catch (error) { setError(message(error)); if (error instanceof AccountError && [401, 403].includes(error.status)) await refresh() }
    finally { setBusy(false) }
  }
  return <><h1>Mon profil</h1><p>{user.email} · {user.role === 'admin' ? 'Administrateur' : 'Analyste'}</p><p>L’adresse de connexion reste inchangée. Les conversations de l’assistant restent temporaires et séparées de ce compte.</p>
    {notice && <p role="status">{notice}</p>}{error && <p role="alert" className="platform-error">{error}</p>}
    <form className="platform-form-card" aria-label="Modifier le profil" onSubmit={event => { void submit(event, false) }}><h2>Informations personnelles</h2><label>Nom affiché<input key={user.id} name="displayName" defaultValue={user.displayName} required maxLength={80} autoComplete="name" /></label><button type="submit" className="platform-primary" disabled={busy}>Enregistrer le profil</button></form>
    <form className="platform-form-card" aria-label="Modifier le mot de passe" onSubmit={event => { void submit(event, true) }}><h2>Changer le mot de passe</h2><p>Cette action déconnecte toutes vos sessions. Reconnectez-vous avec le nouveau mot de passe.</p><label>Mot de passe actuel<input name="currentPassword" type="password" autoComplete="current-password" required maxLength={128} /></label><label>Nouveau mot de passe<input name="password" type="password" autoComplete="new-password" required minLength={12} maxLength={128} aria-describedby="new-password-help" /></label><p id="new-password-help">12 à 128 caractères.</p><button type="submit" className="platform-primary" disabled={busy}>Changer le mot de passe</button></form>
  </>
}
