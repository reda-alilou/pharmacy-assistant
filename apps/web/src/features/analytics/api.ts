import { z } from 'zod'
import { columnSchema, datasetRequest } from '@/features/datasets/api'
import { definitionSchema } from './contracts'
export { datasetRequest as analyticsRequest }

const numeric=z.string().nullable(),count=z.number().int().nonnegative()
const cell=z.union([z.string(),z.boolean(),z.null()])
const row=z.object({rowNumber:count,sourceLine:count,values:z.record(z.string(),cell),originalValues:z.record(z.string(),z.string()),details:z.record(z.string(),numeric).optional()})
const completeness=z.object({column:z.string(),present:count,missing:count,missingRate:numeric})
const conventions=z.record(z.string(),z.string())
const envelope={algorithm:z.literal('cp3-v1'),definition:definitionSchema,sources:z.array(z.object({datasetId:z.string(),versionId:z.string(),title:z.string(),versionNumber:count,importedRows:count})),conventions}
const metric=z.object({value:numeric,present:count,missing:count})
const aggregate=z.object({kind:z.literal('aggregate'),filteredRows:count,groupsTotal:count,omittedGroups:count,rows:z.array(z.object({groups:z.array(numeric),rowCount:count,share:numeric,metrics:z.array(metric)})),plot:z.object({zero:z.string(),positions:z.array(numeric)}),...envelope})
const histogram=z.object({kind:z.literal('histogram'),total:count,present:count,missing:count,minimum:numeric,maximum:numeric,constant:z.boolean().nullable(),bins:z.array(z.object({index:count,lower:z.string(),upper:z.string(),count})),...envelope})
const scatter=z.object({kind:z.literal('scatter'),filteredRows:count,pairedRows:count,missingPairs:count,omittedPoints:count,points:z.array(z.object({rowNumber:count,sourceLine:count,x:z.string(),y:z.string(),px:z.string(),py:z.string()})),...envelope})
const missing=z.object({kind:z.literal('missing'),filteredRows:count,columns:z.array(completeness),groups:z.array(z.object({key:numeric,rowCount:count,cells:z.array(completeness)})),groupsTotal:count,omittedGroups:count,affectedRows:count,page:count,pageSize:count,rows:z.array(row),...envelope})
const outliers=z.object({kind:z.literal('outliers'),filteredRows:count,present:count,missing:count,insufficientRows:count,flaggedRows:count,groupsTotal:count,omittedGroups:count,groups:z.array(z.object({key:numeric,total:count,present:count,missing:count,q1:numeric,q3:numeric,iqr:numeric,lower:numeric,upper:numeric,status:z.enum(['insufficient','zero_iqr','evaluated']),flagged:count})),page:count,pageSize:count,rows:z.array(row),...envelope})
const summary=z.object({total:count,present:count,missing:count,distinct:count,missing_rate:numeric,minimum:numeric,maximum:numeric,sum:numeric,mean:numeric,stddev_sample:numeric,q1:numeric,median:numeric,q3:numeric})
const pair=z.object({left:z.string(),right:z.string()})
const comparison=z.object({kind:z.literal('compare'),rowCounts:z.object({left:count,right:count}),schema:z.object({left:z.array(columnSchema),right:z.array(columnSchema),mappings:z.array(pair),unmappedLeft:z.array(z.string()),unmappedRight:z.array(z.string())}),statistics:z.array(z.object({leftColumn:z.string(),rightColumn:z.string(),typeChanged:z.boolean(),left:summary,right:summary})),
  rowComparison:z.object({added:count,removed:count,changed:count,unchanged:count,page:count,pageSize:count,rows:z.array(z.object({key:z.array(z.string()),status:z.enum(['added','removed','changed']),left_row:count.nullable(),right_row:count.nullable(),left_line:count.nullable(),right_line:count.nullable(),left_values:z.array(numeric).nullable(),right_values:z.array(numeric).nullable(),left_original:z.array(numeric).nullable(),right_original:z.array(numeric).nullable()}))}).nullable(),...envelope})
const option=z.object({title:z.string(),reason:z.string(),definition:definitionSchema})
const recommendations=z.object({kind:z.literal('recommend'),filteredRows:count,columns:z.array(z.object({id:z.string(),type:z.string(),distinct:count,present:count})),options:z.array(option),notes:z.array(z.string()),...envelope})
export const resultSchema=z.discriminatedUnion('kind',[aggregate,histogram,scatter,missing,outliers,comparison,recommendations])
export type Result=z.infer<typeof resultSchema>
export const analysisSchema=z.object({id:z.string(),ownerId:z.string(),title:z.string(),description:z.string(),definition:definitionSchema,revision:count,createdAt:z.string(),updatedAt:z.string(),access:z.enum(['owner','shared']).default('owner')})
export const savedSchema=z.object({analysis:analysisSchema})
export const listSchema=z.object({analyses:z.array(analysisSchema.extend({definition:definitionSchema.optional()})),hasMore:z.boolean(),page:count})
export const templatesSchema=z.object({templates:z.array(z.object({id:z.string(),title:z.string(),reason:z.string(),definition:definitionSchema.nullable()}))})
export const KIND_NAMES={aggregate:'Agrégations et classement',histogram:'Distribution numérique',scatter:'Nuage de points',missing:'Valeurs manquantes',outliers:'Valeurs atypiques (IQR)',recommend:'Recommandations de graphiques',compare:'Comparaison de datasets / versions'}
export const OP_NAMES={rows:'Nombre de lignes',present:'Valeurs présentes',missing:'Valeurs manquantes',distinct:'Valeurs distinctes présentes',sum:'Somme',mean:'Moyenne',median:'Médiane',min:'Minimum',max:'Maximum',q1:'Premier quartile',q3:'Troisième quartile',stddev_sample:'Écart-type (échantillon)',stddev_population:'Écart-type (population)'}
export const CHART_NAMES={table:'Tableau',kpi:'Carte KPI',bar:'Barres',line:'Courbe temporelle',pie:'Graphique circulaire'}

// Round only labels; exact server results remain visible in result tables.
export function decimalLabel(value:string|null,precision=2):string {
  if(value===null)return 'Non défini'
  if(!/^-?\d+(?:\.\d+)?$/.test(value))return value
  const negative=value.startsWith('-'),[whole,fraction='']=value.replace(/^-/,'').split('.')
  let scaled=BigInt(whole!+fraction.padEnd(precision,'0').slice(0,precision))
  if(Number(fraction[precision]??'0')>=5)scaled++
  const digits=scaled.toString().padStart(precision+1,'0'),integer=precision?digits.slice(0,-precision):digits
  return (negative&&scaled!==0n?'−':'')+integer.replace(/\B(?=(\d{3})+(?!\d))/g,' ')+(precision?','+digits.slice(-precision):'')
}
