import { z } from 'zod'
import { aggregateSchema, histogramSchema, scatterSchema } from '../analytics/contracts.js'

export const visualDefinitionSchema=z.discriminatedUnion('kind',[aggregateSchema,histogramSchema,scatterSchema])
export const widgetSchema=z.object({
  id:z.uuid(),title:z.string().trim().min(1).max(160),description:z.string().max(1000).default(''),
  definition:visualDefinitionSchema,width:z.union([z.literal(4),z.literal(6),z.literal(12)]).default(6),
  height:z.number().int().min(3).max(12).default(5),variant:z.enum(['standard','horizontal','donut']).default('standard'),
}).strict()
export const dashboardFilterSchema=z.object({
  id:z.uuid(),label:z.string().trim().min(1).max(100),kind:z.enum(['category','numeric','date','presence']),
  mappings:z.array(z.object({widgetId:z.uuid(),column:z.string()}).strict()).min(1).max(20),
  choices:z.array(z.string().max(500)).max(50).default([]),
  minimum:z.string().max(100).default(''),maximum:z.string().max(100).default(''),
  defaultValues:z.array(z.string().max(500)).max(50).default([]),readerEditable:z.boolean().default(true),
}).strict()
export const configurationSchema=z.object({algorithm:z.literal('cp4-v1').default('cp4-v1'),widgets:z.array(widgetSchema).max(20),filters:z.array(dashboardFilterSchema).max(10).default([])}).strict().superRefine((value,ctx)=>{
  for(const key of ['widgets','filters'] as const)if(new Set(value[key].map(item=>item.id)).size!==value[key].length)ctx.addIssue({code:'custom',message:'Identifiants dupliqués.',path:[key]})
  for(const [index,filter] of value.filters.entries()){
    if(new Set(filter.mappings.map(map=>map.widgetId+':'+map.column)).size!==filter.mappings.length||filter.mappings.some(map=>!value.widgets.some(widget=>widget.id===map.widgetId)))ctx.addIssue({code:'custom',message:'Correspondances explicites invalides.',path:['filters',index]})
  }
})
export const saveDashboardSchema=z.object({title:z.string().trim().min(1).max(160),description:z.string().max(4000).default(''),configuration:configurationSchema}).strict()
export const updateDashboardSchema=saveDashboardSchema.extend({revision:z.number().int().positive()}).strict()
export const filterValuesSchema=z.array(z.object({filterId:z.uuid(),values:z.array(z.string().max(500)).max(50)}).strict()).max(10)
export const widgetExecutionSchema=z.object({revision:z.number().int().positive(),values:filterValuesSchema.default([])}).strict()
export const previewWidgetSchema=z.object({configuration:configurationSchema,widgetId:z.uuid(),values:filterValuesSchema.default([])}).strict()
export type Configuration=z.infer<typeof configurationSchema>
export type Widget=z.infer<typeof widgetSchema>
export type DashboardFilter=z.infer<typeof dashboardFilterSchema>
export type FilterValues=z.infer<typeof filterValuesSchema>
export type SaveDashboard=z.infer<typeof saveDashboardSchema>
