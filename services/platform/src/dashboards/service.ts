import { randomUUID } from 'node:crypto'
import type pg from 'pg'
import { ApiError } from '../contracts.js'
import { transaction } from '../database.js'
import { activeAccount, onwardAccess, resourceAccess } from '../access.js'
import type { AnalyticsService } from '../analytics/service.js'
import { load,type Loaded } from '../analytics/sql.js'
import { configurationSchema, type Configuration, type FilterValues, type SaveDashboard,type Widget } from './contracts.js'
import { filteredDefinition, validateConfiguration } from './filters.js'

const changed=()=>new ApiError(409,'dashboard_changed','Ce tableau de bord a changé. Rechargez la révision actuelle avant de continuer.')
function visualColumns(loaded:Loaded,definition:Widget['definition']){
  const ids=new Set(definition.source.filters.map(filter=>filter.column))
  if(definition.kind==='aggregate'){definition.groupBy.forEach(group=>ids.add(group.column));definition.measures.forEach(measure=>{if(measure.column)ids.add(measure.column)})}
  else if(definition.kind==='histogram')ids.add(definition.column)
  else{ids.add(definition.x);ids.add(definition.y)}
  return loaded.columns.filter(column=>ids.has(column.id))
}
const serialize=(row:pg.QueryResultRow,user:string)=>({id:row.id,ownerId:row.owner_id,title:row.title,description:row.description,configuration:configurationSchema.parse(row.configuration),revision:row.revision,createdAt:row.created_at.toISOString(),updatedAt:row.updated_at.toISOString(),access:row.owner_id===user?'owner':'shared'})
export class DashboardService{
  constructor(public pool:pg.Pool,public analytics:AnalyticsService){}
  async ready(){await this.pool.query('SELECT id FROM platform.dashboards LIMIT 0')}
  async list(user:string,page:number){
    const rows=await this.pool.query(`SELECT d.* FROM platform.dashboards d WHERE d.owner_id=$1 OR EXISTS(SELECT 1 FROM platform.dashboard_grants g WHERE g.dashboard_id=d.id AND g.recipient_id=$1) ORDER BY updated_at DESC,id LIMIT 26 OFFSET $2`,[user,(page-1)*25])
    // Lists expose titles and counts, not unexecuted widget queries.
    return {dashboards:rows.rows.slice(0,25).map(row=>({id:row.id,title:row.title,description:row.description,revision:row.revision,access:row.owner_id===user?'owner':'shared',widgetCount:row.configuration.widgets.length,updatedAt:row.updated_at.toISOString()})),page,hasMore:rows.rows.length>25}
  }
  async get(user:string,id:string){
    return transaction(this.pool,async db=>{
      await db.query('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
      const row=await resourceAccess(db,user,'dashboard',id)
      if(row.owner_id!==user)await onwardAccess(db,'dashboard',row)
      return {dashboard:serialize(row,user)}
    })
  }
  async preview(user:string,configuration:Configuration,widgetId:string,values:FilterValues){
    return this.analytics.bounded(()=>transaction(this.pool,async db=>{
      await db.query('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
      await validateConfiguration(db,user,configuration)
      const widget=configuration.widgets.find(widget=>widget.id===widgetId)
      if(!widget)throw new ApiError(422,'invalid_widget','Widget absent de cette configuration.')
      const definition=await filteredDefinition(db,configuration,widget,values,false)
      return {result:await this.analytics.calculate(db,user,definition),columns:visualColumns(await load(db,user,definition.source),definition)}
    }))
  }
  async execute(user:string,id:string,widgetId:string,revision:number,values:FilterValues){
    return this.analytics.bounded(()=>transaction(this.pool,async db=>{
      await db.query('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
      const row=await resourceAccess(db,user,'dashboard',id)
      if(row.revision!==revision)throw changed()
      const reader=row.owner_id!==user
      if(reader)await onwardAccess(db,'dashboard',row)
      const configuration=configurationSchema.parse(row.configuration),widget=configuration.widgets.find(widget=>widget.id===widgetId)
      if(!widget)throw new ApiError(404,'widget_not_found','Widget introuvable dans cette révision.')
      const definition=await filteredDefinition(db,configuration,widget,values,reader)
      return {result:await this.analytics.calculate(db,row.owner_id,definition),columns:visualColumns(await load(db,row.owner_id,definition.source),definition)}
    }))
  }
  private async write(db:pg.PoolClient,user:string,input:SaveDashboard,id?:string,revision?:number){
    await activeAccount(db,user)
    if(id){const old=await resourceAccess(db,user,'dashboard',id,true,true);if(old.revision!==revision)throw changed()}
    const selected=[...new Map(input.configuration.widgets.map(widget=>[widget.definition.source.versionId,widget.definition.source])).values()].sort((a,b)=>a.datasetId.localeCompare(b.datasetId)||a.versionId.localeCompare(b.versionId))
    for(const source of selected)await load(db,user,source,true)
    await validateConfiguration(db,user,input.configuration)
    for(const widget of input.configuration.widgets){
      // The saved base definition and effective defaults must both be valid.
      await this.analytics.calculate(db,user,widget.definition)
      if(input.configuration.filters.some(filter=>filter.mappings.some(mapping=>mapping.widgetId===widget.id)))await this.analytics.calculate(db,user,await filteredDefinition(db,input.configuration,widget,[],false))
    }
    const dashboardId=id??randomUUID()
    if(id){
      await db.query("DELETE FROM platform.dataset_dependencies WHERE kind='dashboard' AND resource_id=$1",[id])
      await db.query('DELETE FROM platform.dashboard_sources WHERE dashboard_id=$1',[id])
      await db.query('DELETE FROM platform.dashboard_authorizations WHERE dashboard_id=$1',[id])
      await db.query('UPDATE platform.dashboards SET title=$2,description=$3,configuration=$4,revision=revision+1,updated_at=now() WHERE id=$1',[id,input.title,input.description,input.configuration])
    }else await db.query('INSERT INTO platform.dashboards(id,owner_id,title,description,configuration) VALUES($1,$2,$3,$4,$5)',[dashboardId,user,input.title,input.description,input.configuration])
    for(const source of selected){
      await db.query('INSERT INTO platform.dashboard_sources(dashboard_id,dataset_id,version_id) VALUES($1,$2,$3)',[dashboardId,source.datasetId,source.versionId])
      await db.query("INSERT INTO platform.dataset_dependencies(id,dataset_id,version_id,kind,resource_id,label) VALUES($1,$2,$3,'dashboard',$4,$5)",[randomUUID(),source.datasetId,source.versionId,dashboardId,input.title])
    }
    await db.query("INSERT INTO platform.activity(actor_id,action,resource_kind,resource_id) VALUES($1,$2,'dashboard',$3)",[user,id?'dashboard.updated':'dashboard.created',dashboardId])
    return {dashboard:serialize((await db.query('SELECT * FROM platform.dashboards WHERE id=$1',[dashboardId])).rows[0]!,user)}
  }
  async save(user:string,input:SaveDashboard,id?:string,revision?:number){return this.analytics.bounded(()=>transaction(this.pool,db=>this.write(db,user,input,id,revision)))}
  async copy(user:string,id:string,title:string){
    return this.analytics.bounded(()=>transaction(this.pool,async db=>{
      const row=await resourceAccess(db,user,'dashboard',id,true)
      if(row.owner_id!==user)await onwardAccess(db,'dashboard',row,true)
      // write rechecks actual dataset permissions; a presentation grant cannot become raw-data access.
      const copied=await this.write(db,user,{title,description:row.description,configuration:configurationSchema.parse(row.configuration)})
      await db.query("INSERT INTO platform.activity(actor_id,action,resource_kind,resource_id,details) VALUES($1,'dashboard.copied','dashboard',$2,$3)",[user,copied.dashboard.id,{sourceId:id}])
      return copied
    }))
  }
  async remove(user:string,id:string,revision:number){
    await transaction(this.pool,async db=>{
      await activeAccount(db,user)
      const row=await resourceAccess(db,user,'dashboard',id,true,true)
      if(row.revision!==revision)throw changed()
      await db.query("DELETE FROM platform.dataset_dependencies WHERE kind='dashboard' AND resource_id=$1",[id])
      await db.query('DELETE FROM platform.dashboards WHERE id=$1',[id])
      await db.query("INSERT INTO platform.activity(actor_id,action,resource_kind,resource_id) VALUES($1,'dashboard.deleted','dashboard',$2)",[user,id])
    })
  }
}
