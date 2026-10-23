import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router'
import { z } from 'zod'
import { useAccounts } from '@/features/accounts/account-context'
import { versionDetailSchema, useDatasetResource, type Column } from '@/features/datasets/api'
import { Status } from '@/features/datasets/shared'
import { definitionSchema, type Definition, type Source } from './contracts'
import { analysisSchema, analyticsRequest, KIND_NAMES, listSchema, resultSchema, savedSchema, templatesSchema, type Result } from './api'
import { DefinitionControls, Filters, SourcePicker } from './controls'
import { Results } from './results'
import { SharedAnalysis } from './shared'
import { SharingPanel } from '@/features/sharing/panel'

const emptySource:Source={datasetId:'',versionId:'',search:'',filters:[]}
const defaultStyle={xLabel:'',yLabel:'',unit:'',precision:2,legend:true}
function draft(kind:Definition['kind'],source:Source,columns:Column[]):Definition {
  const common={source,algorithm:'cp3-v1' as const},numeric=columns.filter(c=>['integer','decimal'].includes(c.type)),first=columns[0]?.id??''
  if(kind==='aggregate')return {...common,kind,measures:[{operation:'rows',column:null,label:'Lignes'}],groupBy:[],order:{by:'measure',index:0,direction:'desc'},limit:20,chart:'table',style:{...defaultStyle}}
  if(kind==='histogram')return {...common,kind,column:numeric[0]?.id??'',bins:10,style:{...defaultStyle}}
  if(kind==='scatter')return {...common,kind,x:numeric[0]?.id??'',y:numeric[1]?.id??'',pointLimit:500,style:{...defaultStyle}}
  if(kind==='missing')return {...common,kind,columns:first?[first]:[],groupBy:null,groupLimit:50}
  if(kind==='outliers')return {...common,kind,column:numeric[0]?.id??'',groupBy:null,factor:'1.5',minimumGroupSize:4,groupLimit:50}
  if(kind==='recommend')return {...common,kind,columns:numeric[0]?[numeric[0].id]:first?[first]:[]}
  return {...common,kind:'compare',right:{...source,filters:[...source.filters]},mappings:[],keys:[]}
}
export function AnalysesPage(){
  const[page,setPage]=useState(1),resource=useDatasetResource('/analyses?page='+page,listSchema)
  return <><p className="platform-eyebrow">Configurations privées et reproductibles</p><h1>Mes analyses</h1><p>Chaque analyse conserve ses versions, filtres, règles et choix graphiques. Le partage en lecture seule et les tableaux de bord conservent des autorisations distinctes des datasets.</p><Link className="platform-primary" to="/analyses/nouvelle">Créer une analyse</Link>
    {!resource.data?<Status error={resource.error}/>:<>{!resource.data.analyses.length?<section className="platform-panel"><h2>Aucune analyse enregistrée</h2><p>Créez une configuration, vérifiez son résultat puis enregistrez-la explicitement.</p></section>:resource.data.analyses.map(analysis=><article className="platform-panel" key={analysis.id}><h2><Link to={'/analyses/'+analysis.id}>{analysis.title}</Link></h2><p>{analysis.description||'Aucune description.'}</p><p>{analysis.definition?KIND_NAMES[analysis.definition.kind]:'Analyse partagée'} · {analysis.access==='shared'?'lecture seule':'vous êtes propriétaire'} · version épinglée · modifiée le {new Date(analysis.updatedAt).toLocaleString('fr-FR')}</p></article>)}<div className="dataset-pagination"><button type="button" disabled={page===1} onClick={()=>setPage(page-1)}>Analyses précédentes</button><span>Page {page}</span><button type="button" disabled={!resource.data.hasMore} onClick={()=>setPage(page+1)}>Analyses suivantes</button></div></>}
  </>
}
export function AnalysisPage(){
  const{id}=useParams<{id:string}>(),[search]=useSearchParams(),resource=useDatasetResource(id?'/analyses/'+id:null,savedSchema)
  if(id&&!resource.data)return <Status error={resource.error}/>
  if(resource.data?.analysis.access==='shared')return <><Link to="/analyses">← Mes analyses</Link><SharedAnalysis analysis={resource.data.analysis}/></>
  const kind=search.get('kind')
  return <Editor key={id??'new'} initial={resource.data?.analysis} initialKind={kind&&Object.hasOwn(KIND_NAMES,kind)?kind as Definition['kind']:'aggregate'} source={{...emptySource,datasetId:search.get('dataset')??'',versionId:search.get('version')??''}}/>
}
function Editor({initial,source,initialKind}:{initial?:z.infer<typeof analysisSchema>;source:Source;initialKind:Definition['kind']}){
  const{session}=useAccounts(),navigate=useNavigate()
  const[saved,setSaved]=useState(initial),[definition,setDefinition]=useState<Definition>(initial?.definition??draft(initialKind,source,[]))
  const[title,setTitle]=useState(initial?.title??''),[description,setDescription]=useState(initial?.description??'')
  const[baseline,setBaseline]=useState(JSON.stringify({title:initial?.title??'',description:initial?.description??'',definition:initial?.definition??draft(initialKind,source,[])}))
  const[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState(''),[deleting,setDeleting]=useState(false)
  const[result,setResult]=useState<{key:string;value:Result}|null>(null)
  const key=JSON.stringify(definition),dirty=JSON.stringify({title,description,definition})!==baseline
  const left=useDatasetResource(definition.source.datasetId&&definition.source.versionId?`/datasets/${definition.source.datasetId}/versions/${definition.source.versionId}`:null,versionDetailSchema)
  const right=useDatasetResource(definition.kind==='compare'&&definition.right.datasetId&&definition.right.versionId?`/datasets/${definition.right.datasetId}/versions/${definition.right.versionId}`:null,versionDetailSchema)
  const columns=left.data?.columns.map(c=>c.definition)??[],rightColumns=right.data?.columns.map(c=>c.definition)??[]
  const templates=useDatasetResource(left.data?'/analytics/templates':null,templatesSchema,0,{csrfToken:session!.csrfToken,body:definition.source})
  useEffect(()=>{if(!dirty)return;const warn=(event:BeforeUnloadEvent)=>{event.preventDefault()};window.addEventListener('beforeunload',warn);return()=>window.removeEventListener('beforeunload',warn)},[dirty])
  function change(value:Definition){setDefinition(value);setResult(null);setError('');setNotice('')}
  async function run(page=1){
    setBusy(true);setError('');setResult(null);setNotice('')
    try{const valid=definitionSchema.safeParse(definition);if(!valid.success){setError('Configuration incomplète. Choisissez les versions, colonnes et limites valides avant le calcul.');return}
      const value=await analyticsRequest('/analytics/execute',resultSchema,{method:'POST',csrfToken:session!.csrfToken,body:{definition:valid.data,page,pageSize:25}});setResult({key,value})
    }catch(error){setError(error instanceof Error?error.message:'Calcul indisponible.')}
    finally{setBusy(false)}
  }
  async function save(){
    if(!title.trim()||!result||result.key!==key)return
    setBusy(true);setError('');setNotice('')
    try{const body={title,description,definition,...(saved?{revision:saved.revision}:{})},response=await analyticsRequest(saved?'/analyses/'+saved.id:'/analyses',savedSchema,{method:saved?'PATCH':'POST',csrfToken:session!.csrfToken,body})
      setSaved(response.analysis);setTitle(response.analysis.title);setBaseline(JSON.stringify({title:response.analysis.title,description:response.analysis.description,definition:response.analysis.definition}));setNotice('Analyse enregistrée. Les versions et les règles restent épinglées.');setDeleting(false)
      if(!saved)navigate('/analyses/'+response.analysis.id,{replace:true})
    }catch(error){setError(error instanceof Error?error.message:'Enregistrement indisponible.')}
    finally{setBusy(false)}
  }
  async function remove(){
    if(!saved)return
    setBusy(true);setError('')
    try{await analyticsRequest('/analyses/'+saved.id,z.undefined(),{method:'DELETE',csrfToken:session!.csrfToken,body:{revision:saved.revision}});navigate('/analyses')}
    catch(error){setError(error instanceof Error?error.message:'Suppression indisponible.')}
    finally{setBusy(false)}
  }
  return <><Link to="/analyses">← Mes analyses</Link><h1>{saved?'Configurer l’analyse : '+saved.title:'Créer une analyse'}</h1><p>Calculs sur vos versions privées. Aucun tableau de bord ou partage n’est créé. Les prix sont des observations datées ; les statistiques ne comparent pas une valeur thérapeutique.</p>
    {dirty&&<p role="status">Modifications non enregistrées. Calculez pour vérifier, puis enregistrez explicitement.</p>}{notice&&<p role="status">{notice}</p>}{error&&<p role="alert" className="platform-error">{error}</p>}
    <fieldset className="analytics-controls" disabled={busy} aria-busy={busy}><legend className="sr-only">Configuration, calcul et sauvegarde de l’analyse</legend>
      <section className="platform-panel"><h2>Sources et périmètre</h2><SourcePicker value={definition.source} onChange={source=>change(source.datasetId!==definition.source.datasetId?draft(definition.kind,{...source,search:"",filters:[]},[]):{...definition,source})}/>{left.error&&<Status error={left.error}/>}<p>Changer de dataset réinitialise ses filtres et les réglages de calcul ; aucune équivalence de colonnes n’est déduite. Changer de version conserve les réglages pour revalidation par le serveur, sans remplacement implicite par une version récente.</p>{left.data&&<Filters key={definition.source.versionId} columns={columns} source={definition.source} onChange={source=>change({...definition,source})}/>}
        {definition.kind==='compare'&&<><SourcePicker value={definition.right} label="Droite" onChange={right=>change(right.datasetId!==definition.right.datasetId?{...definition,right:{...right,search:"",filters:[]},mappings:[],keys:[]}:{...definition,right})}/>{right.error&&<Status error={right.error}/>} {right.data&&<Filters key={definition.right.versionId} label="Droite" columns={rightColumns} source={definition.right} onChange={right=>change({...definition,right})}/>}</>}
      </section>
      <section className="platform-panel"><h2>Configuration de l’analyse</h2><label>Type d’analyse<select aria-label="Type d’analyse" disabled={!left.data} value={definition.kind} onChange={event=>change(draft(event.target.value as Definition['kind'],definition.source,columns))}>{Object.entries(KIND_NAMES).map(([kind,name])=><option key={kind} value={kind}>{name}</option>)}</select></label><p>Changer de type réinitialise ses réglages ; les filtres de la source sont conservés. Les résultats précédents sont retirés à chaque changement.</p><DefinitionControls value={definition} columns={columns} rightColumns={rightColumns} onChange={change}/><button type="button" className="platform-primary" disabled={!left.data||definition.kind==='compare'&&!right.data} onClick={()=>{void run()}}>{busy?'Traitement en cours…':'Calculer l’analyse'}</button></section>
      <section className="platform-panel"><h2>Modèles pharmaceutiques</h2><p>Ces modèles utilisent le même moteur que vos analyses. Ils sont proposés uniquement si les colonnes attendues existent ; les correspondances ne sont pas devinées.</p>{templates.data?templates.data.templates.map(template=><article className="analytics-recommendation" key={template.id}><h3>{template.title}</h3><p>{template.reason}</p><button type="button" disabled={!template.definition} onClick={()=>template.definition&&change(template.definition)}>Appliquer le modèle : {template.title}</button></article>):<p>{templates.error||'Choisissez une version pour vérifier les modèles disponibles.'}</p>}</section>
      {result&&result.key===key?<Results result={result.value} columns={columns} rightColumns={rightColumns} onApply={change} onPage={page=>{void run(page)}}/>:<section className="platform-panel"><h2>Résultat à calculer</h2><p>{busy?'Calcul en cours…':'Vérifiez les réglages puis cliquez sur « Calculer l’analyse ». Un ancien résultat n’est jamais présenté comme celui d’une configuration modifiée.'}</p></section>}
      <section className="platform-panel"><h2>Enregistrement privé et explicite</h2><label>Titre de l’analyse<input aria-label="Titre de l’analyse" value={title} maxLength={160} required onChange={event=>setTitle(event.target.value)}/></label><label>Description de l’analyse<textarea aria-label="Description de l’analyse" value={description} maxLength={4000} rows={3} onChange={event=>setDescription(event.target.value)}/></label><button type="button" className="platform-primary" disabled={!title.trim()||!result||result.key!==key} onClick={()=>{void save()}}>Enregistrer l’analyse</button><p>Réouverture : la configuration complète est conservée ; lancez le calcul pour consulter le résultat. Une nouvelle version de dataset ne remplace pas les références enregistrées. Aucun lien de partage n’est créé.</p>
        {saved&&<div className="analytics-delete">{!deleting?<button type="button" onClick={()=>setDeleting(true)}>Supprimer cette analyse</button>:<><p>La configuration sera supprimée et ses dépendances retirées. Les datasets et leurs versions seront conservés.</p><button type="button" className="dataset-danger" onClick={()=>{void remove()}}>Confirmer la suppression de l’analyse</button><button type="button" onClick={()=>setDeleting(false)}>Annuler la suppression de l’analyse</button></>}</div>}
      </section>
    </fieldset>
    {saved&&!dirty&&!busy&&<><p><Link to={'/tableaux/nouveau?analysis='+saved.id}>Ajouter une visualisation de cette analyse à un tableau de bord</Link></p><SharingPanel path={'/analyses/'+saved.id} kind="analysis"/></>}
  </>
}
