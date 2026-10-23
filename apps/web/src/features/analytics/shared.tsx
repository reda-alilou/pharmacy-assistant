import { useState } from 'react'
import { useNavigate } from 'react-router'
import { z } from 'zod'
import { useAccounts } from '@/features/accounts/account-context'
import { columnSchema } from '@/features/datasets/api'
import { analysisSchema,analyticsRequest,resultSchema,savedSchema } from './api'
import { Results } from './results'

const executionSchema=z.object({result:resultSchema,columns:z.array(columnSchema),rightColumns:z.array(columnSchema),inspectionAvailable:z.boolean()})
export function SharedAnalysis({analysis}:{analysis:z.infer<typeof analysisSchema>}){
  const{session}=useAccounts(),navigate=useNavigate(),[execution,setExecution]=useState<z.infer<typeof executionSchema>|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[title,setTitle]=useState('')
  async function run(page=1){setBusy(true);setError('');setExecution(null);try{setExecution(await analyticsRequest('/analyses/'+analysis.id+'/execute',executionSchema,{method:'POST',csrfToken:session!.csrfToken,body:{revision:analysis.revision,page,pageSize:25}}))}catch(error){setError(error instanceof Error?error.message:'Source ou autorisation indisponible.')}finally{setBusy(false)}}
  async function copy(){setBusy(true);setError('');try{const response=await analyticsRequest('/analyses/'+analysis.id+'/copy',savedSchema,{method:'POST',csrfToken:session!.csrfToken,body:{title}});navigate('/analyses/'+response.analysis.id)}catch(error){setError(error instanceof Error?error.message:'Copie indisponible.')}finally{setBusy(false)}}
  return <><p className="platform-eyebrow">Analyse partagée · lecture seule · révision {analysis.revision}</p><h1>{analysis.title}</h1><p>{analysis.description}</p><p>Le serveur exécute uniquement la configuration enregistrée. Ce partage ne donne pas accès à l’exploration des datasets ni à leurs lignes originales. Une copie modifiable exige des droits dataset distincts sur toutes les sources.</p>{error&&<p role="alert">{error}</p>}<button type="button" disabled={busy} className="platform-primary" onClick={()=>{void run()}}>{busy?'Traitement en cours…':'Calculer les résultats partagés'}</button>
    {execution&&<Results result={execution.result} columns={execution.columns} rightColumns={execution.rightColumns} inspectionAvailable={execution.inspectionAvailable} readOnly onApply={()=>{}} onPage={page=>{void run(page)}}/>}
    <section className="platform-panel"><h2>Copie privée</h2><label>Titre de la copie d’analyse<input aria-label="Titre de la copie d’analyse" maxLength={160} value={title} disabled={busy} onChange={event=>setTitle(event.target.value)}/></label><button type="button" disabled={busy||!title.trim()} onClick={()=>{void copy()}}>Copier cette analyse en privé</button></section>
  </>
}
