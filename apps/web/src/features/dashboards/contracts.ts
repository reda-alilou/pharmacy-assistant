import { z } from 'zod'
import { aggregateSchema,histogramSchema,scatterSchema } from '@/features/analytics/contracts'
export const visualDefinitionSchema=z.discriminatedUnion('kind',[aggregateSchema,histogramSchema,scatterSchema])
export const widgetSchema=z.object({id:z.uuid(),title:z.string().trim().min(1).max(160),description:z.string().max(1000).default(''),definition:visualDefinitionSchema,width:z.union([z.literal(4),z.literal(6),z.literal(12)]).default(6),height:z.number().int().min(3).max(12).default(5),variant:z.enum(['standard','horizontal','donut']).default('standard')}).strict()
export const dashboardFilterSchema=z.object({id:z.uuid(),label:z.string().trim().min(1).max(100),kind:z.enum(['category','numeric','date','presence']),mappings:z.array(z.object({widgetId:z.uuid(),column:z.string()}).strict()).min(1).max(20),choices:z.array(z.string().max(500)).max(50).default([]),minimum:z.string().max(100).default(''),maximum:z.string().max(100).default(''),defaultValues:z.array(z.string().max(500)).max(50).default([]),readerEditable:z.boolean().default(true)}).strict()
export const configurationSchema=z.object({algorithm:z.literal('cp4-v1').default('cp4-v1'),widgets:z.array(widgetSchema).max(20),filters:z.array(dashboardFilterSchema).max(10).default([])}).strict()
export const dashboardSchema=z.object({id:z.string(),ownerId:z.string(),title:z.string(),description:z.string(),configuration:configurationSchema,revision:z.number(),createdAt:z.string(),updatedAt:z.string(),access:z.enum(['owner','shared'])})
export const savedDashboardSchema=z.object({dashboard:dashboardSchema})
export const dashboardsSchema=z.object({dashboards:z.array(z.object({id:z.string(),title:z.string(),description:z.string(),revision:z.number(),access:z.enum(['owner','shared']),widgetCount:z.number(),updatedAt:z.string()})),page:z.number(),hasMore:z.boolean()})
export type Configuration=z.infer<typeof configurationSchema>
export type Widget=z.infer<typeof widgetSchema>
export type DashboardFilter=z.infer<typeof dashboardFilterSchema>
export type Dashboard=z.infer<typeof dashboardSchema>
export type FilterValues={filterId:string;values:string[]}[]
