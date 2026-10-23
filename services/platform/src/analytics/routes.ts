import express from 'express'
import { z } from 'zod'
import { requireUser } from '../contracts.js'
import type { AccountStore } from '../store.js'
import { executeSchema, saveSchema, sourceSchema, updateSchema } from './contracts.js'
import type { AnalyticsService } from './service.js'

export function analyticsRoutes(service:AnalyticsService,accounts:AccountStore){
  const router=express.Router()
  router.use((_req,res,next)=>{res.locals.analysisUser=requireUser(res.locals.auth?.session?.user??null);next()})
  const owner=(res:express.Response):string=>res.locals.analysisUser.id
  const id=(value:unknown)=>z.uuid().parse(value)
  const throttle=async(_req:express.Request,res:express.Response,next:express.NextFunction)=>{await accounts.throttle('analytics:'+owner(res),60);next()}
  router.post('/analytics/execute',throttle,async(req,res)=>{const body=executeSchema.parse(req.body);res.json(await service.execute(owner(res),body.definition,body.page,body.pageSize))})
  router.post('/analytics/templates',async(req,res)=>{res.json(await service.templates(owner(res),sourceSchema.parse(req.body)))})
  router.get('/analyses',async(req,res)=>{res.json(await service.list(owner(res),z.coerce.number().int().min(1).max(100000).default(1).parse(req.query.page)))})
  router.get('/analyses/:id',async(req,res)=>{res.json(await service.get(owner(res),id(req.params.id)))})
  router.post('/analyses',throttle,async(req,res)=>{res.status(201).json(await service.save(owner(res),saveSchema.parse(req.body)))})
  router.patch('/analyses/:id',throttle,async(req,res)=>{const{revision,...body}=updateSchema.parse(req.body);res.json(await service.save(owner(res),body,id(req.params.id),revision))})
  router.delete('/analyses/:id',async(req,res)=>{const body=z.object({revision:z.number().int().positive()}).strict().parse(req.body);await service.remove(owner(res),id(req.params.id),body.revision);res.status(204).end()})
  return router
}
