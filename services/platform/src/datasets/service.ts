import { randomUUID, createHash } from 'node:crypto'
import type pg from 'pg'
import { ApiError } from '../contracts.js'
import { transaction } from '../database.js'
import { columnSchema, configurationSchema, LIMITS, optionsSchema, type Column, type Configuration, type DataQuery, type Metadata, type Options, type Validation } from './contracts.js'
import { columnId, inferColumns, parseCsv, validDate, validateRows } from './csv.js'
import { buildQuery, expression } from './query.js'

const missing = () => new ApiError(404,'dataset_not_found','Jeu de données ou import introuvable.')
const changed = () => new ApiError(409,'dataset_changed','Cet élément a changé. Actualisez avant de recommencer.')
const metadataDate = (metadata: Metadata) => { if(metadata.observationDate && !validDate(metadata.observationDate)) throw new ApiError(422,'invalid_date','Date d’observation invalide.') }
const sha = (bytes: Buffer) => createHash('sha256').update(bytes).digest('hex')
const stamp = (value: Date) => value.toISOString()
function dataset(row: Record<string,any>) {
  return { id:row.id,ownerId:row.owner_id,ownerName:row.owner_name,title:row.title,description:row.description,category:row.category,source:row.source,
    observationDate:row.observation_date ? (row.observation_date instanceof Date ? row.observation_date.toISOString().slice(0,10):row.observation_date) : null,
    archived:row.archived,revision:row.revision,createdAt:stamp(row.created_at),updatedAt:stamp(row.updated_at),versionCount:Number(row.version_count ?? 0) }
}
const version = (row: Record<string,any>) => ({id:row.id,datasetId:row.dataset_id,number:row.version_number,rowCount:row.row_count,columnCount:row.column_count,filename:row.filename,sourceSha256:row.source_sha256,configuration:configurationSchema.parse(row.configuration),createdAt:stamp(row.created_at)})
export class DatasetService {
  constructor(public pool: pg.Pool) {}
  private busy = false
  private async active(db:pg.PoolClient,owner:string){
    if(!(await db.query('SELECT id FROM platform.users WHERE id=$1 AND active FOR SHARE',[owner])).rowCount)
      throw new ApiError(401,'authentication_required','Connectez-vous pour continuer.')
  }
  async bounded<T>(work:()=>Promise<T>) {
    if(this.busy) throw new ApiError(429,'import_busy','Un fichier est en cours de traitement. Réessayez dans un instant.',1)
    this.busy=true
    try{return await work()}finally{this.busy=false}
  }
  async ready() { await this.pool.query('SELECT id FROM platform.dataset_versions LIMIT 0'); await this.pool.query('SELECT receipt_id FROM platform.import_uploads LIMIT 0') }
  async cleanup() {
    await transaction(this.pool,async db=>{
      await db.query(`UPDATE platform.import_receipts j SET status='expired' WHERE status IN ('uploaded','invalid','validated') AND EXISTS(SELECT 1 FROM platform.import_uploads u WHERE u.receipt_id=j.id AND u.expires_at<=now())`)
      await db.query('DELETE FROM platform.import_uploads WHERE expires_at<=now()')
    })
  }
  async upload(owner: string, filename: string, content: Buffer) {
    if(!filename || filename.length>255 || /[\u0000-\u001f\u007f/\\]/.test(filename) || !filename.toLowerCase().endsWith('.csv')) throw new ApiError(422,'invalid_filename','Choisissez un fichier .csv avec un nom simple (255 caractères maximum).')
    if(!content.length || content.length>LIMITS.bytes) throw new ApiError(413,'file_limit','Le fichier doit contenir entre 1 octet et 10 Mio.')
    return transaction(this.pool,async db=>{
      if(!(await db.query('SELECT id FROM platform.users WHERE id=$1 AND active FOR UPDATE',[owner])).rowCount) throw new ApiError(401,'authentication_required','Connectez-vous pour continuer.')
      const count = await db.query('SELECT count(*)::int n FROM platform.import_uploads u JOIN platform.import_receipts j ON j.id=u.receipt_id WHERE j.owner_id=$1 AND u.expires_at>now()',[owner])
      if(count.rows[0].n>=LIMITS.uploadsPerUser) throw new ApiError(429,'upload_limit','Maximum : cinq imports temporaires. Annulez un import ou attendez son expiration.')
      const id=randomUUID()
      await db.query(`INSERT INTO platform.import_receipts(id,owner_id,filename,source_sha256,byte_count,status) VALUES($1,$2,$3,$4,$5,'uploaded')`,[id,owner,filename,sha(content),content.length])
      const result=await db.query('INSERT INTO platform.import_uploads(receipt_id,content) VALUES($1,$2) RETURNING expires_at',[id,content])
      await db.query("INSERT INTO platform.activity(actor_id,action,resource_id,resource_kind) VALUES($1,'import.uploaded',$2,'import')",[owner,id])
      return {id,filename,revision:0,status:'uploaded',expiresAt:stamp(result.rows[0].expires_at)}
    })
  }
  private async uploadRecord(owner:string,id:string,db:pg.Pool|pg.PoolClient=this.pool,lock=false) {
    const result=await db.query(`SELECT j.*,u.content,u.configuration,u.validation,u.revision,u.expires_at FROM platform.import_receipts j LEFT JOIN platform.import_uploads u ON u.receipt_id=j.id WHERE j.id=$1 AND j.owner_id=$2 ${lock?'FOR UPDATE OF j':''}`,[id,owner])
    const row=result.rows[0]
    if(!row) throw missing()
    if(row.status!=='imported' && (!row.content || row.expires_at<=new Date())) throw new ApiError(410,'upload_expired','Cet import temporaire a expiré ou a été annulé. Sélectionnez à nouveau le fichier.')
    return row
  }
  async getUpload(owner:string,id:string) {
    const row=await this.uploadRecord(owner,id)
    if(row.status==='imported') {
      const published=await this.pool.query('SELECT id,dataset_id FROM platform.dataset_versions WHERE receipt_id=$1',[id])
      return {id,filename:row.filename,status:row.status,published:published.rows[0]?{datasetId:published.rows[0].dataset_id,versionId:published.rows[0].id}:null}
    }
    return this.bounded(async()=>{
      const options=optionsSchema.parse(row.configuration ? Object.fromEntries(Object.entries(row.configuration).filter(([key])=>key!=='columns')) : {})
      const parsed=await parseCsv(row.content,options)
      const configuration=row.configuration ?? {...options,delimiter:parsed.delimiter,columns:inferColumns(parsed,options)}
      return {id,filename:row.filename,revision:row.revision,status:row.status,expiresAt:stamp(row.expires_at),configuration,validation:row.validation,
        rowCount:parsed.rows.length,columnCount:parsed.headers.length,sample:parsed.rows.slice(0,20).map(row=>row.cells),
        structure:{valid:!parsed.issueCount,issueCount:parsed.issueCount,issues:parsed.issues,truncated:parsed.issueCount>parsed.issues.length},warnings:['Les types proposés portent sur les 200 premières lignes. Les dates ambiguës restent du texte. Vérifiez les conventions puis validez tout le fichier.']}
    })
  }
  async configure(owner:string,id:string,revision:number,options:Options,columns?:Column[],validate=false) {
    return this.bounded(async()=>{
      const upload=await this.uploadRecord(owner,id)
      if(upload.status==='imported' || upload.revision!==revision) throw changed()
      const parsed=await parseCsv(upload.content,options)
      const selected=columns ?? inferColumns(parsed,options)
      if(columns && (columns.length!==parsed.headers.length || columns.some((column,index)=>column.id!==columnId(parsed.headers[index]!) || column.originalName!==parsed.headers[index] || column.name!==parsed.headers[index]!.trim())))
        throw new ApiError(422,'column_mismatch','Les colonnes doivent correspondre exactement aux en-têtes du fichier.')
      // Invalid CSV headers/structure are visible in preview, never publishable.
      const configuration={...options,delimiter:parsed.delimiter,columns:selected} as Configuration
      let report:Validation|null=null
      if(validate) report=(await validateRows(parsed,configuration)).report
      const result=await transaction(this.pool,async db=>{
        await this.active(db,owner)
        const current=await this.uploadRecord(owner,id,db,true)
        if(current.revision!==revision || current.status==='imported') throw changed()
        const updated=await db.query('UPDATE platform.import_uploads SET configuration=$3,validation=$4,revision=revision+1 WHERE receipt_id=$1 AND revision=$2 RETURNING revision',[id,revision,configuration,report])
        if(!updated.rowCount) throw changed()
        await db.query('UPDATE platform.import_receipts SET status=$2,issue_count=$3 WHERE id=$1',[id,report?(report.valid?'validated':'invalid'):'uploaded',report?.issueCount ?? parsed.issueCount])
        if(report && !report.valid) await db.query("INSERT INTO platform.activity(actor_id,action,resource_id,resource_kind,details) VALUES($1,'import.validation_failed',$2,'import',$3)",[owner,id,{issueCount:report.issueCount}])
        return updated.rows[0].revision
      })
      const warnings=[...parsed.warnings,'Types proposés sur les 200 premières lignes ; seule la validation complète autorise l’import.']
      if(parsed.rows.some(row=>row.cells.some(value=>/^\d{2}\/\d{2}\/\d{4}$/.test(value)))) warnings.push('Dates avec « / » : choisissez explicitement le type Date et le format jour/mois ou mois/jour. Aucun format ambigu n’est deviné.')
      return {id,revision:result,configuration,rowCount:parsed.rows.length,columnCount:parsed.headers.length,sample:parsed.rows.slice(0,20).map(row=>row.cells),warnings,
        structure:{valid:!parsed.issueCount,issueCount:parsed.issueCount,issues:parsed.issues,truncated:parsed.issueCount>parsed.issues.length},validation:report}
    })
  }
  async report(owner:string,id:string):Promise<Validation> {
    const row=await this.uploadRecord(owner,id)
    if(!row.validation) throw new ApiError(409,'not_validated','Validez le fichier pour obtenir le rapport.')
    return row.validation
  }
  async cancel(owner:string,id:string) {
    await transaction(this.pool,async db=>{
      await this.active(db,owner)
      const row=await this.uploadRecord(owner,id,db,true)
      if(row.status==='imported') throw new ApiError(409,'already_imported','Cet import est déjà publié.')
      await db.query('DELETE FROM platform.import_uploads WHERE receipt_id=$1',[id])
      await db.query("UPDATE platform.import_receipts SET status='cancelled' WHERE id=$1",[id])
      await db.query("INSERT INTO platform.activity(actor_id,action,resource_id,resource_kind) VALUES($1,'import.cancelled',$2,'import')",[owner,id])
    })
  }
  async publish(owner:string,id:string,revision:number,metadata:Metadata,target?:string) {
    metadataDate(metadata)
    return this.bounded(async()=>{
      const upload=await this.uploadRecord(owner,id)
      if(upload.status==='imported') return this.published(owner,id)
      if(upload.revision!==revision || !upload.validation?.valid) throw new ApiError(409,'not_validated','Une validation complète de la configuration actuelle est requise.')
      const config=configurationSchema.parse(upload.configuration)
      const parsed=await parseCsv(upload.content,config)
      const checked=await validateRows(parsed,config)
      if(!checked.report.valid) throw new ApiError(409,'not_validated','Le fichier n’est pas valide.')
      await transaction(this.pool,async db=>{
        await this.active(db,owner)
        const current=await this.uploadRecord(owner,id,db,true)
        if(current.status==='imported') return
        if(current.revision!==revision || !current.validation?.valid) throw changed()
        let datasetId=target
        if(datasetId) {
          const own=await db.query('SELECT id,archived FROM platform.datasets WHERE id=$1 AND owner_id=$2 FOR UPDATE',[datasetId,owner])
          if(!own.rowCount) throw missing()
          if(own.rows[0].archived) throw new ApiError(409,'dataset_archived','Restaurez le jeu de données avant d’ajouter une version.')
        } else {
          datasetId=randomUUID()
          await db.query('INSERT INTO platform.datasets(id,owner_id,title,description,category,source,observation_date) VALUES($1,$2,$3,$4,$5,$6,$7)',[datasetId,owner,metadata.title,metadata.description,metadata.category,metadata.source,metadata.observationDate])
        }
        const next=await db.query('SELECT coalesce(max(version_number),0)+1 n FROM platform.dataset_versions WHERE dataset_id=$1',[datasetId])
        const versionId=randomUUID()
        await db.query('INSERT INTO platform.dataset_versions(id,dataset_id,receipt_id,version_number,row_count,column_count,configuration,source_sha256,filename) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9)',[versionId,datasetId,id,next.rows[0].n,parsed.rows.length,config.columns.length,config,upload.source_sha256,upload.filename])
        for(let offset=0; offset<checked.rows.length; offset+=250) {
          const batch=checked.rows.slice(offset,offset+250).map(row=>({row_number:row.rowNumber,source_line:row.sourceLine,values:row.values,original_values:row.original}))
          await db.query(`INSERT INTO platform.dataset_rows(version_id,row_number,source_line,values,original_values)
            SELECT $1,x.row_number,x.source_line,x.values,x.original_values FROM jsonb_to_recordset($2::jsonb) AS x(row_number int,source_line int,values jsonb,original_values jsonb)`,[versionId,JSON.stringify(batch)])
        }
        for(const [ordinal,column] of config.columns.entries()) {
          const value=expression(column,'$2')
          const numeric=['integer','decimal'].includes(column.type)
          const profile=await db.query(`SELECT count(*)::int AS total,count(${value})::int AS present,count(DISTINCT ${value})::int AS distinct,
            min(${column.type==='boolean'?`(${value})::text`:value})::text AS minimum,max(${column.type==='boolean'?`(${value})::text`:value})::text AS maximum
            ${numeric?`,avg((${value})::numeric(80,24))::text AS mean`:''} FROM platform.dataset_rows r WHERE r.version_id=$1`,[versionId,column.id])
          const stats=profile.rows[0]
          await db.query('INSERT INTO platform.dataset_columns(version_id,id,ordinal,original_name,display_name,data_type,interpretation,profile) VALUES($1,$2,$3,$4,$5,$6,$7,$8)',[versionId,column.id,ordinal,column.originalName,column.name,column.type,column,{...stats,missing:stats.total-stats.present}])
        }
        await db.query('UPDATE platform.datasets SET revision=revision+1,updated_at=now() WHERE id=$1',[datasetId])
        await db.query("UPDATE platform.import_receipts SET status='imported',dataset_id=$2,completed_at=now() WHERE id=$1",[id,datasetId])
        await db.query('DELETE FROM platform.import_uploads WHERE receipt_id=$1',[id])
        await db.query("INSERT INTO platform.activity(actor_id,action,resource_id,resource_kind,details) VALUES($1,'import.succeeded',$2,'dataset',$3)",[owner,datasetId,{versionId,rows:parsed.rows.length,columns:config.columns.length,importId:id}])
      })
      return this.published(owner,id)
    })
  }
  private async published(owner:string,id:string) {
    const result=await this.pool.query('SELECT v.id,v.dataset_id FROM platform.dataset_versions v JOIN platform.datasets d ON d.id=v.dataset_id WHERE v.receipt_id=$1 AND d.owner_id=$2',[id,owner])
    if(!result.rowCount) throw missing()
    return {datasetId:result.rows[0].dataset_id,versionId:result.rows[0].id}
  }
  async list(owner:string,archived:boolean,page=1) {
    const result=await this.pool.query(`SELECT d.*,u.display_name owner_name,(SELECT count(*) FROM platform.dataset_versions v WHERE v.dataset_id=d.id) version_count
      FROM platform.datasets d JOIN platform.users u ON u.id=d.owner_id WHERE d.owner_id=$1 AND d.archived=$2 ORDER BY d.updated_at DESC,d.id LIMIT 26 OFFSET $3`,[owner,archived,(page-1)*25])
    return {datasets:result.rows.slice(0,25).map(dataset),hasMore:result.rows.length>25,page}
  }
  async detail(owner:string,id:string) {
    const result=await this.pool.query(`SELECT d.*,u.display_name owner_name,(SELECT count(*) FROM platform.dataset_versions v WHERE v.dataset_id=d.id) version_count FROM platform.datasets d JOIN platform.users u ON u.id=d.owner_id WHERE d.id=$1 AND d.owner_id=$2`,[id,owner])
    if(!result.rowCount) throw missing()
    const versions=await this.pool.query('SELECT * FROM platform.dataset_versions WHERE dataset_id=$1 ORDER BY version_number DESC LIMIT 25',[id])
    return {dataset:dataset(result.rows[0]),versions:versions.rows.map(version)}
  }
  async versions(owner:string,id:string,page:number) {
    const detail=await this.detail(owner,id)
    const result=await this.pool.query('SELECT * FROM platform.dataset_versions WHERE dataset_id=$1 ORDER BY version_number DESC LIMIT 25 OFFSET $2',[id,(page-1)*25])
    return {versions:result.rows.map(version),total:detail.dataset.versionCount,page}
  }
  async version(owner:string,datasetId:string,versionId:string) {
    const result=await this.pool.query('SELECT v.* FROM platform.dataset_versions v JOIN platform.datasets d ON d.id=v.dataset_id WHERE v.dataset_id=$1 AND v.id=$2 AND d.owner_id=$3',[datasetId,versionId,owner])
    if(!result.rowCount) throw missing()
    const columns=await this.pool.query('SELECT interpretation,profile FROM platform.dataset_columns WHERE version_id=$1 ORDER BY ordinal',[versionId])
    return {version:version(result.rows[0]),columns:columns.rows.map(row=>({definition:columnSchema.parse(row.interpretation),profile:row.profile}))}
  }
  async rows(owner:string,datasetId:string,versionId:string,query:DataQuery) {
    const selected=await this.version(owner,datasetId,versionId)
    const built=buildQuery(versionId,selected.columns.map(column=>column.definition),query)
    return transaction(this.pool,async db=>{
      await db.query('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
      // Recheck ownership in the same snapshot as the data/count query.
      if(!(await db.query('SELECT 1 FROM platform.datasets WHERE id=$1 AND owner_id=$2',[datasetId,owner])).rowCount) throw missing()
      const total=await db.query(`SELECT count(*)::int total FROM platform.dataset_rows r WHERE ${built.where}`,built.countParameters)
      const parameters=[...built.parameters,query.pageSize,(query.page-1)*query.pageSize]
      const rows=await db.query(`SELECT row_number,source_line,values,original_values FROM platform.dataset_rows r WHERE ${built.where} ORDER BY ${built.order} LIMIT $${parameters.length-1} OFFSET $${parameters.length}`,parameters)
      return {versionId,total:total.rows[0].total,page:query.page,pageSize:query.pageSize,rows:rows.rows.map(row=>({rowNumber:row.row_number,sourceLine:row.source_line,values:row.values,originalValues:row.original_values}))}
    })
  }
  async update(owner:string,id:string,revision:number,metadata:Metadata,archived:boolean) {
    metadataDate(metadata)
    await transaction(this.pool,async db=>{
      await this.active(db,owner)
      const own=await db.query('SELECT revision,archived FROM platform.datasets WHERE id=$1 AND owner_id=$2 FOR UPDATE',[id,owner])
      if(!own.rowCount) throw missing()
      if(own.rows[0].revision!==revision) throw changed()
      await db.query('UPDATE platform.datasets SET title=$3,description=$4,category=$5,source=$6,observation_date=$7,archived=$8,revision=revision+1,updated_at=now() WHERE id=$1 AND owner_id=$2',[id,owner,metadata.title,metadata.description,metadata.category,metadata.source,metadata.observationDate,archived])
      await db.query("INSERT INTO platform.activity(actor_id,action,resource_id,resource_kind,details) VALUES($1,$2,$3,'dataset',$4)",[owner,own.rows[0].archived!==archived?'dataset.archived':'dataset.updated',id,{archived}])
    })
    return this.detail(owner,id)
  }
  async dependencies(owner:string,id:string) {
    const detail=await this.detail(owner,id)
    const result=await this.pool.query('SELECT kind,resource_id,label,version_id FROM platform.dataset_dependencies WHERE dataset_id=$1 ORDER BY kind,resource_id',[id])
    return {datasetId:id,title:detail.dataset.title,revision:detail.dataset.revision,versionCount:detail.dataset.versionCount,
      dependencies:result.rows.map(row=>({kind:row.kind,resourceId:row.resource_id,label:row.label,versionId:row.version_id})),canDelete:!result.rowCount}
  }
  async remove(owner:string,id:string,revision:number,confirmTitle:string) {
    await transaction(this.pool,async db=>{
      await this.active(db,owner)
      const result=await db.query('SELECT revision,title FROM platform.datasets WHERE id=$1 AND owner_id=$2 FOR UPDATE',[id,owner])
      if(!result.rowCount) throw missing()
      if(result.rows[0].revision!==revision || result.rows[0].title!==confirmTitle) throw changed()
      if((await db.query('SELECT 1 FROM platform.dataset_dependencies WHERE dataset_id=$1 LIMIT 1',[id])).rowCount) throw new ApiError(409,'dataset_dependencies','Suppression bloquée : retirez ou migrez explicitement les dépendances et les partages.')
      await db.query('DELETE FROM platform.datasets WHERE id=$1 AND owner_id=$2',[id,owner])
      await db.query("INSERT INTO platform.activity(actor_id,action,resource_id,resource_kind) VALUES($1,'dataset.deleted',$2,'dataset')",[owner,id])
    })
  }
}
