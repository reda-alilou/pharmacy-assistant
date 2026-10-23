import { randomUUID } from 'node:crypto'
import type pg from 'pg'
import { ApiError } from '../contracts.js'
import { transaction } from '../database.js'
import { definitionSchema, sources, type Definition, type Save } from './contracts.js'
import { load } from './sql.js'
import { aggregate, histogram, scatter, missingness, outliers } from './engine.js'
import { comparison } from './compare.js'
import { recommendations, templates } from './recommend.js'
import { datasetAccess, onwardAccess, resourceAccess } from '../access.js'

const absent=()=>new ApiError(404,'analysis_not_found','Analyse introuvable pour ce compte.')
const serialized=(row:pg.QueryResultRow,user=row.owner_id as string)=>({id:row.id,ownerId:row.owner_id,title:row.title,description:row.description,definition:definitionSchema.parse(row.definition),revision:row.revision,createdAt:row.created_at.toISOString(),updatedAt:row.updated_at.toISOString(),access:row.owner_id===user?'owner':'shared'})

export class AnalyticsService {
  private running=0
  constructor(public pool:pg.Pool) {}
  async ready(){await this.pool.query('SELECT id FROM platform.analyses LIMIT 0')}
  async bounded<T>(work:()=>Promise<T>){
    if(this.running>=2)throw new ApiError(429,'analytics_busy','Deux analyses sont déjà en cours. Réessayez dans un instant.',1)
    this.running++
    try{return await work()}finally{this.running--}
  }
  private async active(db:pg.PoolClient,owner:string){
    if(!(await db.query('SELECT id FROM platform.users WHERE id=$1 AND active FOR SHARE',[owner])).rowCount)throw new ApiError(401,'authentication_required','Connectez-vous pour continuer.')
  }
  async calculate(db:pg.PoolClient,owner:string,definition:Definition,page=1,pageSize=25,lock=false){
    const selected=await load(db,owner,definition.source,lock)
    // Authorize both sources before any comparison query or metadata response.
    const right=definition.kind==='compare'?await load(db,owner,definition.right,lock):null
    const result=definition.kind==='aggregate'?await aggregate(db,selected,definition):definition.kind==='histogram'?await histogram(db,selected,definition):
      definition.kind==='scatter'?await scatter(db,selected,definition):definition.kind==='missing'?await missingness(db,selected,definition,page,pageSize):
      definition.kind==='outliers'?await outliers(db,selected,definition,page,pageSize):definition.kind==='compare'?await comparison(db,selected,right!,definition,page,pageSize):
      await recommendations(db,selected,definition)
    return {...result,algorithm:'cp3-v1' as const,definition,sources:[selected,...(right?[right]:[])].map(item=>({datasetId:item.source.datasetId,versionId:item.source.versionId,title:item.title,versionNumber:item.number,importedRows:item.rowCount})),
      conventions:{quartiles:'Hyndman–Fan type 7; interpolation linéaire exacte (n−1)×p',standardDeviation:'Échantillon : n−1 (n<2 : non défini). Population : n. Moyennes et écarts-types : calcul numérique PostgreSQL avec 24 décimales, sans virgule flottante binaire.',time:'Regroupements des dates/heures en UTC ; dates calendaires conservées.',missing:'Les statistiques numériques excluent les cellules manquantes ; aucun remplacement par zéro. Les imports invalides sont refusés avant publication.'}}
  }
  async execute(owner:string,definition:Definition,page=1,pageSize=25){
    return this.bounded(()=>transaction(this.pool,async db=>{
      await db.query('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
      return this.calculate(db,owner,definition,page,pageSize)
    }))
  }
  async templates(owner:string,source:Definition['source']){
    return transaction(this.pool,async db=>{
      await db.query('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
      return {templates:templates(await load(db,owner,source))}
    })
  }
  async list(owner:string,page:number){
    const rows=await this.pool.query('SELECT a.* FROM platform.analyses a WHERE owner_id=$1 OR EXISTS(SELECT 1 FROM platform.analysis_grants g WHERE g.analysis_id=a.id AND g.recipient_id=$1) ORDER BY updated_at DESC,id LIMIT 26 OFFSET $2',[owner,(page-1)*25])
    // Shared list entries omit definitions until source/onward permission is checked.
    return {analyses:rows.rows.slice(0,25).map(row=>row.owner_id===owner?serialized(row,owner):{id:row.id,ownerId:row.owner_id,title:row.title,description:row.description,revision:row.revision,createdAt:row.created_at.toISOString(),updatedAt:row.updated_at.toISOString(),access:'shared'}),hasMore:rows.rows.length>25,page}
  }
  async get(owner:string,id:string){
    return transaction(this.pool,async db=>{
      await db.query('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
      const row=await resourceAccess(db,owner,'analysis',id)
      if(row.owner_id!==owner)await onwardAccess(db,'analysis',row)
      return {analysis:serialized(row,owner)}
    })
  }
  async save(owner:string,input:Save,id?:string,revision?:number){
    return this.bounded(()=>transaction(this.pool,db=>this.write(db,owner,input,id,revision)))
  }
  private async write(db:pg.PoolClient,owner:string,input:Save,id?:string,revision?:number){
      await this.active(db,owner)
      if(id){
        const previous=await db.query('SELECT revision FROM platform.analyses WHERE id=$1 AND owner_id=$2 FOR UPDATE',[id,owner])
        if(!previous.rowCount)throw absent()
        if(previous.rows[0].revision!==revision)throw new ApiError(409,'analysis_changed','Cette analyse a changé. Rechargez avant d’enregistrer.')
      }
      // Lock datasets in a stable order, so deletion cannot race dependency creation.
      const sourceList=[...new Map(sources(input.definition).map(source=>[source.versionId,source])).values()].sort((a,b)=>a.datasetId.localeCompare(b.datasetId)||a.versionId.localeCompare(b.versionId))
      for(const source of sourceList)await load(db,owner,source,true)
      // A directly submitted saved configuration must also be executable, including unique-key validation.
      await this.calculate(db,owner,input.definition)
      const analysisId=id??randomUUID()
      if(id){
        await db.query('DELETE FROM platform.dataset_dependencies WHERE kind=\'analysis\' AND resource_id=$1',[id])
        await db.query('DELETE FROM platform.analysis_sources WHERE analysis_id=$1',[id])
        await db.query('DELETE FROM platform.analysis_authorizations WHERE analysis_id=$1',[id])
        await db.query('UPDATE platform.analyses SET title=$3,description=$4,definition=$5,revision=revision+1,updated_at=now() WHERE id=$1 AND owner_id=$2',[id,owner,input.title,input.description,input.definition])
      }else await db.query('INSERT INTO platform.analyses(id,owner_id,title,description,definition) VALUES($1,$2,$3,$4,$5)',[analysisId,owner,input.title,input.description,input.definition])
      for(const source of sourceList){
        await db.query('INSERT INTO platform.analysis_sources(analysis_id,dataset_id,version_id) VALUES($1,$2,$3)',[analysisId,source.datasetId,source.versionId])
        await db.query("INSERT INTO platform.dataset_dependencies(id,dataset_id,version_id,kind,resource_id,label) VALUES($1,$2,$3,'analysis',$4,$5)",[randomUUID(),source.datasetId,source.versionId,analysisId,input.title])
      }
      await db.query("INSERT INTO platform.activity(actor_id,action,resource_id,resource_kind) VALUES($1,$2,$3,'analysis')",[owner,id?'analysis.updated':'analysis.created',analysisId])
      return {analysis:serialized((await db.query('SELECT * FROM platform.analyses WHERE id=$1',[analysisId])).rows[0]!)}
  }
  async copy(user:string,id:string,title:string){
    return this.bounded(()=>transaction(this.pool,async db=>{
      const row=await resourceAccess(db,user,'analysis',id,true)
      if(row.owner_id!==user)await onwardAccess(db,'analysis',row,true)
      const copied=await this.write(db,user,{title,description:row.description,definition:definitionSchema.parse(row.definition)})
      await db.query("INSERT INTO platform.activity(actor_id,action,resource_kind,resource_id,details) VALUES($1,'analysis.copied','analysis',$2,$3)",[user,copied.analysis.id,{sourceId:id}])
      return copied
    }))
  }
  async executeSaved(user:string,id:string,revision:number,page=1,pageSize=25){
    return this.bounded(()=>transaction(this.pool,async db=>{
      await db.query('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
      const row=await resourceAccess(db,user,'analysis',id)
      if(row.revision!==revision)throw new ApiError(409,'analysis_changed','Cette analyse a changé. Rechargez avant de calculer.')
      if(row.owner_id!==user)await onwardAccess(db,'analysis',row)
      const definition=definitionSchema.parse(row.definition)
      const result=await this.calculate(db,row.owner_id,definition,page,pageSize)
      let inspectionAvailable=true
      for(const source of sources(definition))try{await datasetAccess(db,user,source.datasetId)}catch{inspectionAvailable=false}
      // Result sharing permits the saved computation, never browsing original rows.
      if(!inspectionAvailable){
        if(result.kind==='missing'||result.kind==='outliers')result.rows=[]
        if(result.kind==='compare'){
          if(result.rowComparison)result.rowComparison.rows=[]
          result.schema.left=result.schema.left.filter((column:{id:string})=>definition.kind==='compare'&&definition.mappings.some(pair=>pair.left===column.id))
          result.schema.right=result.schema.right.filter((column:{id:string})=>definition.kind==='compare'&&definition.mappings.some(pair=>pair.right===column.id))
          result.schema.unmappedLeft=[];result.schema.unmappedRight=[]
        }
      }
      const selected=await load(db,row.owner_id,definition.source)
      const right=definition.kind==='compare'?await load(db,row.owner_id,definition.right):null
      const allowed=(side:'left'|'right')=>{
        const ids=new Set<string>(),source=side==='right'&&definition.kind==='compare'?definition.right:definition.source
        source.filters.forEach(filter=>ids.add(filter.column))
        if(definition.kind==='aggregate'){definition.measures.forEach(measure=>{if(measure.column)ids.add(measure.column)});definition.groupBy.forEach(group=>ids.add(group.column))}
        else if(definition.kind==='histogram'||definition.kind==='outliers'){ids.add(definition.column);if(definition.kind==='outliers'&&definition.groupBy)ids.add(definition.groupBy.column)}
        else if(definition.kind==='scatter'){ids.add(definition.x);ids.add(definition.y)}
        else if(definition.kind==='missing'||definition.kind==='recommend'){definition.columns.forEach(id=>ids.add(id));if(definition.kind==='missing'&&definition.groupBy)ids.add(definition.groupBy.column)}
        else{definition.mappings.forEach(pair=>ids.add(pair[side]));definition.keys.forEach(pair=>ids.add(pair[side]))}
        return ids
      }
      return {result,columns:selected.columns.filter(column=>allowed('left').has(column.id)),rightColumns:right?.columns.filter(column=>allowed('right').has(column.id))??[],inspectionAvailable}
    }))
  }
  async remove(owner:string,id:string,revision:number){
    await transaction(this.pool,async db=>{
      await this.active(db,owner)
      const selected=await db.query('SELECT revision FROM platform.analyses WHERE id=$1 AND owner_id=$2 FOR UPDATE',[id,owner])
      if(!selected.rowCount)throw absent()
      if(selected.rows[0].revision!==revision)throw new ApiError(409,'analysis_changed','Cette analyse a changé. Rechargez avant de supprimer.')
      await db.query("DELETE FROM platform.dataset_dependencies WHERE kind='analysis' AND resource_id=$1",[id])
      await db.query('DELETE FROM platform.analyses WHERE id=$1 AND owner_id=$2',[id,owner])
      await db.query("INSERT INTO platform.activity(actor_id,action,resource_id,resource_kind) VALUES($1,'analysis.deleted',$2,'analysis')",[owner,id])
    })
  }
}
