import type pg from 'pg'
import { ApiError } from '../contracts.js'
import { transaction } from '../database.js'
import { columnSchema, type DataQuery } from '../datasets/contracts.js'
import { buildQuery } from '../datasets/query.js'
import type { ActivityQuery, DatasetsQuery, UsersQuery } from './contracts.js'

const absent=()=>new ApiError(404,'admin_resource_unavailable','Ressource administrative introuvable.')
export async function administrator(db:pg.PoolClient,id:string){
  const row=await db.query("SELECT id FROM platform.users WHERE id=$1 AND active AND role='admin' FOR SHARE",[id])
  if(!row.rowCount)throw new ApiError(403,'forbidden','Une session administrateur active est requise.')
}
const user=(r:pg.QueryResultRow)=>({id:r.id,email:r.email,displayName:r.display_name,role:r.role,active:r.active,revision:r.permissions_revision,createdAt:r.created_at.toISOString(),updatedAt:r.updated_at.toISOString()})
const dataset=(r:pg.QueryResultRow)=>({id:r.id,title:r.title,description:r.description,category:r.category,source:r.source,observationDate:r.observation_date instanceof Date?r.observation_date.toISOString().slice(0,10):r.observation_date,ownerId:r.owner_id,ownerEmail:r.owner_email,ownerName:r.owner_name,archived:r.archived,suspended:r.suspended,reason:r.suspension_reason,changedAt:r.suspension_changed_at?.toISOString()??null,changedBy:r.suspension_changed_by,revision:r.revision,versionCount:Number(r.version_count),rowCount:Number(r.row_count),updatedAt:r.updated_at.toISOString()})
const datasetSelect=`SELECT d.*,u.email owner_email,u.display_name owner_name,
  (SELECT count(*) FROM platform.dataset_versions v WHERE v.dataset_id=d.id) version_count,
  (SELECT coalesce(sum(row_count),0) FROM platform.dataset_versions v WHERE v.dataset_id=d.id) row_count
  FROM platform.datasets d JOIN platform.users u ON u.id=d.owner_id`
