import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router'
import { z } from 'zod'
import { useAccounts } from '@/features/accounts/account-context'
import { datasetRequest, detailSchema, importSchema, metadataSchema, previewSchema, publishedSchema, TYPE_LABELS, uploadSchema, useDatasetResource, type Configuration, type Metadata, type Options, type Preview } from './api'
import { MetadataFields, Status } from './shared'

export function UploadPage(){
  const{session}=useAccounts(),navigate=useNavigate(),[search]=useSearchParams()
  const[file,setFile]=useState<File|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('')
  const target=search.get('dataset')
  async function upload(event:FormEvent){
    event.preventDefault();if(!file)return
    if(file.size>10*1024*1024||file.size===0){setError('Choisissez un fichier non vide, de 10 Mio maximum.');return}
    setBusy(true);setError('')
    try{const result=await datasetRequest('/imports',uploadSchema,{method:'POST',csrfToken:session!.csrfToken,file});navigate(`/donnees/imports/${result.id}${target?'?dataset='+encodeURIComponent(target):''}`)}
    catch(error){setError(error instanceof Error?error.message:'Import indisponible.')}
    finally{setBusy(false)}
  }
  return <><Link to="/donnees">← Mes jeux de données</Link><h1>{target?'Ajouter une version CSV':'Importer un CSV'}</h1><p>Le fichier reste privé. Aucun jeu de données ne sera publié avant la validation complète et votre confirmation.</p><ol className="dataset-steps"><li aria-current="step">1. Fichier</li><li>2. Configuration</li><li>3. Description</li><li>4. Validation et publication</li></ol>
    <form className="platform-form-card" onSubmit={event=>{void upload(event)}}><label>Fichier CSV<input type="file" accept=".csv,text/csv" required onChange={event=>{setFile(event.target.files?.[0]??null);setError('')}} /></label><p>UTF-8 (avec ou sans BOM) ou Windows-1252. Maximum : 10 Mio, 25 000 lignes, 100 colonnes, 1 000 000 de cellules. Les autres formats ne sont pas encore pris en charge.</p>{error&&<p role="alert" className="platform-error">{error}</p>}<button className="platform-primary" type="submit" disabled={busy||!file}>{busy?'Transfert en cours…':'Préparer l’aperçu'}</button></form><p><a href="/samples/pharmaceutical-presentations.csv" download>Télécharger un exemple pharmaceutique attribué</a> · Observations datées, prix inconnus conservés. <a href="/samples/README.md">Provenance et règles de l’exemple</a></p>
  </>
}
export function ImportPage(){
  const{id}=useParams<{id:string}>(),[search]=useSearchParams()
  const resource=useDatasetResource(id?'/imports/'+id:null,importSchema)
  const target=search.get('dataset')
  const targetResource=useDatasetResource(target?'/datasets/'+target:null,detailSchema)
  if(!resource.data)return <Status error={resource.error}/>
  if(!('configuration'in resource.data))return <><h1>Import déjà publié</h1>{resource.data.published?<Link to={`/donnees/${resource.data.published.datasetId}?version=${resource.data.published.versionId}`}>Ouvrir la version importée</Link>:<p>Le jeu de données a été supprimé.</p>}</>
  if(target&&!targetResource.data)return <Status error={targetResource.error}/>
  return <ImportEditor key={id} initial={resource.data} id={id!} target={target} targetMetadata={targetResource.data?.dataset}/>
}
function ImportEditor({initial,id,target,targetMetadata}:{initial:Preview&{filename:string;expiresAt:string};id:string;target:string|null;targetMetadata?:Metadata}){
  const{session}=useAccounts(),navigate=useNavigate()
  const[state,setState]=useState<Preview>(initial),[configuration,setConfiguration]=useState<Configuration>(initial.configuration)
  const[dirty,setDirty]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('')
  const[metadata,setMetadata]=useState<Metadata>(targetMetadata?metadataSchema.parse(targetMetadata):{title:initial.filename.replace(/\.csv$/i,''),description:'',category:'',source:'',observationDate:null})
  const[markers,setMarkers]=useState(configuration.missingMarkers.filter(value=>value!=='').join('\n'))
  function updateOptions(patch:Partial<Options>){setConfiguration(current=>({...current,...patch}));setDirty(true);setError('')}
  function updateColumn(index:number,patch:Partial<Configuration['columns'][number]>){setConfiguration(current=>({...current,columns:current.columns.map((column,ordinal)=>ordinal===index?{...column,...patch}:column)}));setDirty(true);setError('')}
  async function configure(validate:boolean){
    setBusy(true);setError('')
    try{
      const{columns,...options}=configuration
      const result=await datasetRequest(`/imports/${id}/${validate?'validate':'preview'}`,previewSchema,{method:'POST',csrfToken:session!.csrfToken,body:{revision:state.revision,options,...(validate&&columns.length&&state.structure.valid?{columns}: {})}})
      setState(result);setConfiguration(result.configuration);setDirty(false)
    }catch(error){setError(error instanceof Error?error.message:'Configuration indisponible.')}
    finally{setBusy(false)}
  }
  async function publish(){
    setBusy(true);setError('')
    try{const result=await datasetRequest(`/imports/${id}/publish`,publishedSchema,{method:'POST',csrfToken:session!.csrfToken,body:{revision:state.revision,metadata,...(target?{datasetId:target}:{})}});navigate(`/donnees/${result.datasetId}?version=${result.versionId}`)}
    catch(error){setError(error instanceof Error?error.message:'Publication indisponible.')}
    finally{setBusy(false)}
  }
  async function cancel(){
    setBusy(true);setError('')
    try{await datasetRequest('/imports/'+id,z.undefined(),{method:'DELETE',csrfToken:session!.csrfToken});navigate('/donnees')}
    catch(error){setError(error instanceof Error?error.message:'Annulation indisponible.')}
    finally{setBusy(false)}
  }
  const report=dirty?null:state.validation
  return <><Link to="/donnees">← Mes jeux de données</Link><h1>Préparer {initial.filename}</h1><p>Import temporaire privé · Expire le {new Date(initial.expiresAt).toLocaleString('fr-FR')} (une heure après le transfert). Rechargez cette URL pour vérifier l’état après une interruption.</p><ol className="dataset-steps"><li>1. Fichier transféré</li><li>2. Configuration</li><li>3. Description</li><li>4. Validation et publication</li></ol>
    {error&&<p role="alert" className="platform-error">{error}</p>}
    <fieldset className="dataset-import-controls" disabled={busy} aria-busy={busy}><legend className="sr-only">Configuration et publication du fichier CSV</legend>
    <section className="platform-panel"><h2>Configuration du fichier</h2><div className="dataset-form-grid"><label>Séparateur<select aria-label="Séparateur" value={configuration.delimiter} onChange={event=>updateOptions({delimiter:event.target.value as Options['delimiter']})}><option value="auto">Détection automatique</option><option value=",">Virgule</option><option value=";">Point-virgule</option><option value={'\t'}>Tabulation</option></select></label><label>Encodage<select aria-label="Encodage" value={configuration.encoding} onChange={event=>updateOptions({encoding:event.target.value as Options['encoding']})}><option value="utf-8">UTF-8</option><option value="windows-1252">Windows-1252</option></select></label><label>Séparateur décimal<select aria-label="Séparateur décimal" value={configuration.decimalSeparator} onChange={event=>updateOptions({decimalSeparator:event.target.value as '.'|','})}><option value=".">Point (12.50)</option><option value=",">Virgule (12,50)</option></select></label></div>
      <label className="dataset-checkbox"><input type="checkbox" checked={configuration.trim} onChange={event=>updateOptions({trim:event.target.checked})}/>Retirer les espaces de bord pour l’interprétation (originaux conservés)</label>
      <label className="dataset-checkbox"><input type="checkbox" checked={configuration.missingMarkers.includes('')} onChange={event=>updateOptions({missingMarkers:event.target.checked?[...configuration.missingMarkers.filter(value=>value!==''),'']:configuration.missingMarkers.filter(value=>value!=='')})}/>Traiter une cellule vide comme une valeur manquante</label>
      <label>Autres marqueurs manquants (un par ligne, sensibles à la casse)<textarea value={markers} rows={2} onChange={event=>{setMarkers(event.target.value);updateOptions({missingMarkers:[...(configuration.missingMarkers.includes('')?['']:[]),...event.target.value.split('\n').filter(value=>value!=='')]})}}/></label>
      <p>« NA » reste du texte tant que vous ne l’ajoutez pas. Zéro et false ne sont jamais automatiquement manquants. Les séparateurs de milliers, devises et exposants numériques sont refusés pour les colonnes numériques.</p>
      <button type="button" disabled={busy} onClick={()=>{void configure(false)}}>Actualiser l’aperçu et proposer les types</button><p>Cette action réinitialise les types proposés. Après un changement de séparateur ou d’encodage, actualisez avant de choisir les types.</p>
      {state.warnings.map(warning=><p key={warning}>{warning}</p>)}{dirty&&<p role="status">Configuration modifiée : une nouvelle validation est nécessaire.</p>}
    </section>
    <section className="platform-panel"><h2>Aperçu du fichier</h2><p>{state.rowCount} lignes de données · {state.columnCount} colonnes · aperçu limité à 20 lignes. Les cellules ci-dessous sont les textes originaux.</p>
      {!state.structure.valid&&<div role="alert" className="platform-error"><p>{state.structure.issueCount} problème(s) de structure. Corrigez le fichier ou sa configuration. Aucun import partiel.</p>{state.structure.issues.slice(0,20).map((issue,index)=><p key={index}>Ligne source {issue.line}{issue.column?' · '+issue.column:''} : {issue.message}</p>)}</div>}
      <div className="dataset-table-wrap" tabIndex={0} role="region" aria-label="Aperçu CSV"><table><caption>20 premières lignes au maximum</caption><thead><tr>{state.configuration.columns.map((column,index)=><th key={index} scope="col">{column.name||'(en-tête vide)'}</th>)}</tr></thead><tbody>{state.sample.map((row,index)=><tr key={index}>{row.map((cell,ordinal)=><td key={ordinal}>{cell===''?<em>Cellule vide</em>:cell}</td>)}</tr>)}</tbody></table></div>
    </section>
    <section className="platform-panel"><h2>Types et conventions des colonnes</h2><p>Les identifiants avec zéros initiaux sont proposés en texte. Vérifiez les suggestions ; les valeurs invalides ne seront jamais converties en valeurs manquantes.</p>
      <div className="dataset-columns-editor">{configuration.columns.map((column,index)=><fieldset key={column.id+'_'+index}><legend>{column.name||'Colonne '+(index+1)}</legend><label>Type de {column.name}<select aria-label={'Type de '+column.name} value={column.type} onChange={event=>updateColumn(index,{type:event.target.value as typeof column.type})}>{Object.entries(TYPE_LABELS).map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label>
        {column.type==='date'&&<label>Format de {column.name}<select aria-label={'Format de '+column.name} value={column.dateFormat} onChange={event=>updateColumn(index,{dateFormat:event.target.value as typeof column.dateFormat})}><option value="iso">AAAA-MM-JJ</option><option value="dmy">JJ/MM/AAAA</option><option value="mdy">MM/JJ/AAAA</option></select></label>}
        {column.type==='boolean'&&<label>Valeurs de {column.name}<select aria-label={'Valeurs de '+column.name} value={column.booleanFormat} onChange={event=>updateColumn(index,{booleanFormat:event.target.value as typeof column.booleanFormat})}><option value="true-false">true / false</option><option value="oui-non">oui / non</option><option value="1-0">1 / 0</option></select></label>}
        {column.type==='datetime'&&<p>ISO 8601 avec fuseau obligatoire, secondes et 0–6 décimales : 2026-10-23T10:30:00+01:00. Stockage en UTC, microsecondes conservées.</p>}
      </fieldset>)}</div>
    </section>
    <section className="platform-panel"><h2>{target?'Nouvelle version du jeu de données':'Description du jeu de données'}</h2>{target?<p>Une nouvelle version sera ajoutée à « {metadata.title} ». Les versions existantes et les métadonnées seront conservées.</p>:<MetadataFields value={metadata} onChange={setMetadata}/>}</section>
    <section className="platform-panel"><h2>Valider et publier</h2><p>La validation vérifie toutes les lignes. Aucune ligne mal formée ni valeur invalide n’est supprimée silencieusement.</p><button type="button" disabled={busy} onClick={()=>{void configure(true)}}>{busy?'Traitement en cours…':'Valider tout le fichier'}</button>
      {report&&<div role={report.valid?'status':'alert'}><p>{report.valid?`Validation réussie : ${report.rowCount} lignes, ${report.columnCount} colonnes.`:`Validation refusée : ${report.issueCount} erreur(s). Corrigez la configuration ou le fichier.`}</p>{report.truncated&&<p>Rapport limité aux 1 000 premières erreurs. Corrigez-les puis relancez la validation pour obtenir les suivantes.</p>}{report.issues.slice(0,20).map((issue,index)=><p key={index}>Ligne {issue.row} (source {issue.line}), {issue.column??'structure'} : {issue.message}</p>)}{!report.valid&&<a href={`/platform-api/imports/${id}/report`}>Télécharger le rapport de validation CSV</a>}</div>}
      <div className="platform-actions"><button type="button" className="platform-primary" disabled={busy||dirty||!report?.valid||!metadata.title.trim()} onClick={()=>{void publish()}}>{target?'Publier la nouvelle version':'Importer et créer le jeu de données'}</button><button type="button" disabled={busy} onClick={()=>{void cancel()}}>Annuler cet import temporaire</button></div>
    </section>
    </fieldset>
  </>
}
