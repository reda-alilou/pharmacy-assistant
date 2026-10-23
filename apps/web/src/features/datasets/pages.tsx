import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router'
import { z } from 'zod'
import { useAccounts } from '@/features/accounts/account-context'
import { datasetRequest, dependenciesSchema, detailSchema, listSchema, rowsSchema, TYPE_LABELS, useDatasetResource, versionDetailSchema, versionSchema, type Column, type DataQuery, type Dataset, type Filter, type Metadata } from './api'
import { Cell, MetadataFields, Status } from './shared'

export function DatasetsPage(){
  const[archived,setArchived]=useState(false),[page,setPage]=useState(1)
  const resource=useDatasetResource(`/datasets?archived=${archived}&page=${page}`,listSchema)
  return <><p className="platform-eyebrow">Espace de données privé</p><h1>Mes jeux de données</h1><p>Vous êtes propriétaire des fichiers importés ici. Le partage sera ajouté à une prochaine étape.</p><div className="platform-actions"><Link className="platform-primary" to="/donnees/importer">Importer un CSV</Link><label className="dataset-checkbox"><input type="checkbox" checked={archived} onChange={event=>{setArchived(event.target.checked);setPage(1)}}/>Afficher les archives</label></div>
    {!resource.data?<Status error={resource.error}/>:<>{!resource.data.datasets.length?<section className="platform-panel"><h2>{archived?'Aucune archive':'Aucun jeu de données'}</h2><p>{archived?'Vos jeux de données archivés apparaîtront ici.':'Importez un CSV pour consulter ses lignes, ses colonnes et ses versions.'}</p></section>:<div className="dataset-list">{resource.data.datasets.map(dataset=><article className="platform-panel" key={dataset.id}><h2><Link to={'/donnees/'+dataset.id}>{dataset.title}</Link></h2><p>{dataset.description||'Aucune description.'}</p><p>{dataset.category&&dataset.category+' · '}{dataset.versionCount} version(s) · {dataset.archived?'Archivé':'Privé'} · Modifié le {new Date(dataset.updatedAt).toLocaleDateString('fr-FR')}</p></article>)}</div>}<div className="dataset-pagination"><button disabled={page===1} onClick={()=>setPage(page-1)}>Page précédente</button><span>Page {page}</span><button disabled={!resource.data.hasMore} onClick={()=>setPage(page+1)}>Page suivante</button></div></>}
  </>
}
const tabs=[['overview','Vue d’ensemble'],['data','Données'],['columns','Colonnes'],['analysis','Analyse'],['quality','Qualité'],['versions','Versions']] as const
export function DatasetPage(){
  const{id}=useParams<{id:string}>(),[search,setSearch]=useSearchParams(),[nonce,setNonce]=useState(0)
  const detail=useDatasetResource(id?'/datasets/'+id:null,detailSchema,nonce)
  if(!detail.data)return <Status error={detail.error}/>
  const dataset=detail.data.dataset
  const versionId=search.get('version')??detail.data.versions[0]?.id
  const active=tabs.some(([tab])=>tab===search.get('tab'))?search.get('tab')!:'overview'
  const tab=(value:string)=>setSearch(current=>{current.set('tab',value);return current})
  return <><Link to="/donnees">← Mes jeux de données</Link><h1>{dataset.title}</h1><p>{dataset.archived?'Archivé · ':''}Privé · Propriétaire : {dataset.ownerName} · {dataset.versionCount} version(s)</p>
    <div className="platform-actions">{!dataset.archived&&<Link className="platform-primary" to={'/donnees/importer?dataset='+id}>Ajouter une version CSV</Link>}<label>Version consultée<select aria-label="Version consultée" value={versionId} onChange={event=>setSearch(current=>{current.set('version',event.target.value);return current})}>{versionId&&!detail.data.versions.some(version=>version.id===versionId)&&<option value={versionId}>Version de l’URL</option>}{detail.data.versions.map(version=><option key={version.id} value={version.id}>Version {version.number} · {version.filename}</option>)}</select></label></div>
    <nav className="dataset-tabs" aria-label="Vues du jeu de données">{tabs.map(([key,label])=><button type="button" key={key} aria-current={active===key?'page':undefined} onClick={()=>tab(key)}>{label}</button>)}</nav>
    {versionId&&active==='analysis'&&<section className="platform-panel"><h2>Analyser cette version</h2><p>Agrégations, modèles pharmaceutiques, valeurs manquantes, signalements IQR, recommandations et comparaison explicite. Les configurations peuvent être enregistrées en privé.</p><Link className="platform-primary" to={`/analyses/nouvelle?dataset=${dataset.id}&version=${versionId}`}>Créer une analyse de cette version</Link></section>}
    {active==='overview'&&<Overview key={dataset.revision} dataset={dataset} refresh={()=>setNonce(nonce+1)}/>}
    {versionId&&active==='data'&&<DataTable key={versionId} datasetId={dataset.id} versionId={versionId}/>}
    {versionId&&(active==='columns'||active==='quality')&&<ColumnProfiles datasetId={dataset.id} versionId={versionId} quality={active==='quality'}/>}
    {active==='versions'&&<Versions datasetId={dataset.id} count={dataset.versionCount} onSelect={version=>setSearch({version,tab:'data'})}/>}
  </>
}
function Overview({dataset,refresh}:{dataset:Dataset;refresh:()=>void}){
  const{session}=useAccounts(),navigate=useNavigate()
  const[metadata,setMetadata]=useState<Metadata>({title:dataset.title,description:dataset.description,category:dataset.category,source:dataset.source,observationDate:dataset.observationDate})
  const[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState(''),[dependencies,setDependencies]=useState<z.infer<typeof dependenciesSchema>|null>(null),[confirmTitle,setConfirmTitle]=useState('')
  const stored:Metadata={title:dataset.title,description:dataset.description,category:dataset.category,source:dataset.source,observationDate:dataset.observationDate}
  const dirty=JSON.stringify(stored)!==JSON.stringify(metadata)
  async function update(archive:boolean){
    setBusy(true);setError('');setNotice('')
    try{await datasetRequest('/datasets/'+dataset.id,detailSchema,{method:'PATCH',csrfToken:session!.csrfToken,body:{...metadata,archived:archive,revision:dataset.revision}});setNotice('Modifications enregistrées.');refresh()}
    catch(error){setError(error instanceof Error?error.message:'Modification indisponible.')}
    finally{setBusy(false)}
  }
  async function inspectDelete(){
    setBusy(true);setError('')
    try{setDependencies(await datasetRequest('/datasets/'+dataset.id+'/dependencies',dependenciesSchema))}
    catch(error){setError(error instanceof Error?error.message:'Vérification indisponible.')}
    finally{setBusy(false)}
  }
  async function remove(){
    if(!dependencies)return
    setBusy(true);setError('')
    try{await datasetRequest('/datasets/'+dataset.id,z.undefined(),{method:'DELETE',csrfToken:session!.csrfToken,body:{revision:dependencies.revision,confirmTitle}});navigate('/donnees')}
    catch(error){setError(error instanceof Error?error.message:'Suppression indisponible.')}
    finally{setBusy(false)}
  }
  return <>{error&&<p role="alert" className="platform-error">{error}</p>}{notice&&<p role="status">{notice}</p>}<section className="platform-panel"><h2>Informations et provenance</h2><p>Créé le {new Date(dataset.createdAt).toLocaleString('fr-FR')}. La source et la date d’observation sont déclarées par le propriétaire ; elles ne prouvent pas une donnée actuelle.</p><form onSubmit={event=>{event.preventDefault();void update(dataset.archived)}}><MetadataFields value={metadata} onChange={setMetadata} disabled={busy}/><button type="submit" className="platform-primary" disabled={busy}>Enregistrer les métadonnées</button></form></section>
    <section className="platform-panel"><h2>{dataset.archived?'Restaurer dans mon espace':'Archiver'}</h2><p>L’archivage masque ce jeu de données de la liste normale tout en conservant ses versions et ses dépendances.</p>{dirty&&<p>Enregistrez les métadonnées avant l’archivage, ou <button type="button" disabled={busy} onClick={()=>setMetadata(stored)}>Annuler les modifications des métadonnées</button>.</p>}<button type="button" disabled={busy||dirty} onClick={()=>{void update(!dataset.archived)}}>{dataset.archived?'Restaurer le jeu de données':'Archiver le jeu de données'}</button></section>
    <section className="platform-panel"><h2>Suppression définitive</h2><p>La suppression retire toutes les versions et leurs lignes. Les dépendances et les partages doivent être examinés avant confirmation.</p><button type="button" disabled={busy} onClick={()=>{void inspectDelete()}}>Vérifier les dépendances avant suppression</button>
      {dependencies&&<div className="dataset-delete-review"><h3>Confirmer la suppression</h3><p>{dependencies.versionCount} version(s) seront supprimées. {dependencies.dependencies.filter(dependency=>dependency.kind==='share').length} partage(s), {dependencies.dependencies.filter(dependency=>dependency.kind!=='share').length} analyse(s)/tableau(x) dépendant(s).</p>{dependencies.dependencies.map(dependency=><p key={dependency.resourceId}>{dependency.kind} : {dependency.label}</p>)}{!dependencies.canDelete?<p role="alert">Suppression bloquée : retirez ou migrez explicitement les dépendances. Les workflows d’analyses et de partage ne sont pas encore disponibles.</p>:<><label>Recopiez le titre pour confirmer<input value={confirmTitle} onChange={event=>setConfirmTitle(event.target.value)}/></label><button type="button" className="dataset-danger" disabled={busy||confirmTitle!==dependencies.title} onClick={()=>{void remove()}}>Supprimer définitivement toutes les versions</button></>}<button type="button" onClick={()=>{setDependencies(null);setConfirmTitle('')}} disabled={busy}>Annuler la suppression</button></div>}
    </section></>
}
function Versions({datasetId,count,onSelect}:{datasetId:string;count:number;onSelect:(id:string)=>void}){
  const[page,setPage]=useState(1)
  const schema=z.object({versions:z.array(versionSchema),total:z.number(),page:z.number()})
  // Stable schema identity is important to avoid re-fetching after each render.
  const[contract]=useState(()=>schema)
  const resource=useDatasetResource(`/datasets/${datasetId}/versions?page=${page}`,contract)
  if(!resource.data)return <Status error={resource.error}/>
  return <section className="platform-panel"><h2>Historique des imports</h2><p>Les versions publiées sont immuables. Choisir une version antérieure ne remplace aucune donnée.</p>{resource.data.versions.map(version=><article className="dataset-version" key={version.id}><h3>Version {version.number}</h3><p>{version.filename} · {version.rowCount} lignes · {version.columnCount} colonnes · {new Date(version.createdAt).toLocaleString('fr-FR')}</p><p className="dataset-hash">SHA-256 : {version.sourceSha256}</p><button type="button" onClick={()=>onSelect(version.id)}>Consulter la version {version.number}</button></article>)}<div className="dataset-pagination"><button disabled={page===1} onClick={()=>setPage(page-1)}>Versions précédentes</button><span>Page {page}</span><button disabled={page*25>=count} onClick={()=>setPage(page+1)}>Versions suivantes</button></div></section>
}
function ColumnProfiles({datasetId,versionId,quality}:{datasetId:string;versionId:string;quality:boolean}){
  const resource=useDatasetResource(`/datasets/${datasetId}/versions/${versionId}`,versionDetailSchema)
  if(!resource.data)return <Status error={resource.error}/>
  return <section className="platform-panel"><h2>{quality?'Qualité : profil initial':'Colonnes et statistiques descriptives'}</h2><p>Version {resource.data.version.number} · {resource.data.version.rowCount} lignes. Les comptes et statistiques portent sur la version entière, sans filtre. Les valeurs manquantes sont exclues des minimums, maximums et moyennes. Distincts compte uniquement les valeurs présentes. Une moyenne entre médicaments ne mesure pas leur valeur thérapeutique.</p>{quality&&<p>Ce profil de complétude accompagne l’import. Les analyses avancées des valeurs manquantes, les signalements IQR et la comparaison sont accessibles depuis l’onglet Analyse.</p>}
    <div className="dataset-table-wrap" tabIndex={0} role="region" aria-label="Profil des colonnes"><table><caption>Profil de la version {resource.data.version.number}</caption><thead><tr><th scope="col">Colonne</th><th scope="col">Type</th><th scope="col">Présents</th><th scope="col">Manquants</th><th scope="col">Complétude</th><th scope="col">Distincts</th>{!quality&&<><th scope="col">Minimum</th><th scope="col">Maximum</th><th scope="col">Moyenne numérique</th></>}</tr></thead><tbody>{resource.data.columns.map(({definition:column,profile})=><tr key={column.id}><th scope="row">{column.name}</th><td>{TYPE_LABELS[column.type]}</td><td>{profile.present}</td><td>{profile.missing}</td><td>{(100*profile.present/profile.total).toLocaleString('fr-FR',{maximumFractionDigits:2})} %</td><td>{profile.distinct}</td>{!quality&&<><td><Cell value={profile.minimum}/></td><td><Cell value={profile.maximum}/></td><td>{profile.mean??'Sans objet'}</td></>}</tr>)}</tbody></table></div>
  </section>
}
const ALL_OPS:Record<string,string>={contains:'Contient',equals:'Égal à',starts_with:'Commence par',in:'Valeurs sélectionnées (OU)',gt:'Supérieur à',gte:'Supérieur ou égal à',lt:'Inférieur à',lte:'Inférieur ou égal à',between:'Entre deux valeurs',before:'Avant',after:'Après',missing:'Manquant',present:'Présent'}
function operations(column?:Column){return !column?[]:['equals','in',...(column.type==='text'?['contains','starts_with']:['integer','decimal'].includes(column.type)?['gt','gte','lt','lte','between']:['date','datetime'].includes(column.type)?['before','after','between']:[]),'missing','present']}
function DataTable({datasetId,versionId}:{datasetId:string;versionId:string}){
  const version=useDatasetResource(`/datasets/${datasetId}/versions/${versionId}`,versionDetailSchema)
  if(!version.data)return <Status error={version.error}/>
  return <Explore key={versionId} datasetId={datasetId} version={version.data}/>
}
function Explore({datasetId,version}:{datasetId:string;version:z.infer<typeof versionDetailSchema>}){
  const{session}=useAccounts(),columns=version.columns.map(column=>column.definition)
  const[query,setQuery]=useState<DataQuery>({page:1,pageSize:25,search:'',filters:[],sort:null})
  const[search,setSearch]=useState(''),[original,setOriginal]=useState(false),[columnId,setColumnId]=useState(columns[0]?.id??''),[op,setOp]=useState('equals'),[value,setValue]=useState(''),[second,setSecond]=useState('')
  const column=columns.find(column=>column.id===columnId)
  const resource=useDatasetResource(`/datasets/${datasetId}/versions/${version.version.id}/rows`,rowsSchema,0,{csrfToken:session!.csrfToken,body:query})
  function addFilter(event:FormEvent){
    event.preventDefault()
    const filter:Filter={column:columnId,op,values:['missing','present'].includes(op)?[]:op==='in'?value.split('\n'):op==='between'?[value,second]:[value]}
    setQuery(current=>({...current,page:1,filters:[...current.filters,filter]}));setValue('');setSecond('')
  }
  const valueInput=(label:string,current:string,change:(value:string)=>void)=>column?.type==='boolean'&&op!=='in'?<label>{label}<select aria-label={label} value={current} required onChange={event=>change(event.target.value)}><option value="">Choisir</option><option value="true">true</option><option value="false">false</option></select></label>:<label>{label}<input type={column?.type==='date'?'date':'text'} value={current} onChange={event=>change(event.target.value)} placeholder={column?.type==='datetime'?'2026-10-23T10:30:00Z':undefined}/></label>
  return <section className="platform-panel"><h2>Données · Version {version.version.number}</h2><p>{version.version.rowCount} lignes · {version.version.columnCount} colonnes. Recherche, filtres et tri sont appliqués à la version entière sur le serveur.</p>
    <form className="dataset-search" onSubmit={event=>{event.preventDefault();setQuery(current=>({...current,page:1,search}))}}><label>Rechercher dans toutes les colonnes<input value={search} maxLength={200} onChange={event=>setSearch(event.target.value)}/></label><button type="submit">Rechercher</button></form>
    <form className="dataset-filter-builder" onSubmit={addFilter} aria-label="Ajouter un filtre"><h3>Filtrer les lignes</h3><div className="dataset-form-grid"><label>Colonne du filtre<select aria-label="Colonne du filtre" value={columnId} onChange={event=>{setColumnId(event.target.value);setOp('equals');setValue('');setSecond('')}}>{columns.map(column=><option key={column.id} value={column.id}>{column.name} ({TYPE_LABELS[column.type]})</option>)}</select></label><label>Opération<select aria-label="Opération" value={op} onChange={event=>{setOp(event.target.value);setValue('');setSecond('')}}>{operations(column).map(op=><option value={op} key={op}>{ALL_OPS[op]}</option>)}</select></label>
      {!['missing','present'].includes(op)&&(op==='in'?<label>Valeurs sélectionnées (une par ligne)<textarea value={value} onChange={event=>setValue(event.target.value)} rows={3}/></label>:valueInput('Valeur du filtre',value,setValue))}{op==='between'&&valueInput('Borne supérieure',second,setSecond)}</div><p>Les filtres se combinent avec ET. Les valeurs d’un filtre sélectionné se combinent avec OU. Nombres avec point décimal, dates AAAA-MM-JJ, dates/heures ISO avec fuseau, booléens true/false.</p><button type="submit" disabled={query.filters.length>=20}>Ajouter le filtre</button></form>
    <div className="dataset-active-filters" role="group" aria-label="Filtres actifs">{query.search&&<p>Recherche active : {query.search}</p>}{query.filters.map((filter,index)=><span key={index}>{columns.find(column=>column.id===filter.column)?.name} : {ALL_OPS[filter.op]} {filter.values.join(' ; ')} <button type="button" aria-label={'Retirer le filtre '+(index+1)} onClick={()=>setQuery(current=>({...current,page:1,filters:current.filters.filter((_,ordinal)=>index!==ordinal)}))}>Retirer</button></span>)}{(query.filters.length>0||query.search)&&<button type="button" onClick={()=>{setSearch('');setQuery(current=>({...current,page:1,search:'',filters:[]}))}}>Effacer tous les filtres et la recherche</button>}</div>
    <div className="dataset-form-grid"><label>Trier par<select aria-label="Trier par" value={query.sort?.column??''} onChange={event=>setQuery(current=>({...current,page:1,sort:event.target.value?{column:event.target.value,direction:current.sort?.direction??'asc'}:null}))}><option value="">Ordre du fichier</option>{columns.map(column=><option value={column.id} key={column.id}>{column.name}</option>)}</select></label><label>Sens du tri<select aria-label="Sens du tri" disabled={!query.sort} value={query.sort?.direction??'asc'} onChange={event=>setQuery(current=>({...current,page:1,sort:current.sort?{...current.sort,direction:event.target.value as 'asc'|'desc'}:null}))}><option value="asc">Croissant</option><option value="desc">Décroissant</option></select></label><label>Lignes par page<select aria-label="Lignes par page" value={query.pageSize} onChange={event=>setQuery(current=>({...current,page:1,pageSize:Number(event.target.value)}))}><option value={25}>25</option><option value={50}>50</option><option value={100}>100</option></select></label></div>
    <label className="dataset-checkbox"><input type="checkbox" checked={original} onChange={event=>setOriginal(event.target.checked)}/>Afficher les textes originaux (le tri et les filtres utilisent les valeurs interprétées)</label>
    {!resource.data?<Status error={resource.error}/>:<><p role="status">{resource.data.total} ligne(s) correspondent · Page {query.page}. Valeurs manquantes toujours en fin de tri.</p>{!resource.data.rows.length?<p>Aucune ligne ne correspond aux filtres.</p>:<div className="dataset-table-wrap" tabIndex={0} role="region" aria-label="Table des données"><table><caption>Version {version.version.number}, page {query.page}, {original?'textes originaux':'valeurs interprétées'}</caption><thead><tr><th scope="col">Ligne source</th>{columns.map(column=><th key={column.id} scope="col">{column.name}</th>)}</tr></thead><tbody>{resource.data.rows.map(row=><tr key={row.rowNumber}><th scope="row">{row.sourceLine}</th>{columns.map(column=><td key={column.id}><Cell value={original?row.originalValues[column.id]:row.values[column.id]}/></td>)}</tr>)}</tbody></table></div>}<div className="dataset-pagination"><button disabled={query.page===1} onClick={()=>setQuery(current=>({...current,page:current.page-1}))}>Page précédente</button><span>{resource.data.total} lignes</span><button disabled={query.page*query.pageSize>=resource.data.total} onClick={()=>setQuery(current=>({...current,page:current.page+1}))}>Page suivante</button></div></>}
  </section>
}