const version=(r:pg.QueryResultRow)=>({id:r.id,number:r.version_number,filename:r.filename,rowCount:r.row_count,columnCount:r.column_count,createdAt:r.created_at.toISOString()})
const receipt=(r:pg.QueryResultRow)=>({id:r.id,filename:r.filename,ownerId:r.owner_id,ownerEmail:r.email,datasetId:r.dataset_id,status:r.status,issueCount:r.issue_count,createdAt:r.created_at.toISOString()})
// Only bounded structured audit fields are exposed. Never serialize arbitrary
// JSON, password hashes, import bodies or session rows into administration.
function details(value:Record<string,unknown>){
  const allowed=['via','before','after','recipientId','kind','resourceId','revision','sourceId','archived','issueCount','versionId','rows','columns','importId','reason','suspended','page','pageSize','returnedRows']
  return Object.fromEntries(Object.entries(value).filter(([key,v])=>allowed.includes(key)&&(['string','boolean','number'].includes(typeof v)||(key==='before'||key==='after')&&v!==null&&typeof v==='object')).map(([key,v])=>[key,(key==='before'||key==='after')?Object.fromEntries(Object.entries(v as Record<string,unknown>).filter(([field,item])=>field==='role'&&(item==='admin'||item==='analyst')||field==='active'&&typeof item==='boolean')):v]))
}
export class AdminService{
  constructor(public pool:pg.Pool){}
  private read<T>(actor:string,work:(db:pg.PoolClient)=>Promise<T>){
    return transaction(this.pool,async db=>{await administrator(db,actor);return work(db)})
  }
  async overview(actor:string){return this.read(actor,async db=>{
    const totals=await db.query(`SELECT
      (SELECT count(*)::int FROM platform.users) users,
      (SELECT count(*)::int FROM platform.users WHERE active) active_users,
      (SELECT count(*)::int FROM platform.users WHERE active AND role='admin') active_admins,
      (SELECT count(*)::int FROM platform.datasets) datasets,
      (SELECT count(*)::int FROM platform.datasets WHERE suspended) suspended_datasets,
      (SELECT count(*)::int FROM platform.dataset_versions) versions,
      (SELECT coalesce(sum(row_count),0)::text FROM platform.dataset_versions) imported_rows,
      (SELECT count(*)::int FROM platform.analyses) analyses,
      (SELECT count(*)::int FROM platform.dashboards) dashboards,
      (SELECT count(*)::int FROM platform.activity WHERE outcome='failure' AND created_at>=now()-interval '7 days') failures_last_week`)
    const imports=await db.query('SELECT r.id,r.filename,r.owner_id,r.dataset_id,r.status,r.issue_count,r.created_at,u.email FROM platform.import_receipts r JOIN platform.users u ON u.id=r.owner_id ORDER BY r.created_at DESC,r.id LIMIT 10')
    const failures=await db.query("SELECT id::text,action,resource_kind,resource_id,created_at FROM platform.activity WHERE outcome='failure' ORDER BY id DESC LIMIT 10")
    return {totals:totals.rows[0],recentImports:imports.rows.map(receipt),recentFailures:failures.rows.map(r=>({id:r.id,action:r.action,resourceKind:r.resource_kind,resourceId:r.resource_id,createdAt:r.created_at.toISOString()}))}
  })}
  async users(actor:string,q:UsersQuery){return this.read(actor,async db=>{
    const rows=await db.query(`SELECT id,email,display_name,role,active,permissions_revision,created_at,updated_at FROM platform.users
      WHERE (strpos(lower(email),lower($1))>0 OR strpos(lower(display_name),lower($1))>0)
      AND ($2='all' OR role=$2) AND ($3='all' OR active=($3='true')) ORDER BY created_at DESC,id LIMIT 26 OFFSET $4`,[q.search,q.role,q.active,(q.page-1)*25])
    return {users:rows.rows.slice(0,25).map(user),page:q.page,hasMore:rows.rows.length>25}
  })}
  async permissions(actor:string,id:string,revision:number,role:'admin'|'analyst',active:boolean){
    return transaction(this.pool,async db=>{
      // Acquire the invariant lock before actor/target row locks, as in the CLI.
      await db.query('SELECT pg_advisory_xact_lock(72419021)');await administrator(db,actor)
      const selected=await db.query('SELECT id,role,active,permissions_revision FROM platform.users WHERE id=$1 FOR UPDATE',[id])
      const before=selected.rows[0];if(!before)throw absent()
      if(before.permissions_revision!==revision)throw new ApiError(409,'account_changed','Ce compte a changé. Actualisez avant de confirmer.')
      if(before.role===role&&before.active===active)return {changed:false,sessionInvalidated:false}
      if(before.role==='admin'&&before.active&&(role!=='admin'||!active)&&!(await db.query("SELECT id FROM platform.users WHERE active AND role='admin' AND id<>$1 LIMIT 1",[id])).rowCount)
        throw new ApiError(409,'last_admin','Le dernier administrateur actif doit être conservé.')
      await db.query('UPDATE platform.users SET role=$2,active=$3,updated_at=now() WHERE id=$1',[id,role,active])
      await db.query("INSERT INTO platform.activity(actor_id,action,resource_kind,resource_id,details) VALUES($1,'account.permissions_changed','account',$2,$3)",[actor,id,{via:'administration',before:{role:before.role,active:before.active},after:{role,active}}])
      return {changed:true,sessionInvalidated:id===actor}
    })
  }
  async datasets(actor:string,q:DatasetsQuery){return this.read(actor,async db=>{
    const rows=await db.query(`${datasetSelect} WHERE (strpos(lower(d.title),lower($1))>0 OR strpos(lower(d.source),lower($1))>0 OR strpos(lower(u.email),lower($1))>0)
      AND ($2::uuid IS NULL OR d.owner_id=$2) AND ($3='all' OR ($3='suspended' AND d.suspended) OR ($3='available' AND NOT d.suspended AND NOT d.archived) OR ($3='archived' AND d.archived)) ORDER BY d.updated_at DESC,d.id LIMIT 26 OFFSET $4`,[q.search,q.owner??null,q.state,(q.page-1)*25])
    return {datasets:rows.rows.slice(0,25).map(dataset),page:q.page,hasMore:rows.rows.length>25}
  })}
  async dataset(actor:string,id:string,page=1){return this.read(actor,async db=>{
    const selected=await db.query(`${datasetSelect} WHERE d.id=$1`,[id]);if(!selected.rowCount)throw absent()
    const versions=await db.query('SELECT id,version_number,filename,row_count,column_count,created_at FROM platform.dataset_versions WHERE dataset_id=$1 ORDER BY version_number DESC LIMIT 26 OFFSET $2',[id,(page-1)*25])
    const imports=await db.query('SELECT r.id,r.filename,r.owner_id,r.dataset_id,r.status,r.issue_count,r.created_at,u.email FROM platform.import_receipts r JOIN platform.users u ON u.id=r.owner_id WHERE r.dataset_id=$1 ORDER BY r.created_at DESC,r.id LIMIT 10',[id])
    return {dataset:dataset(selected.rows[0]),versions:versions.rows.slice(0,25).map(version),hasMore:versions.rows.length>25,page,recentImports:imports.rows.map(receipt)}
  })}
  async suspend(actor:string,id:string,revision:number,suspended:boolean,reason:string){
    return transaction(this.pool,async db=>{
      await administrator(db,actor)
      const selected=await db.query('SELECT revision,suspended FROM platform.datasets WHERE id=$1 FOR UPDATE',[id]);if(!selected.rowCount)throw absent()
      if(selected.rows[0].revision!==revision)throw new ApiError(409,'dataset_changed','Ce dataset a changé. Actualisez avant de confirmer.')
      if(selected.rows[0].suspended===suspended)throw new ApiError(409,'suspension_unchanged','Cet état est déjà appliqué. Actualisez la page.')
      await db.query('UPDATE platform.datasets SET suspended=$2,suspension_reason=$3,suspension_changed_at=now(),suspension_changed_by=$4,revision=revision+1,updated_at=now() WHERE id=$1',[id,suspended,reason,actor])
      await db.query("INSERT INTO platform.activity(actor_id,action,resource_kind,resource_id,details) VALUES($1,$2,'dataset',$3,$4)",[actor,suspended?'dataset.suspended':'dataset.resumed',id,{reason,suspended}])
    })
  }
  async inspect(actor:string,id:string,versionId:string,reason:string,query:DataQuery){
    return this.read(actor,async db=>{
      // A separate, explicitly audited path; it does not grant ordinary ownership
      // or leave a reusable inspection permission behind. Works during suspension.
      const selected=await db.query('SELECT v.id,v.version_number,v.filename,v.row_count,v.column_count,v.created_at FROM platform.dataset_versions v JOIN platform.datasets d ON d.id=v.dataset_id WHERE v.dataset_id=$1 AND v.id=$2 FOR SHARE OF d',[id,versionId]);if(!selected.rowCount)throw absent()
      const columns=await db.query('SELECT interpretation,profile FROM platform.dataset_columns WHERE version_id=$1 ORDER BY ordinal',[versionId])
      const definitions=columns.rows.map(r=>columnSchema.parse(r.interpretation)),built=buildQuery(versionId,definitions,query)
      const total=await db.query(`SELECT count(*)::int total FROM platform.dataset_rows r WHERE ${built.where}`,built.countParameters)
      const parameters=[...built.parameters,query.pageSize,(query.page-1)*query.pageSize]
      const rows=await db.query(`SELECT row_number,source_line,values,original_values FROM platform.dataset_rows r WHERE ${built.where} ORDER BY ${built.order} LIMIT $${parameters.length-1} OFFSET $${parameters.length}`,parameters)
      // Failure to record the inspection fails the whole response.
      await db.query("INSERT INTO platform.activity(actor_id,action,resource_kind,resource_id,details) VALUES($1,'dataset.inspected','dataset',$2,$3)",[actor,id,{versionId,reason,page:query.page,pageSize:query.pageSize,returnedRows:rows.rowCount}])
      return {version:version(selected.rows[0]),columns:columns.rows.map((r,i)=>({definition:definitions[i],profile:r.profile})),total:total.rows[0].total,page:query.page,pageSize:query.pageSize,rows:rows.rows.map(r=>({rowNumber:r.row_number,sourceLine:r.source_line,values:r.values,originalValues:r.original_values}))}
    })
  }
  async activity(actor:string,q:ActivityQuery){return this.read(actor,async db=>{
    const values:unknown[]=[],where:string[]=[]
    for(const [column,value] of [['a.actor_id',q.actor],['a.action',q.action],['a.resource_kind',q.kind],['a.resource_id',q.resource],['a.outcome',q.outcome]] as const){if(value){values.push(value);where.push(`${column}=$${values.length}`)}}
    if(q.from){values.push(q.from);where.push(`a.created_at >= $${values.length}::date AT TIME ZONE 'UTC'`)}
    if(q.to){values.push(q.to);where.push(`a.created_at < ($${values.length}::date+1) AT TIME ZONE 'UTC'`)}
    values.push((q.page-1)*25)
    const rows=await db.query(`SELECT a.id::text,a.actor_id,u.display_name,u.email,a.action,a.resource_kind,a.resource_id,a.outcome,a.details,a.created_at FROM platform.activity a LEFT JOIN platform.users u ON u.id=a.actor_id ${where.length?'WHERE '+where.join(' AND '):''} ORDER BY a.id DESC LIMIT 26 OFFSET $${values.length}`,values)
    return {events:rows.rows.slice(0,25).map(r=>({id:r.id,actorId:r.actor_id,actorName:r.display_name,actorEmail:r.email,action:r.action,resourceKind:r.resource_kind,resourceId:r.resource_id,outcome:r.outcome,details:details(r.details),createdAt:r.created_at.toISOString()})),page:q.page,hasMore:rows.rows.length>25,retention:'Conservation sans purge automatique ; aucune conversation patient ni secret de session.'}
  })}
}
