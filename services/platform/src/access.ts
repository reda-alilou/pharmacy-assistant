import type pg from 'pg'
import { ApiError } from './contracts.js'

export type Database = pg.Pool | pg.PoolClient
export const unavailable=()=>new ApiError(404,'resource_unavailable','Ressource introuvable ou accès révoqué pour ce compte.')
export function assertDatasetAvailable(row:{suspended:boolean}){
  if(row.suspended)throw new ApiError(423,'dataset_suspended','Source indisponible : ce jeu de données est suspendu par l’administration. Les données et configurations sont conservées.')
}
export async function activeAccount(db:Database,user:string){
  if(!(await db.query('SELECT id FROM platform.users WHERE id=$1 AND active FOR SHARE',[user])).rowCount)
    throw new ApiError(401,'authentication_required','Connectez-vous pour continuer.')
}
// Fixed SQL fragment: $1 dataset, $2 actor. Result grants never grant dataset access.
export const datasetPermission=`(d.owner_id=$2 OR EXISTS(SELECT 1 FROM platform.dataset_grants g WHERE g.dataset_id=d.id AND g.recipient_id=$2))`
export async function datasetAccess(db:Database,user:string,id:string,lock=false,absent=unavailable){
  const selected=await db.query(`SELECT d.id,d.owner_id,d.suspended FROM platform.datasets d WHERE d.id=$1 ${lock?'FOR SHARE OF d':''}`,[id])
  if(!selected.rowCount)throw absent()
  if(selected.rows[0].owner_id!==user){
    const grant=await db.query(`SELECT id FROM platform.dataset_grants WHERE dataset_id=$1 AND recipient_id=$2 ${lock?'FOR SHARE':''}`,[id,user])
    if(!grant.rowCount)throw absent()
  }
  assertDatasetAvailable(selected.rows[0])
  return selected.rows[0].owner_id as string
}
export type ResourceKind='dashboard'|'analysis'
export const resourceTables={dashboard:{table:'dashboards',sources:'dashboard_sources',key:'dashboard_id',grants:'dashboard_grants',authorizations:'dashboard_authorizations'},
  analysis:{table:'analyses',sources:'analysis_sources',key:'analysis_id',grants:'analysis_grants',authorizations:'analysis_authorizations'}} as const
export async function resourceAccess(db:Database,user:string,kind:ResourceKind,id:string,lock=false,own=false){
  const absent=kind==='analysis'?()=>new ApiError(404,'analysis_not_found','Analyse introuvable ou accès révoqué pour ce compte.'):unavailable
  const tables=resourceTables[kind]
  const selected=await db.query(`SELECT r.* FROM platform.${tables.table} r WHERE r.id=$1 ${lock?'FOR UPDATE OF r':''}`,[id])
  if(!selected.rowCount)throw absent()
  const row=selected.rows[0]!
  if(row.owner_id!==user){
    if(own)throw absent()
    if(!(await db.query(`SELECT id FROM platform.${tables.grants} WHERE ${tables.key}=$1 AND recipient_id=$2 ${lock?'FOR SHARE':''}`,[id,user])).rowCount)throw absent()
  }
  return row
}
export async function onwardAccess(db:Database,kind:ResourceKind,row:pg.QueryResultRow,lock=false){
  const tables=resourceTables[kind]
  const datasets=await db.query(`SELECT DISTINCT dataset_id FROM platform.${tables.sources} WHERE ${tables.key}=$1 ORDER BY dataset_id`,[row.id])
  for(const {dataset_id:id} of datasets.rows){
    const owner=await datasetAccess(db,row.owner_id,id,lock)
    if(owner!==row.owner_id){
      const authorization=await db.query(`SELECT revision FROM platform.${tables.authorizations} WHERE dataset_id=$1 AND ${tables.key}=$2 AND revision=$3 ${lock?'FOR SHARE':''}`,[id,row.id,row.revision])
      if(!authorization.rowCount)throw new ApiError(403,'onward_authorization_required','Le propriétaire original doit autoriser la diffusion de cette révision avant son partage ou sa consultation partagée.')
    }
  }
}
