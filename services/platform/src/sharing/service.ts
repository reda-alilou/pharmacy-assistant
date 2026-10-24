import { randomUUID } from 'node:crypto'
import type pg from 'pg'
import { ApiError } from '../contracts.js'
import { transaction } from '../database.js'
import { activeAccount, datasetAccess, onwardAccess, resourceAccess, resourceTables, unavailable, type Database, type ResourceKind } from '../access.js'
import { reviewConfiguration } from './review.js'

export type ShareKind=ResourceKind|'dataset'
const tables=(kind:ShareKind)=>kind==='dataset'?{table:'datasets',grants:'dataset_grants',key:'dataset_id'}:resourceTables[kind]
async function own(db:Database,user:string,kind:ShareKind,id:string,lock=false){
  if(kind!=='dataset')return resourceAccess(db,user,kind,id,lock,true)
  const result=await db.query(`SELECT * FROM platform.datasets WHERE id=$1 AND owner_id=$2 ${lock?'FOR UPDATE':''}`,[id,user])
  if(!result.rowCount)throw unavailable()
  return result.rows[0]!
}
const audit=(db:Database,user:string,action:string,kind:ShareKind,id:string,details:Record<string,unknown>)=>db.query(
  'INSERT INTO platform.activity(actor_id,action,resource_kind,resource_id,details) VALUES($1,$2,$3,$4,$5)',[user,action,kind,id,details])

