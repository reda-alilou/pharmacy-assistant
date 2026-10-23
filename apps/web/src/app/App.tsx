import { createBrowserRouter,createRoutesFromElements,Link,Route,RouterProvider } from 'react-router'
import { AccountProvider } from '@/features/accounts/context'
import { AdministrationPending, AuthPage, Introduction, PlatformLayout, Profile, Protected, Workspace } from '@/features/accounts/pages'
import './styles/platform.css'
import './styles/datasets.css'
import './styles/analytics.css'
import './styles/dashboards.css'
import { lazy,Suspense,useEffect } from 'react'
const Chat=lazy(()=>import('@/features/chat/components/chat'))

const DatasetsPage=lazy(()=>import('@/features/datasets/pages').then(module=>({default:module.DatasetsPage})))
const DatasetPage=lazy(()=>import('@/features/datasets/pages').then(module=>({default:module.DatasetPage})))
const ImportPage=lazy(()=>import('@/features/datasets/import').then(module=>({default:module.ImportPage})))
const UploadPage=lazy(()=>import('@/features/datasets/import').then(module=>({default:module.UploadPage})))
const AnalysesPage=lazy(()=>import('@/features/analytics/pages').then(module=>({default:module.AnalysesPage})))
const AnalysisPage=lazy(()=>import('@/features/analytics/pages').then(module=>({default:module.AnalysisPage})))
const DashboardsPage=lazy(()=>import('@/features/dashboards/pages').then(module=>({default:module.DashboardsPage})))
const DashboardPage=lazy(()=>import('@/features/dashboards/pages').then(module=>({default:module.DashboardPage})))

function AssistantPage() {
  useEffect(() => { document.title = 'Assistant pharmacie' }, [])
  return <Chat />
}

const router=createBrowserRouter(createRoutesFromElements(<>
    <Route path="/assistant" element={<AssistantPage />} />
    <Route element={<AccountProvider><PlatformLayout /></AccountProvider>}>
      <Route index element={<Introduction />} />
      <Route path="connexion" element={<AuthPage />} />
      <Route path="inscription" element={<AuthPage register />} />
      <Route element={<Protected />}><Route path="espace" element={<Workspace />} /><Route path="profil" element={<Profile />} />
        <Route path="donnees" element={<DatasetsPage />} /><Route path="donnees/importer" element={<UploadPage />} /><Route path="donnees/imports/:id" element={<ImportPage />} /><Route path="donnees/:id" element={<DatasetPage />} />
        <Route path="analyses" element={<AnalysesPage />} /><Route path="analyses/nouvelle" element={<AnalysisPage />} /><Route path="analyses/:id" element={<AnalysisPage />} />
        <Route path="tableaux" element={<DashboardsPage />} /><Route path="tableaux/nouveau" element={<DashboardPage />} /><Route path="tableaux/:id" element={<DashboardPage />} />
      </Route>
      <Route element={<Protected admin />}><Route path="administration" element={<AdministrationPending />} /></Route>
      <Route path="*" element={<><h1>Page introuvable</h1><Link to="/">Retour à l’accueil</Link></>} />
    </Route>
  </>))
export default function App() {
  return <Suspense fallback={<p role="status">Chargement de la page…</p>}><RouterProvider router={router}/></Suspense>
}
