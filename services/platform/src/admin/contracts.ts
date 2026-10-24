import { z } from 'zod'
export const actions = ['account.registered','account.provisioned','account.updated','account.password_changed','account.permissions_changed','import.uploaded','import.validation_failed','import.succeeded','import.cancelled','dataset.updated','dataset.archived','dataset.deleted','dataset.version_created','dataset.suspended','dataset.resumed','dataset.inspected','analysis.created','analysis.updated','analysis.deleted','analysis.copied','dashboard.created','dashboard.updated','dashboard.deleted','dashboard.copied','sharing.granted','sharing.revoked','sharing.authorized','sharing.authorization_revoked'] as const
const page=z.coerce.number().int().min(1).max(100000).default(1)
const search=z.string().trim().max(160).default('')
const calendarDate=z.iso.date().refine(value=>!value.startsWith('0000'),'PostgreSQL ne prend pas en charge l’année zéro.')
export const usersQuery=z.object({page,search,role:z.enum(['all','admin','analyst']).default('all'),active:z.enum(['all','true','false']).default('all')}).strict()
export const datasetsQuery=z.object({page,search,owner:z.uuid().optional(),state:z.enum(['all','available','suspended','archived']).default('all')}).strict()
export const activityQuery=z.object({page,actor:z.uuid().optional(),action:z.enum(actions).optional(),kind:z.enum(['account','dataset','import','analysis','dashboard']).optional(),resource:z.uuid().optional(),outcome:z.enum(['success','failure']).optional(),from:calendarDate.optional(),to:calendarDate.optional()}).strict().refine(q=>!q.from||!q.to||q.from<=q.to,'La période est inversée.')
export const reason=z.string().trim().min(3).max(1000).refine(value=>!/[\u0000-\u001f\u007f]/.test(value))
export const permissionsBody=z.object({revision:z.number().int().positive(),role:z.enum(['admin','analyst']),active:z.boolean(),confirm:z.literal(true)}).strict()
export const suspensionBody=z.object({revision:z.number().int().positive(),suspended:z.boolean(),reason,confirm:z.literal(true)}).strict()
export type UsersQuery=z.infer<typeof usersQuery>
export type DatasetsQuery=z.infer<typeof datasetsQuery>
export type ActivityQuery=z.infer<typeof activityQuery>
