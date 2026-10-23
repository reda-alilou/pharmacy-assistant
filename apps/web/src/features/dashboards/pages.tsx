import { useEffect,useRef,useState,type PointerEvent } from 'react'
import { Link,useBlocker,useNavigate,useParams,useSearchParams } from 'react-router'
import { z } from 'zod'
import { useAccounts } from '@/features/accounts/account-context'
import { columnSchema,datasetRequest,useDatasetResource,versionDetailSchema,type Column } from '@/features/datasets/api'
import { Status } from '@/features/datasets/shared'
import { definitionSchema,type Source } from '@/features/analytics/contracts'
import { listSchema,resultSchema,savedSchema,type Result } from '@/features/analytics/api'
import { DefinitionControls,Filters,SourcePicker } from '@/features/analytics/controls'
import { Results } from '@/features/analytics/results'
import { SharingPanel } from '@/features/sharing/panel'
import { configurationSchema,dashboardsSchema,savedDashboardSchema,type Configuration,type Dashboard,type FilterValues,type Widget } from './contracts'
import { FilterEditor,ReaderFilters } from './filter-controls'

const emptyConfiguration:Configuration={algorithm:'cp4-v1',widgets:[],filters:[]}
const emptySource:Source={datasetId:'',versionId:'',search:'',filters:[]}
const responseSchema=z.object({result:resultSchema,columns:z.array(columnSchema)})
const message=(error:unknown)=>error instanceof Error?error.message:'Tableau de bord indisponible.'
function visual(kind:'aggregate'|'histogram'|'scatter',source=emptySource):Widget['definition']{
  const style={xLabel:'',yLabel:'',unit:'',precision:2,legend:true},common={algorithm:'cp3-v1' as const,source}
  return kind==='aggregate'?{...common,kind,style,measures:[{operation:'rows',column:null,label:'Lignes'}],groupBy:[],order:{by:'measure',index:0,direction:'desc'},limit:20,chart:'kpi'}:
    kind==='histogram'?{...common,kind,style,column:'',bins:10}:{...common,kind,style,x:'',y:'',pointLimit:500}
}
export function DashboardsPage(){
  const[page,setPage]=useState(1),resource=useDatasetResource('/dashboards?page='+page,dashboardsSchema)
  return <><p className="platform-eyebrow">Indicateurs et collaboration</p><h1>Mes tableaux de bord</h1><p>Vos tableaux de bord et ceux qui vous sont partagés. Les droits dataset et les droits de consultation des résultats restent distincts.</p><Link className="platform-primary" to="/tableaux/nouveau">Créer un tableau de bord</Link>{!resource.data?<Status error={resource.error}/>:<>{!resource.data.dashboards.length?<section className="platform-panel"><h2>Aucun tableau de bord</h2><p>Commencez vide ou ajoutez une visualisation issue d’une analyse enregistrée.</p></section>:resource.data.dashboards.map(dashboard=><article className="platform-panel" key={dashboard.id}><h2><Link to={'/tableaux/'+dashboard.id}>{dashboard.title}</Link></h2><p>{dashboard.description||'Aucune description.'}</p><p>{dashboard.widgetCount} widgets · {dashboard.access==='owner'?'vous êtes propriétaire':'partagé en lecture seule'} · révision {dashboard.revision}</p></article>)}<div className="dataset-pagination"><button type="button" disabled={page===1} onClick={()=>setPage(page-1)}>Tableaux précédents</button><span>Page {page}</span><button type="button" disabled={!resource.data.hasMore} onClick={()=>setPage(page+1)}>Tableaux suivants</button></div></>}</>
}
export function DashboardPage(){
  const{id}=useParams<{id:string}>(),[search]=useSearchParams(),resource=useDatasetResource(id?'/dashboards/'+id:null,savedDashboardSchema)
  if(id&&!resource.data)return <Status error={resource.error}/>
  return <DashboardEditor key={id??'new'} initial={resource.data?.dashboard} initialAnalysis={search.get('analysis')}/>
}
function DashboardEditor({initial,initialAnalysis}:{initial?:Dashboard;initialAnalysis:string|null}){
  const{session}=useAccounts(),navigate=useNavigate(),[saved,setSaved]=useState(initial),[editing,setEditing]=useState(!initial)
  const[title,setTitle]=useState(initial?.title??''),[description,setDescription]=useState(initial?.description??''),[configuration,setConfiguration]=useState<Configuration>(initial?.configuration??emptyConfiguration)
  const[baseline,setBaseline]=useState(JSON.stringify({title:initial?.title??'',description:initial?.description??'',configuration:initial?.configuration??emptyConfiguration}))
  const[selected,setSelected]=useState<string|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState(''),[deleting,setDeleting]=useState(false),[copyTitle,setCopyTitle]=useState('')
  const[values,setValues]=useState<FilterValues>([]),[preview,setPreview]=useState<{id:string;configuration:Configuration}|null>(null),[analysisPage,setAnalysisPage]=useState(1),[analysisId,setAnalysisId]=useState(initialAnalysis??'')
  const analyses=useDatasetResource(editing?'/analyses?page='+analysisPage:null,listSchema)
  const own=!saved||saved.access==='owner',key=JSON.stringify({title,description,configuration}),dirty=key!==baseline
  const skipBlock=useRef(false),grid=useRef<HTMLDivElement>(null)
  const blocker=useBlocker(()=>!skipBlock.current&&(dirty||busy))
  useEffect(()=>{if(blocker.state==='blocked'){if(window.confirm(busy?'Une opération est en cours et peut terminer côté serveur. Quitter et vérifier son résultat plus tard ?':'Des modifications ne sont pas enregistrées. Quitter sans les enregistrer ?'))blocker.proceed();else blocker.reset()}},[blocker,busy])
  useEffect(()=>{
    if(!dirty&&!busy)return
    const warn=(event:BeforeUnloadEvent)=>event.preventDefault()
    const beforeLogout=(event:Event)=>{if(!window.confirm(busy?'Une opération est en cours et peut terminer côté serveur. Se déconnecter et vérifier son résultat plus tard ?':'Des modifications ne sont pas enregistrées. Se déconnecter sans les enregistrer ?'))event.preventDefault()}
    window.addEventListener('beforeunload',warn);window.addEventListener('platform:before-logout',beforeLogout)
    return()=>{window.removeEventListener('beforeunload',warn);window.removeEventListener('platform:before-logout',beforeLogout)}
  },[dirty,busy])
  function change(next:Configuration){setConfiguration(next);setPreview(null);setValues([]);setError('');setNotice('')}
  function addWidget(widget:Widget){change({...configuration,widgets:[...configuration.widgets,widget]});setSelected(widget.id)}
  function duplicate(widget:Widget){
    const id=crypto.randomUUID()
    if(configuration.filters.some(filter=>filter.mappings.length+filter.mappings.filter(mapping=>mapping.widgetId===widget.id).length>20)){setError('La duplication dépasserait 20 correspondances dans un filtre. Réduisez les correspondances avant de dupliquer.');return}
    change({...configuration,widgets:[...configuration.widgets,{...structuredClone(widget),id,title:(widget.title+' · copie').slice(0,160)}],filters:configuration.filters.map(filter=>({...filter,mappings:[...filter.mappings,...filter.mappings.filter(mapping=>mapping.widgetId===widget.id).map(mapping=>({...mapping,widgetId:id}))]}))});setSelected(id)
  }
  async function addAnalysis(id=analysisId){
    if(!id)return
    setBusy(true);setError('')
    try{const response=await datasetRequest('/analyses/'+id,savedSchema),definition=definitionSchema.parse(response.analysis.definition)
      if(!['aggregate','histogram','scatter'].includes(definition.kind))throw new Error('Cette analyse ne contient pas une visualisation de dashboard. Créez une configuration graphique depuis ses recommandations ou choisissez une agrégation, un histogramme ou un nuage de points.')
      if(configuration.widgets.length>=20)throw new Error('20 widgets maximum.')
      addWidget({id:crypto.randomUUID(),title:response.analysis.title,description:response.analysis.description.slice(0,1000),definition:definition as Widget['definition'],width:6,height:5,variant:'standard'})
    }catch(error){setError(message(error))}finally{setBusy(false)}
  }
  function patchWidget(id:string,patch:Partial<Widget>){
    const previous=configuration.widgets.find(widget=>widget.id===id)
    const changedDataset=patch.definition&&previous&&patch.definition.source.datasetId!==previous.definition.source.datasetId
    change({...configuration,widgets:configuration.widgets.map(widget=>widget.id===id?{...widget,...patch}:widget),filters:changedDataset?configuration.filters.map(filter=>({...filter,mappings:filter.mappings.filter(mapping=>mapping.widgetId!==id)})):configuration.filters})
  }
  function move(id:string,direction:number){const index=configuration.widgets.findIndex(widget=>widget.id===id),target=index+direction;if(index<0||target<0||target>=configuration.widgets.length)return;const widgets=[...configuration.widgets],[widget]=widgets.splice(index,1);widgets.splice(target,0,widget!);change({...configuration,widgets});setNotice('Position '+(target+1)+' sur '+widgets.length+'.')}
  function reorder(id:string,targetId:string){const from=configuration.widgets.findIndex(widget=>widget.id===id),to=configuration.widgets.findIndex(widget=>widget.id===targetId);if(from<0||to<0||from===to)return;const widgets=[...configuration.widgets],[widget]=widgets.splice(from,1);widgets.splice(to,0,widget!);change({...configuration,widgets});setNotice('Widget déplacé en position '+(to+1)+'.')}
  function removeWidget(id:string){change({...configuration,widgets:configuration.widgets.filter(widget=>widget.id!==id),filters:configuration.filters.map(filter=>({...filter,mappings:filter.mappings.filter(mapping=>mapping.widgetId!==id)})).filter(filter=>filter.mappings.length)});if(selected===id)setSelected(null)}
  async function save(){
    setBusy(true);setError('');setNotice('')
    try{const valid=configurationSchema.safeParse(configuration);if(!title.trim()||!valid.success)throw new Error('Vérifiez le titre, les versions, les colonnes, les limites et les correspondances avant d’enregistrer.')
      const response=await datasetRequest(saved?'/dashboards/'+saved.id:'/dashboards',savedDashboardSchema,{method:saved?'PATCH':'POST',csrfToken:session!.csrfToken,body:{title,description,configuration:valid.data,...(saved?{revision:saved.revision}:{})}})
      setSaved(response.dashboard);setTitle(response.dashboard.title);setDescription(response.dashboard.description);setConfiguration(response.dashboard.configuration);setBaseline(JSON.stringify({title:response.dashboard.title,description:response.dashboard.description,configuration:response.dashboard.configuration}));setEditing(false);setSelected(null);setPreview(null);setValues([]);setNotice('Tableau de bord enregistré. Les sources restent épinglées. Toute autorisation de diffusion externe doit être renouvelée pour cette révision.')
      if(!saved){skipBlock.current=true;navigate('/tableaux/'+response.dashboard.id,{replace:true})}
    }catch(error){setError(message(error))}finally{setBusy(false)}
  }
  function discard(){if(dirty&&!window.confirm('Abandonner toutes les modifications non enregistrées ?'))return;const next=saved?{title:saved.title,description:saved.description,configuration:saved.configuration}:{title:'',description:'',configuration:emptyConfiguration};setTitle(next.title);setDescription(next.description);setConfiguration(next.configuration);setBaseline(JSON.stringify(next));setEditing(!saved);setSelected(null);setPreview(null);setValues([]);setError('');setNotice('Modifications abandonnées.')}
  async function copy(){if(!saved)return;setBusy(true);setError('');try{const response=await datasetRequest('/dashboards/'+saved.id+'/copy',savedDashboardSchema,{method:'POST',csrfToken:session!.csrfToken,body:{title:copyTitle}});skipBlock.current=true;navigate('/tableaux/'+response.dashboard.id)}catch(error){setError(message(error))}finally{setBusy(false)}}
  async function remove(){if(!saved)return;setBusy(true);setError('');try{await datasetRequest('/dashboards/'+saved.id,z.undefined(),{method:'DELETE',csrfToken:session!.csrfToken,body:{revision:saved.revision}});skipBlock.current=true;navigate('/tableaux')}catch(error){setError(message(error))}finally{setBusy(false)}}
  const current=configuration.widgets.find(widget=>widget.id===selected)
  return <><Link to="/tableaux">← Mes tableaux de bord</Link><p className="platform-eyebrow">{saved?`Révision ${saved.revision} · ${own?'propriétaire':'lecture seule'}`:'Nouveau tableau de bord privé'}</p><h1>{saved?saved.title:'Créer un tableau de bord'}</h1>{saved&&!editing&&<p>{saved.description}</p>}{dirty&&<p role="status">Modifications non enregistrées.</p>}{busy&&<p role="status">Opération en cours…</p>}{notice&&<p role="status">{notice}</p>}{error&&<p role="alert" className="platform-error">{error}</p>}
    <div className="platform-actions">{own&&saved&&!editing&&<button type="button" disabled={busy} onClick={()=>{setEditing(true);setValues([])}}>Modifier le tableau de bord</button>}{own&&editing&&<><button type="button" className="platform-primary" disabled={busy||!title.trim()} onClick={()=>{void save()}}>Enregistrer les modifications</button><button type="button" disabled={busy} onClick={discard}>Abandonner les modifications</button></>}</div>
    {editing&&own&&<fieldset className="dashboard-editor" disabled={busy}><legend className="sr-only">Édition du tableau de bord</legend><section className="platform-panel"><h2>Informations et widgets</h2><label>Titre du tableau de bord<input aria-label="Titre du tableau de bord" required maxLength={160} value={title} onChange={event=>{setTitle(event.target.value);setNotice('')}}/></label><label>Description du tableau de bord<textarea aria-label="Description du tableau de bord" maxLength={4000} value={description} onChange={event=>setDescription(event.target.value)}/></label><button type="button" disabled={configuration.widgets.length>=20} onClick={()=>addWidget({id:crypto.randomUUID(),title:'Nouveau widget',description:'',definition:visual('aggregate'),width:6,height:5,variant:'standard'})}>Ajouter un widget vide</button>
      <label>Analyse enregistrée<select aria-label="Analyse enregistrée" value={analysisId} onChange={event=>setAnalysisId(event.target.value)}><option value="">Choisir une analyse graphique</option>{analysisId&&!analyses.data?.analyses.some(analysis=>analysis.id===analysisId)&&<option value={analysisId}>Analyse sélectionnée</option>}{analyses.data?.analyses.map(analysis=><option key={analysis.id} value={analysis.id}>{analysis.title}{analysis.access==='shared'?' · partagée':''}</option>)}</select></label><button type="button" disabled={!analysisId||configuration.widgets.length>=20} onClick={()=>{void addAnalysis()}}>Ajouter cette analyse au tableau</button><div className="dataset-pagination"><button type="button" disabled={analysisPage===1} onClick={()=>setAnalysisPage(analysisPage-1)}>Analyses précédentes</button><span>Page {analysisPage}</span><button type="button" disabled={!analyses.data?.hasMore} onClick={()=>setAnalysisPage(analysisPage+1)}>Analyses suivantes</button></div>{analyses.error&&<p role="alert">{analyses.error}</p>}<p>Une visualisation ajoutée conserve une copie de sa configuration et de ses versions. Modifier l’analyse originale ne change pas ce tableau. Les droits sur les sources restent nécessaires.</p></section>
      {current&&<WidgetEditor key={current.id} widget={current} patch={patch=>patchWidget(current.id,patch)} preview={()=>setPreview({id:current.id,configuration:structuredClone(configuration)})}/>}
      <FilterEditor configuration={configuration} onChange={change}/>
    </fieldset>}
    {(!editing||preview)&&<ReaderFilters configuration={editing?preview!.configuration:configuration} values={values} onChange={setValues} reader={!own}/>}
    <section aria-label="Widgets du tableau de bord"><h2>{editing?'Disposition et prévisualisation':'Indicateurs et visualisations'}</h2><p id="dashboard-layout-help">{editing?'Déplacez les widgets par leur poignée ou les commandes Monter/Descendre. Les flèches de la poignée déplacent le widget ; celles du redimensionnement ajustent largeur/hauteur. Sur petit écran, l’ordre reste identique en une colonne.':'Les filtres sont appliqués avant le calcul. Chaque widget conserve ses sources, son périmètre et ses états de chargement/erreur.'}</p>{!configuration.widgets.length?<p>Aucun widget. Commencez vide ou ajoutez une analyse graphique.</p>:<div className="dashboard-grid" ref={grid}>{configuration.widgets.map((widget,index)=><article key={widget.id} data-widget-id={widget.id} className="dashboard-widget" style={{gridColumn:`span ${widget.width}`,gridRow:`span ${widget.height}`}} aria-label={widget.title}>
      <header><h3>{widget.title}</h3>{widget.description&&<p>{widget.description}</p>}{editing&&own&&<fieldset disabled={busy} className="dashboard-widget-actions"><legend className="sr-only">Actions du widget {widget.title}</legend><LayoutHandle widget={widget} grid={grid} reorder={reorder} resize={patch=>patchWidget(widget.id,patch)} move={direction=>move(widget.id,direction)}/><button type="button" disabled={index===0} onClick={()=>move(widget.id,-1)}>Monter {widget.title}</button><button type="button" disabled={index===configuration.widgets.length-1} onClick={()=>move(widget.id,1)}>Descendre {widget.title}</button><button type="button" onClick={()=>setSelected(widget.id)}>Configurer {widget.title}</button><button type="button" disabled={configuration.widgets.length>=20} onClick={()=>duplicate(widget)}>Dupliquer {widget.title}</button><button type="button" onClick={()=>{if(window.confirm('Supprimer ce widget du brouillon, ses correspondances et les filtres qui n’auront plus de cible ?'))removeWidget(widget.id)}}>Supprimer {widget.title}</button></fieldset>}</header>
      <div className="dashboard-widget-body" tabIndex={0} role="region" aria-label={'Contenu de '+widget.title}>{!editing&&saved?<WidgetResult scope={'Widget '+(index+1)+' : '+widget.title} widget={widget} configuration={configuration} saved={saved} values={values}/>:preview?.id===widget.id?<WidgetResult scope={'Widget '+(index+1)+' : '+widget.title} widget={widget} configuration={preview.configuration} values={values}/>:<p>Configurez puis prévisualisez ce widget. Aucun ancien résultat n’est présenté comme actuel.</p>}</div>
    </article>)}</div>}</section>
    {saved&&!editing&&<section className="platform-panel"><h2>Créer votre copie</h2><p>Une copie privée n’hérite d’aucun partage ni d’aucune autorisation de diffusion. Elle exige un accès dataset distinct à toutes les sources.</p><fieldset disabled={busy}><legend className="sr-only">Copie du tableau</legend><label>Titre de la copie<input aria-label="Titre de la copie" maxLength={160} value={copyTitle} onChange={event=>setCopyTitle(event.target.value)}/></label><button type="button" disabled={!copyTitle.trim()} onClick={()=>{void copy()}}>Créer une copie privée</button></fieldset></section>}
    {saved&&own&&!editing&&<><SharingPanel path={'/dashboards/'+saved.id} kind="dashboard"/><section className="platform-panel"><h2>Supprimer le tableau de bord</h2><p>Les analyses et datasets sont conservés. Les accès partagés à ce tableau seront retirés.</p>{deleting?<><button type="button" disabled={busy} className="dataset-danger" onClick={()=>{void remove()}}>Confirmer la suppression du tableau</button><button type="button" disabled={busy} onClick={()=>setDeleting(false)}>Annuler la suppression</button></>:<button type="button" disabled={busy} onClick={()=>setDeleting(true)}>Supprimer ce tableau de bord</button>}</section></>}</>
}
function WidgetEditor({widget,patch,preview}:{widget:Widget;patch:(value:Partial<Widget>)=>void;preview:()=>void}){
  const source=widget.definition.source,metadata=useDatasetResource(source.datasetId&&source.versionId?`/datasets/${source.datasetId}/versions/${source.versionId}`:null,versionDetailSchema),columns=metadata.data?.columns.map(column=>column.definition)??[]
  return <section className="platform-panel"><h2>Configurer : {widget.title}</h2><label>Titre du widget<input aria-label="Titre du widget" value={widget.title} maxLength={160} onChange={event=>patch({title:event.target.value})}/></label><label>Description du widget<textarea aria-label="Description du widget" value={widget.description} maxLength={1000} onChange={event=>patch({description:event.target.value})}/></label><div className="dataset-form-grid"><label>Largeur du widget<select aria-label="Largeur du widget" value={widget.width} onChange={event=>patch({width:Number(event.target.value) as Widget['width']})}><option value={4}>Un tiers (4/12)</option><option value={6}>Une moitié (6/12)</option><option value={12}>Toute la largeur (12/12)</option></select></label><label>Hauteur du widget<input aria-label="Hauteur du widget" type="number" min={3} max={12} value={widget.height} onChange={event=>patch({height:Number(event.target.value)})}/></label></div>
    <SourcePicker value={source} label="Source du widget" onChange={next=>patch({definition:next.datasetId===source.datasetId?{...widget.definition,source:next}:visual(widget.definition.kind,{...next,search:'',filters:[]}),variant:'standard'})}/>{metadata.error&&<p role="alert">{metadata.error}</p>}{metadata.data&&<><Filters source={source} columns={columns} onChange={source=>patch({definition:{...widget.definition,source}})} label="Widget"/><label>Type de widget<select aria-label="Type de widget" value={widget.definition.kind} onChange={event=>patch({definition:visual(event.target.value as Widget['definition']['kind'],source),variant:'standard'})}><option value="aggregate">Agrégats, KPI et graphiques</option><option value="histogram">Histogramme</option><option value="scatter">Nuage de points</option></select></label><DefinitionControls value={widget.definition} columns={columns} rightColumns={[]} onChange={definition=>{if(['aggregate','histogram','scatter'].includes(definition.kind))patch({definition:definition as Widget['definition'],variant:'standard'})}}/>{widget.definition.kind==='aggregate'&&widget.definition.chart==='pie'&&<label>Style circulaire<select aria-label="Style circulaire" value={widget.variant} onChange={event=>patch({variant:event.target.value as Widget['variant']})}><option value="standard">Disque</option><option value="donut">Anneau</option></select></label>}</>}
    <button type="button" disabled={!metadata.data} onClick={preview}>Prévisualiser ce widget</button><p>Changer de dataset retire les correspondances interactives de ce widget. Remappez-les explicitement ; les noms identiques ne créent aucune équivalence. Un filtre sans cible doit être remappé ou supprimé avant l’enregistrement.</p><p>Les réglages du graphique sont indépendants des dimensions de sa zone. Les tableaux exacts restent accessibles dans chaque widget.</p>
  </section>
}

