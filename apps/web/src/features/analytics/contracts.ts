import { z } from 'zod'
const filterSchema=z.object({column:z.string(),op:z.enum(['contains','equals','starts_with','in','gt','gte','lt','lte','between','before','after','missing','present']),values:z.array(z.string().max(500)).max(50).default([])}).strict()

export const ANALYTICS_LIMITS = { measures: 8, groups: 2, results: 200, missingColumns: 20, mappings: 10, points: 1000, pageSize: 100 }
export const sourceSchema = z.object({ datasetId: z.uuid(), versionId: z.uuid(), search: z.string().max(200).default(''), filters: z.array(filterSchema).max(20).default([]) }).strict()
export const groupSchema = z.object({ column: z.string(), interval: z.enum(['value','day','month','year']).default('value') }).strict()
export const operationSchema = z.enum(['rows','present','missing','distinct','sum','mean','median','min','max','q1','q3','stddev_sample','stddev_population'])
export const measureSchema = z.object({ operation: operationSchema, column: z.string().nullable().default(null), label: z.string().trim().max(80).default('') }).strict()
export const styleSchema = z.object({ xLabel: z.string().max(100).default(''), yLabel: z.string().max(100).default(''), unit: z.string().max(40).default(''), precision: z.number().int().min(0).max(12).default(2), legend: z.boolean().default(true) }).strict()
const common = { algorithm: z.literal('cp3-v1').default('cp3-v1'), source: sourceSchema }
export const aggregateSchema = z.object({ ...common, kind: z.literal('aggregate'), measures: z.array(measureSchema).min(1).max(8), groupBy: z.array(groupSchema).max(2).default([]),
  order: z.object({ by: z.enum(['group','measure']), index: z.number().int().min(0).max(7), direction: z.enum(['asc','desc']) }).strict().default({by:'measure',index:0,direction:'desc'}),
  limit: z.number().int().min(1).max(200).default(20), chart: z.enum(['table','kpi','bar','line','pie']).default('table'), style: styleSchema.default({xLabel:'',yLabel:'',unit:'',precision:2,legend:true}) }).strict()
export const histogramSchema = z.object({ ...common, kind: z.literal('histogram'), column: z.string(), bins: z.number().int().min(2).max(50).default(10), style: styleSchema.default({xLabel:'',yLabel:'',unit:'',precision:2,legend:true}) }).strict()
export const scatterSchema = z.object({ ...common, kind: z.literal('scatter'), x: z.string(), y: z.string(), pointLimit: z.number().int().min(1).max(1000).default(500), style: styleSchema.default({xLabel:'',yLabel:'',unit:'',precision:2,legend:true}) }).strict()
export const missingSchema = z.object({ ...common, kind: z.literal('missing'), columns: z.array(z.string()).min(1).max(20), groupBy: groupSchema.nullable().default(null), groupLimit: z.number().int().min(1).max(200).default(50) }).strict()
export const outlierSchema = z.object({ ...common, kind: z.literal('outliers'), column: z.string(), groupBy: groupSchema.nullable().default(null), factor: z.enum(['1.5','3']).default('1.5'), minimumGroupSize: z.literal(4).default(4), groupLimit: z.number().int().min(1).max(200).default(50) }).strict()
const pairSchema = z.object({ left: z.string(), right: z.string() }).strict()
export const compareSchema = z.object({ ...common, kind: z.literal('compare'), right: sourceSchema, mappings: z.array(pairSchema).max(10).default([]), keys: z.array(pairSchema).max(3).default([]) }).strict()
export const recommendationSchema = z.object({ ...common, kind: z.literal('recommend'), columns: z.array(z.string()).min(1).max(3) }).strict()
export const definitionSchema = z.discriminatedUnion('kind',[aggregateSchema,histogramSchema,scatterSchema,missingSchema,outlierSchema,compareSchema,recommendationSchema])
export const executeSchema = z.object({ definition: definitionSchema, page: z.number().int().min(1).max(50000).default(1), pageSize: z.number().int().min(1).max(100).default(25) }).strict()
export const saveSchema = z.object({ title: z.string().trim().min(1).max(160), description: z.string().max(4000).default(''), definition: definitionSchema }).strict()
export const updateSchema = saveSchema.extend({ revision: z.number().int().positive() }).strict()
export type Source = z.infer<typeof sourceSchema>
export type Group = z.infer<typeof groupSchema>
export type Definition = z.infer<typeof definitionSchema>
export type Aggregate = z.infer<typeof aggregateSchema>
export type Style = z.infer<typeof styleSchema>
export type Save = z.infer<typeof saveSchema>

export function sources(definition: Definition): Source[] { return definition.kind === 'compare' ? [definition.source,definition.right] : [definition.source] }
