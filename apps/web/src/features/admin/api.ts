import { z } from 'zod'
import { columnSchema, rowsSchema } from '@/features/datasets/api'
export const userSchema=z.object({id:z.string(),email:z.string(),displayName:z.string(),role:z.enum(['admin','analyst']),active:z.boolean(),revision:z.number(),createdAt:z.string(),updatedAt:z.string()})
export const usersSchema=z.object({users:z.array(userSchema),page:z.number(),hasMore:z.boolean()})
export const datasetSchema=z.object({id:z.string(),title:z.string(),description:z.string(),category:z.string(),source:z.string(),observationDate:z.string().nullable(),ownerId:z.string(),ownerEmail:z.string(),ownerName:z.string(),archived:z.boolean(),suspended:z.boolean(),reason:z.string(),changedAt:z.string().nullable(),changedBy:z.string().nullable(),revision:z.number(),versionCount:z.number(),rowCount:z.number(),updatedAt:z.string()})
export const datasetsSchema=z.object({datasets:z.array(datasetSchema),page:z.number(),hasMore:z.boolean()})
const versionSchema=z.object({id:z.string(),number:z.number(),filename:z.string(),rowCount:z.number(),columnCount:z.number(),createdAt:z.string()})
const receiptSchema=z.object({id:z.string(),filename:z.string(),ownerId:z.string(),ownerEmail:z.string(),datasetId:z.string().nullable(),status:z.string(),issueCount:z.number(),createdAt:z.string()})
export const detailSchema=z.object({dataset:datasetSchema,versions:z.array(versionSchema),page:z.number(),hasMore:z.boolean(),recentImports:z.array(receiptSchema)})
export const inspectionSchema=z.object({version:versionSchema,columns:z.array(z.object({definition:columnSchema,profile:z.record(z.string(),z.unknown())})),total:z.number(),page:z.number(),pageSize:z.number(),rows:rowsSchema.shape.rows})
export const overviewSchema=z.object({totals:z.object({users:z.number(),active_users:z.number(),active_admins:z.number(),datasets:z.number(),suspended_datasets:z.number(),versions:z.number(),imported_rows:z.string(),analyses:z.number(),dashboards:z.number(),failures_last_week:z.number()}),recentImports:z.array(receiptSchema),recentFailures:z.array(z.object({id:z.string(),action:z.string(),resourceKind:z.string(),resourceId:z.string(),createdAt:z.string()}))})
export const activitySchema=z.object({events:z.array(z.object({id:z.string(),actorId:z.string().nullable(),actorName:z.string().nullable(),actorEmail:z.string().nullable(),action:z.string(),resourceKind:z.string(),resourceId:z.string(),outcome:z.string(),details:z.record(z.string(),z.unknown()),createdAt:z.string()})),page:z.number(),hasMore:z.boolean(),retention:z.string()})
export const permissionResult=z.object({changed:z.boolean(),sessionInvalidated:z.boolean()})
export const ACTIONS:Record<string,string>={
  'account.registered':'Inscription','account.provisioned':'Administrateur créé','account.updated':'Profil modifié','account.password_changed':'Mot de passe modifié','account.permissions_changed':'Droits du compte modifiés',
  'import.uploaded':'CSV reçu','import.validation_failed':'Validation échouée','import.succeeded':'Import publié','import.cancelled':'Import annulé',
  'dataset.updated':'Métadonnées modifiées','dataset.archived':'Archivage modifié','dataset.deleted':'Dataset supprimé','dataset.version_created':'Version créée','dataset.suspended':'Dataset suspendu','dataset.resumed':'Dataset rétabli','dataset.inspected':'Contenu inspecté',
  'analysis.created':'Analyse créée','analysis.updated':'Analyse modifiée','analysis.deleted':'Analyse supprimée','analysis.copied':'Analyse copiée',
  'dashboard.created':'Tableau créé','dashboard.updated':'Tableau modifié','dashboard.deleted':'Tableau supprimé','dashboard.copied':'Tableau copié',
  'sharing.granted':'Accès partagé','sharing.revoked':'Accès révoqué','sharing.authorized':'Diffusion autorisée','sharing.authorization_revoked':'Autorisation révoquée',
}
export function queryString(values:Record<string,string|number>){return new URLSearchParams(Object.entries(values).filter(([,v])=>v!==''&&v!=='all').map(([k,v])=>[k,String(v)])).toString()}