export class SharingService {
  constructor(public pool:pg.Pool){}
  async list(user:string,kind:ShareKind,id:string,page=1){
    return transaction(this.pool,async db=>{
      await db.query('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
      const row=await own(db,user,kind,id),table=tables(kind)
      const grants=await db.query(`SELECT g.id,u.email,u.display_name,g.created_at FROM platform.${table.grants} g JOIN platform.users u ON u.id=g.recipient_id WHERE g.${table.key}=$1 ORDER BY g.created_at DESC,g.id LIMIT 26 OFFSET $2`,[id,(page-1)*25])
      const authorizations:Record<string,unknown>[]=[]
      if(kind!=='dataset'){
        const resource=resourceTables[kind]
        const sources=await db.query(`SELECT DISTINCT d.id,d.title,d.owner_id,u.display_name, a.revision FROM platform.${resource.sources} s JOIN platform.datasets d ON d.id=s.dataset_id JOIN platform.users u ON u.id=d.owner_id LEFT JOIN platform.${resource.authorizations} a ON a.dataset_id=d.id AND a.${resource.key}=$1 WHERE s.${resource.key}=$1 ORDER BY d.id`,[id])
        for(const source of sources.rows){
          let available=true
          try{await datasetAccess(db,user,source.id)}catch{available=false}
          authorizations.push({datasetId:source.id,title:source.title,ownerName:source.display_name,required:source.owner_id!==user,authorized:source.owner_id===user||source.revision===row.revision,available})
        }
      }
      return {grants:grants.rows.slice(0,25).map(grant=>({id:grant.id,email:grant.email,displayName:grant.display_name,createdAt:grant.created_at.toISOString()})),authorizations,hasMore:grants.rows.length>25,page}
    })
  }
  async grant(user:string,kind:ShareKind,id:string,email:string){
    return transaction(this.pool,async db=>{
      await activeAccount(db,user)
      const row=await own(db,user,kind,id,true),table=tables(kind)
      if(kind==='dataset')await datasetAccess(db,user,id,true)
      if(kind!=='dataset')await onwardAccess(db,kind,row,true)
      const recipient=await db.query('SELECT id FROM platform.users WHERE email=$1 AND active FOR SHARE',[email])
      if(!recipient.rowCount)throw new ApiError(422,'recipient_unavailable','Partage indisponible pour cette adresse exacte. Le destinataire doit avoir un compte actif.')
      if(recipient.rows[0].id===user)throw new ApiError(422,'self_share','Vous êtes déjà propriétaire de cette ressource.')
      // Idempotent exact-recipient grants do not create duplicate dependencies.
      const grant=await db.query(`INSERT INTO platform.${table.grants}(id,${table.key},recipient_id,created_by) VALUES($1,$2,$3,$4) ON CONFLICT(${table.key},recipient_id) DO UPDATE SET created_by=EXCLUDED.created_by RETURNING id`,[randomUUID(),id,recipient.rows[0].id,user])
      if(kind==='dataset')await db.query("INSERT INTO platform.dataset_dependencies(id,dataset_id,kind,resource_id,label) VALUES($1,$2,'share',$3,'Accès partagé au dataset') ON CONFLICT DO NOTHING",[randomUUID(),id,grant.rows[0].id])
      await audit(db,user,'sharing.granted',kind,id,{recipientId:recipient.rows[0].id})
      return {id:grant.rows[0].id}
    })
  }
  async revoke(user:string,kind:ShareKind,id:string,grantId:string){
    await transaction(this.pool,async db=>{
      await activeAccount(db,user);await own(db,user,kind,id,true)
      const table=tables(kind)
      const removed=await db.query(`DELETE FROM platform.${table.grants} WHERE id=$1 AND ${table.key}=$2 RETURNING recipient_id`,[grantId,id])
      if(!removed.rowCount)throw unavailable()
      if(kind==='dataset')await db.query("DELETE FROM platform.dataset_dependencies WHERE kind='share' AND resource_id=$1",[grantId])
      await audit(db,user,'sharing.revoked',kind,id,{recipientId:removed.rows[0].recipient_id})
    })
  }
  async review(user:string,datasetId:string,page=1){
    return transaction(this.pool,async db=>{
      await db.query('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
      await own(db,user,'dataset',datasetId)
      const resources:Record<string,unknown>[]=[]
      const matches=await db.query(`SELECT * FROM (
        SELECT 'dashboard' kind,r.id,r.updated_at FROM platform.dashboards r WHERE r.owner_id<>$2 AND EXISTS(SELECT 1 FROM platform.dashboard_sources s WHERE s.dashboard_id=r.id AND s.dataset_id=$1)
        UNION ALL
        SELECT 'analysis' kind,r.id,r.updated_at FROM platform.analyses r WHERE r.owner_id<>$2 AND EXISTS(SELECT 1 FROM platform.analysis_sources s WHERE s.analysis_id=r.id AND s.dataset_id=$1)
      ) resources ORDER BY updated_at DESC,id,kind LIMIT 11 OFFSET $3`,[datasetId,user,(page-1)*10])
      for(const match of matches.rows.slice(0,10)){
        const kind:ResourceKind=match.kind==='dashboard'?'dashboard':'analysis'
        const table=resourceTables[kind]
        const records=await db.query(`SELECT r.*,u.display_name,u.email,a.revision allowed_revision FROM platform.${table.table} r JOIN platform.users u ON u.id=r.owner_id LEFT JOIN platform.${table.authorizations} a ON a.${table.key}=r.id AND a.dataset_id=$1 WHERE r.id=$2`,[datasetId,match.id])
        for(const row of records.rows){
          resources.push({id:row.id,kind,title:row.title,ownerName:row.display_name,ownerEmail:row.email,revision:row.revision,authorized:row.allowed_revision===row.revision,
            review:await reviewConfiguration(db,user,datasetId,kind,row)})
        }
      }
      return {resources,page,hasMore:matches.rows.length>10}
    })
  }
  async authorize(user:string,datasetId:string,kind:ResourceKind,id:string,revision:number,allow:boolean){
    await transaction(this.pool,async db=>{
      await activeAccount(db,user)
      const table=resourceTables[kind]
      // Same resource-then-dataset order as saves, to serialize revision approval.
      const resource=await db.query(`SELECT * FROM platform.${table.table} WHERE id=$1 FOR SHARE`,[id])
      await own(db,user,'dataset',datasetId,true)
      const row=resource.rows[0]
      if(!row||row.owner_id===user||!(await db.query(`SELECT 1 FROM platform.${table.sources} WHERE ${table.key}=$1 AND dataset_id=$2`,[id,datasetId])).rowCount)throw unavailable()
      if(row.revision!==revision)throw new ApiError(409,'resource_changed','La configuration a changé. Relisez la révision actuelle avant de décider.')
      if(allow){
        await datasetAccess(db,row.owner_id,datasetId,true)
        await db.query(`INSERT INTO platform.${table.authorizations}(dataset_id,${table.key},revision,authorized_by) VALUES($1,$2,$3,$4) ON CONFLICT(dataset_id,${table.key}) DO UPDATE SET revision=EXCLUDED.revision,authorized_by=EXCLUDED.authorized_by,created_at=now()`,[datasetId,id,revision,user])
      }else await db.query(`DELETE FROM platform.${table.authorizations} WHERE dataset_id=$1 AND ${table.key}=$2`,[datasetId,id])
      await audit(db,user,allow?'sharing.authorized':'sharing.authorization_revoked','dataset',datasetId,{kind,resourceId:id,revision})
    })
  }
}
