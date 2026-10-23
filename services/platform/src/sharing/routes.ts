import express from 'express'
import { z } from 'zod'
import { requireUser } from '../contracts.js'
import type { AccountStore } from '../store.js'
import type { SharingService } from './service.js'

export function sharingRoutes(service:SharingService,accounts:AccountStore){
  const router=express.Router(),id=(value:unknown)=>z.uuid().parse(value)
  router.use((_req,res,next)=>{res.locals.sharingUser=requireUser(res.locals.auth?.session?.user??null);next()})
  const user=(res:express.Response):string=>res.locals.sharingUser.id
  const page=(value:unknown)=>z.coerce.number().int().min(1).max(100000).default(1).parse(value)
  for(const [path,kind] of [['datasets','dataset'],['analyses','analysis'],['dashboards','dashboard']] as const){
    router.get(`/${path}/:id/shares`,async(req,res)=>res.json(await service.list(user(res),kind,id(req.params.id),page(req.query.page))))
    router.post(`/${path}/:id/shares`,async(req,res)=>{await accounts.throttle('sharing:'+user(res),30);const body=z.object({email:z.email().trim().toLowerCase()}).strict().parse(req.body);res.status(201).json(await service.grant(user(res),kind,id(req.params.id),body.email))})
    router.delete(`/${path}/:id/shares/:grant`,async(req,res)=>{z.object({}).strict().parse(req.body);await service.revoke(user(res),kind,id(req.params.id),id(req.params.grant));res.status(204).end()})
  }
  router.get('/datasets/:id/onward',async(req,res)=>res.json(await service.review(user(res),id(req.params.id),page(req.query.page))))
  router.post('/datasets/:id/onward',async(req,res)=>{const body=z.object({kind:z.enum(['dashboard','analysis']),resourceId:z.uuid(),revision:z.number().int().positive(),allow:z.boolean()}).strict().parse(req.body);await service.authorize(user(res),id(req.params.id),body.kind,body.resourceId,body.revision,body.allow);res.status(204).end()})
  return router
}