// Keep browser concurrency at the backend's two-heavy-calculation bound.
let executing=0
const waiting:(()=>void)[]=[]
async function queued<T>(work:()=>Promise<T>):Promise<T>{if(executing>=2)await new Promise<void>(resolve=>waiting.push(resolve));else executing++;try{return await work()}finally{const next=waiting.shift();if(next)next();else executing--}}
function WidgetResult({widget,configuration,saved,values,scope}:{scope:string;widget:Widget;configuration:Configuration;saved?:Dashboard;values:FilterValues}){
  const{session}=useAccounts(),[nonce,setNonce]=useState(0),[state,setState]=useState<{key:string;result:Result|null;columns:Column[];error:string}>({key:'',result:null,columns:[],error:''})
  const key=JSON.stringify({widget,configuration,saved:saved?.revision,values,nonce}),csrf=session!.csrfToken
  useEffect(()=>{
    let active=true
    const timer=window.setTimeout(()=>{void queued(async()=>{
      if(!active)return
      try{const path=saved?`/dashboards/${saved.id}/widgets/${widget.id}/execute`:'/dashboards/preview',body=saved?{revision:saved.revision,values}:{configuration,widgetId:widget.id,values}
        const response=await datasetRequest(path,responseSchema,{method:'POST',csrfToken:csrf,body});if(active)setState({key,result:response.result,columns:response.columns,error:''})
      }catch(error){if(active)setState({key,result:null,columns:[],error:message(error)})}
    })},350)
    return()=>{active=false;window.clearTimeout(timer)}
  },[key,csrf,saved,widget.id,configuration,values])
  if(state.key!==key)return <p role="status">Calcul du widget en cours…</p>
  if(state.error)return <div role="alert"><p>{state.error}</p><button type="button" onClick={()=>setNonce(nonce+1)}>Réessayer le widget</button><p>Le résultat précédent a été retiré. Une source ou une autorisation peut être indisponible.</p></div>
  return state.result?<Results result={state.result} columns={state.columns} rightColumns={[]} onApply={()=>{}} onPage={()=>{}} variant={widget.variant} scope={scope}/>:null
}
function LayoutHandle({widget,grid,reorder,resize,move}:{widget:Widget;grid:React.RefObject<HTMLDivElement|null>;reorder:(id:string,target:string)=>void;resize:(patch:Partial<Widget>)=>void;move:(direction:number)=>void}){
  const gesture=useRef<{x:number;y:number;resize:boolean}|null>(null),[moving,setMoving]=useState<false|'move'|'resize'>(false)
  function down(event:PointerEvent<HTMLButtonElement>,resizing:boolean){if(event.button!==0||!window.matchMedia('(min-width: 900px)').matches)return;event.preventDefault();event.currentTarget.setPointerCapture(event.pointerId);gesture.current={x:event.clientX,y:event.clientY,resize:resizing};setMoving(resizing?'resize':'move')}
  function up(event:PointerEvent<HTMLButtonElement>){const start=gesture.current;gesture.current=null;setMoving(false);if(!start)return
    if(start.resize){const width=grid.current?.getBoundingClientRect().width??1,desired=widget.width+(event.clientX-start.x)/width*12,choices=[4,6,12] as const;resize({width:choices.reduce((best,value)=>Math.abs(value-desired)<Math.abs(best-desired)?value:best,widget.width),height:Math.min(12,Math.max(3,widget.height+Math.round((event.clientY-start.y)/80)))})}
    else{const target=document.elementFromPoint(event.clientX,event.clientY)?.closest<HTMLElement>('[data-widget-id]')?.dataset.widgetId;if(target)reorder(widget.id,target)}
  }
  const cancel=()=>{gesture.current=null;setMoving(false)}
  return <><button type="button" className="dashboard-handle" aria-describedby="dashboard-layout-help" aria-pressed={moving==='move'} onPointerDown={event=>down(event,false)} onPointerUp={up} onPointerCancel={cancel} onKeyDown={event=>{if(['ArrowUp','ArrowDown'].includes(event.key)){event.preventDefault();move(event.key==='ArrowUp'?-1:1)}}}>Déplacer {widget.title}</button><button type="button" className="dashboard-handle" aria-describedby="dashboard-layout-help" onPointerDown={event=>down(event,true)} onPointerUp={up} onPointerCancel={cancel} onKeyDown={event=>{
    if(['ArrowLeft','ArrowRight'].includes(event.key)){event.preventDefault();const widths=[4,6,12] as const,index=widths.indexOf(widget.width);resize({width:widths[Math.max(0,Math.min(2,index+(event.key==='ArrowLeft'?-1:1)))]})}
    if(['ArrowUp','ArrowDown'].includes(event.key)){event.preventDefault();resize({height:Math.max(3,Math.min(12,widget.height+(event.key==='ArrowUp'?-1:1)))})}
  }}>Redimensionner {widget.title}</button></>
}
