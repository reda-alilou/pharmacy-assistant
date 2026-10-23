import { useEffect, useState } from 'react'
import { z } from 'zod'
import { AccountError } from '@/features/accounts/api'

export const columnSchema=z.object({id:z.string(),name:z.string(),originalName:z.string(),type:z.enum(['text','integer','decimal','boolean','date','datetime']),dateFormat:z.enum(['iso','dmy','mdy']),booleanFormat:z.enum(['true-false','oui-non','1-0'])})
export const optionsSchema=z.object({delimiter:z.enum(['auto',',',';','\t']),encoding:z.enum(['utf-8','windows-1252']),trim:z.boolean(),decimalSeparator:z.enum(['.',',']),missingMarkers:z.array(z.string())})
export const configSchema=optionsSchema.extend({columns:z.array(columnSchema)})
const issueSchema=z.object({row:z.number(),line:z.number(),column:z.string().nullable(),code:z.string(),message:z.string()})
const structureSchema=z.object({valid:z.boolean(),issueCount:z.number(),issues:z.array(issueSchema),truncated:z.boolean()})
const validationSchema=structureSchema.extend({rowCount:z.number(),columnCount:z.number()})
export const previewSchema=z.object({id:z.string(),revision:z.number(),configuration:configSchema,rowCount:z.number(),columnCount:z.number(),sample:z.array(z.array(z.string())),warnings:z.array(z.string()),structure:structureSchema,validation:validationSchema.nullable()})
export const uploadSchema=z.object({id:z.string(),filename:z.string(),revision:z.number(),status:z.string(),expiresAt:z.string()})
export const importSchema=z.union([previewSchema.extend({filename:z.string(),status:z.string(),expiresAt:z.string()}),z.object({id:z.string(),filename:z.string(),status:z.literal('imported'),published:z.object({datasetId:z.string(),versionId:z.string()}).nullable()})])
export const metadataSchema=z.object({title:z.string(),description:z.string(),category:z.string(),source:z.string(),observationDate:z.string().nullable()})
export const datasetSchema=metadataSchema.extend({id:z.string(),ownerId:z.string(),ownerName:z.string(),archived:z.boolean(),revision:z.number(),createdAt:z.string(),updatedAt:z.string(),versionCount:z.number()})
export const versionSchema=z.object({id:z.string(),datasetId:z.string(),number:z.number(),rowCount:z.number(),columnCount:z.number(),filename:z.string(),sourceSha256:z.string(),configuration:configSchema,createdAt:z.string()})
export const detailSchema=z.object({dataset:datasetSchema,versions:z.array(versionSchema)})
export const listSchema=z.object({datasets:z.array(datasetSchema),hasMore:z.boolean(),page:z.number()})
export const profileSchema=z.object({definition:columnSchema,profile:z.object({total:z.number(),present:z.number(),missing:z.number(),distinct:z.number(),minimum:z.string().nullable(),maximum:z.string().nullable(),mean:z.string().nullable().optional()})})
export const versionDetailSchema=z.object({version:versionSchema,columns:z.array(profileSchema)})
export const rowsSchema=z.object({versionId:z.string(),total:z.number(),page:z.number(),pageSize:z.number(),rows:z.array(z.object({rowNumber:z.number(),sourceLine:z.number(),values:z.record(z.string(),z.union([z.string(),z.boolean(),z.null()])),originalValues:z.record(z.string(),z.string())}))})
export const dependenciesSchema=z.object({datasetId:z.string(),title:z.string(),revision:z.number(),versionCount:z.number(),canDelete:z.boolean(),dependencies:z.array(z.object({kind:z.string(),resourceId:z.string(),label:z.string(),versionId:z.string().nullable()}))})
export const publishedSchema=z.object({datasetId:z.string(),versionId:z.string()})
export type Column=z.infer<typeof columnSchema>
export type Configuration=z.infer<typeof configSchema>
export type Options=z.infer<typeof optionsSchema>
export type Preview=z.infer<typeof previewSchema>
export type Metadata=z.infer<typeof metadataSchema>
export type Dataset=z.infer<typeof datasetSchema>
export type Filter={column:string;op:string;values:string[]}
export type DataQuery={page:number;pageSize:number;search:string;filters:Filter[];sort:{column:string;direction:'asc'|'desc'}|null}
export type RequestOptions={method:string;csrfToken:string;body?:unknown;file?:File}
export async function datasetRequest<T>(path:string,schema:z.ZodType<T>,options?:RequestOptions):Promise<T>{
  const controller=new AbortController(),timer=window.setTimeout(()=>controller.abort(),60000)
  try{
    const response=await fetch('/platform-api'+path,{method:options?.method??'GET',credentials:'same-origin',cache:'no-store',signal:controller.signal,
      headers:options?{'Content-Type':options.file?'application/octet-stream':'application/json','X-CSRF-Token':options.csrfToken,...(options.file?{'X-Filename':encodeURIComponent(options.file.name)}:{})}:undefined,
      body:options?.file??(options?JSON.stringify(options.body??{}):undefined)})
    if(!response.ok){
      const error=z.object({error:z.object({code:z.string(),message:z.string()})}).safeParse(await response.json().catch(()=>null))
      throw new AccountError(response.status,error.success?error.data.error.code:'dataset_error',error.success?error.data.error.message:'Le service de données est indisponible. Vérifiez l’état de l’import avant de recommencer.')
    }
    return schema.parse(response.status===204?undefined:await response.json())
  }catch(error){if(error instanceof AccountError)throw error;throw new AccountError(0,'dataset_connection_error','Connexion interrompue ou réponse invalide. Rechargez cette page pour vérifier le résultat avant de répéter une modification.')}
  finally{window.clearTimeout(timer)}
}
export function useDatasetResource<T>(path:string|null,schema:z.ZodType<T>,nonce=0,options?:{csrfToken:string;body:unknown}){
  const body=JSON.stringify(options?.body),csrf=options?.csrfToken
  const key=JSON.stringify([path,body,nonce,csrf])
  const[state,setState]=useState<{key:string;data:T|null;error:string}>({key:'',data:null,error:''})
  useEffect(()=>{
    let active=true
    if(path)void datasetRequest(path,schema,csrf?{method:'POST',csrfToken:csrf,body:JSON.parse(body!)}:undefined).then(data=>{if(active)setState({key,data,error:''})}).catch(error=>{if(active)setState({key,data:null,error:error instanceof Error?error.message:'Service indisponible.'})})
    return()=>{active=false}
  },[path,schema,body,csrf,key])
  return state.key===key?state:{key,data:null,error:''}
}
export const DEFAULT_OPTIONS:Options={delimiter:'auto',encoding:'utf-8',decimalSeparator:'.',trim:false,missingMarkers:['']}
export const TYPE_LABELS:Record<Column['type'],string>={text:'Texte',integer:'Entier',decimal:'Décimal',boolean:'Booléen',date:'Date',datetime:'Date et heure'}
