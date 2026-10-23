import { z } from 'zod'

export const LIMITS = { bytes: 10 * 1024 * 1024, rows: 25000, columns: 100, cells: 1_000_000, cellCharacters: 16384, issues: 1000, pageSize: 100, uploadsPerUser: 5 }
export const typeSchema = z.enum(['text','integer','decimal','boolean','date','datetime'])
export const columnSchema = z.object({ id: z.string().regex(/^c_[a-f0-9]{16}$/), name: z.string().max(160), originalName: z.string().max(160), type: typeSchema,
  dateFormat: z.enum(['iso','dmy','mdy']).default('iso'), booleanFormat: z.enum(['true-false','oui-non','1-0']).default('true-false') }).strict()
export const optionsSchema = z.object({ delimiter: z.enum(['auto',',',';','\t']).default('auto'), encoding: z.enum(['utf-8','windows-1252']).default('utf-8'), trim: z.boolean().default(false),
  decimalSeparator: z.enum(['.',',']).default('.'),
  missingMarkers: z.array(z.string().max(100)).max(30).default(['']) }).strict()
export const configurationSchema = optionsSchema.extend({ columns: z.array(columnSchema).min(1).max(LIMITS.columns) }).strict()
export const configureBody = z.object({ revision: z.number().int().min(0), options: optionsSchema, columns: z.array(columnSchema).min(1).max(LIMITS.columns).optional() }).strict()
export const metadataSchema = z.object({ title: z.string().trim().min(1).max(160), description: z.string().max(4000).default(''), category: z.string().trim().max(100).default(''),
  source: z.string().trim().max(500).default(''), observationDate: z.string().regex(/^\d{4}-\d{2}-\d{2}$/).nullable().default(null) }).strict()
export const publishBody = z.object({ revision: z.number().int().min(0), metadata: metadataSchema, datasetId: z.uuid().optional() }).strict()
export const patchBody = metadataSchema.extend({ revision: z.number().int().positive(), archived: z.boolean() }).strict()
export const filterSchema = z.object({ column: z.string(), op: z.enum(['contains','equals','starts_with','in','gt','gte','lt','lte','between','before','after','missing','present']), values: z.array(z.string().max(500)).max(50).default([]) }).strict()
export const querySchema = z.object({ page: z.number().int().min(1).max(25000).default(1), pageSize: z.number().int().min(1).max(LIMITS.pageSize).default(25),
  search: z.string().max(200).default(''), filters: z.array(filterSchema).max(20).default([]),
  sort: z.object({ column: z.string(), direction: z.enum(['asc','desc']) }).strict().nullable().default(null) }).strict()
export type Column = z.infer<typeof columnSchema>
export type Options = z.infer<typeof optionsSchema>
export type Configuration = z.infer<typeof configurationSchema>
export type Metadata = z.infer<typeof metadataSchema>
export type DataQuery = z.infer<typeof querySchema>
export type Issue = { row: number; line: number; column: string | null; code: string; message: string }
export type Parsed = { headers: string[]; rows: { cells: string[]; line: number }[]; issues: Issue[]; issueCount: number; delimiter: ',' | ';' | '\t'; warnings: string[] }
export type Converted = { rowNumber: number; sourceLine: number; values: Record<string,string|boolean|null>; original: Record<string,string> }
export type Validation = { valid: boolean; issueCount: number; issues: Issue[]; truncated: boolean; rowCount: number; columnCount: number }
