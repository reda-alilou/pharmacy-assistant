import type pg from 'pg'
import { ApiError } from '../contracts.js'
import { columnSchema, querySchema, type Column } from '../datasets/contracts.js'
import { buildQuery, expression } from '../datasets/query.js'
import type { Group, Source } from './contracts.js'
import { datasetAccess } from '../access.js'

export const invalid = (message: string) => new ApiError(422,'invalid_analysis',message)
export const numericType = (column: Column) => column.type==='integer' || column.type==='decimal'
export const compatible = (a:Column,b:Column) => a.type===b.type || numericType(a)&&numericType(b)
export type Loaded = { source: Source; title: string; number: number; rowCount:number; columns:Column[] }
export async function load(db:pg.PoolClient,owner:string,source:Source,lock=false):Promise<Loaded> {
  await datasetAccess(db,owner,source.datasetId,lock,()=>new ApiError(404,'analysis_source_unavailable','Source ou version introuvable ou accès révoqué pour ce compte.'))
  const result=await db.query(`SELECT d.title,v.version_number,v.row_count FROM platform.datasets d JOIN platform.dataset_versions v ON v.dataset_id=d.id
    WHERE d.id=$1 AND v.id=$2 ${lock?'FOR SHARE OF d':''}`,[source.datasetId,source.versionId])
  if(!result.rowCount)throw new ApiError(404,'analysis_source_unavailable','Source ou version introuvable pour ce compte.')
  const columns=await db.query('SELECT interpretation FROM platform.dataset_columns WHERE version_id=$1 ORDER BY ordinal',[source.versionId])
  return {source,title:result.rows[0].title,number:result.rows[0].version_number,rowCount:result.rows[0].row_count,columns:columns.rows.map(row=>columnSchema.parse(row.interpretation))}
}
export function column(loaded:Loaded,id:string,numeric=false):Column {
  const found=loaded.columns.find(item=>item.id===id)
  if(!found)throw invalid('Colonne absente de la version sélectionnée. Vérifiez la configuration avant de changer de version.')
  if(numeric&&!numericType(found))throw invalid('Cette opération exige une colonne numérique.')
  return found
}
export function unique(values:string[],message='Sélectionnez des colonnes différentes.') { if(new Set(values).size!==values.length)throw invalid(message) }
export class Query {
  parameters:unknown[]
  where:string
  constructor(public loaded:Loaded) {
    const built=buildQuery(loaded.source.versionId,loaded.columns,querySchema.parse({search:loaded.source.search,filters:loaded.source.filters}))
    this.parameters=[...built.countParameters];this.where=built.where
  }
  parameter(value:unknown) { this.parameters.push(value);return '$'+this.parameters.length }
  value(id:string,numeric=false) { return expression(column(this.loaded,id,numeric),this.parameter(id)) }
  text(id:string) { column(this.loaded,id);return `(r.values->>${this.parameter(id)})` }
  group(group:Group) {
    const selected=column(this.loaded,group.column), value=this.text(group.column)
    if(group.interval==='value')return value
    if(!['date','datetime'].includes(selected.type))throw invalid('Le regroupement temporel exige une date ou une date/heure.')
    return `left(${value},${{day:10,month:7,year:4}[group.interval]})`
  }
}
// Hyndman–Fan type 7: rank=(n-1)*p, exact numeric interpolation on sorted values.
// p is a fixed internal literal, never user SQL. Empty arrays yield SQL NULL.
export function quantile(array:string,p:'0.25'|'0.5'|'0.75') {
  const rank=`((cardinality(${array})-1)*${p}::numeric)`
  const low=`floor(${rank})::int+1`, high=`ceil(${rank})::int+1`
  return `((${array})[${low}]+((${array})[${high}]-(${array})[${low}])*(${rank}-floor(${rank})))`
}
export function rowsShape(rows:pg.QueryResultRow[]) {
  return rows.map(row=>({rowNumber:row.row_number,sourceLine:row.source_line,values:row.values,originalValues:row.original_values,...(row.details?{details:row.details}:{})}))
}
export const boundedPage=(page:number,pageSize:number)=>({limit:pageSize,offset:(page-1)*pageSize})
