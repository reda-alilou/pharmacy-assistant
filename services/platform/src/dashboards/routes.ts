import express from 'express'
import { z } from 'zod'
import { requireUser } from '../contracts.js'
import type { AccountStore } from '../store.js'
import type { DashboardService } from './service.js'
import { previewWidgetSchema, saveDashboardSchema, updateDashboardSchema, widgetExecutionSchema } from './contracts.js'

export function dashboardRoutes(service:DashboardService,accounts:AccountStore){
  const router=express.Router(),id=(value:unknown)=>z.uuid().parse(value)
  router.use((_req,res,next)=>{res.locals.dashboardUser=requireUser(res.locals.auth?.session?.user??null);next()})
  const user=(res:express.Response):string=>res.locals.dashboardUser.id
  const throttle=async(_req:express.Request,res:express.Response,next:express.NextFunction)=>{await accounts.throttle('dashboard:'+user(res),300);next()}
  router.get('/dashboards',async(req,res)=>res.json(await service.list(user(res),z.coerce.number().int().min(1).max(100000).default(1).parse(req.query.page))))
  router.post('/dashboards/preview',throttle,async(req,res)=>{const body=previewWidgetSchema.parse(req.body);res.json(await service.preview(user(res),body.configuration,body.widgetId,body.values))})
  router.post('/dashboards',throttle,async(req,res)=>res.status(201).json(await service.save(user(res),saveDashboardSchema.parse(req.body))))
  router.get('/dashboards/:id',async(req,res)=>res.json(await service.get(user(res),id(req.params.id))))
  router.patch('/dashboards/:id',throttle,async(req,res)=>{const {revision,...body}=updateDashboardSchema.parse(req.body);res.json(await service.save(user(res),body,id(req.params.id),revision))})
  router.post('/dashboards/:id/widgets/:widget/execute',throttle,async(req,res)=>{const body=widgetExecutionSchema.parse(req.body);res.json(await service.execute(user(res),id(req.params.id),id(req.params.widget),body.revision,body.values))})
  router.post('/dashboards/:id/copy',throttle,async(req,res)=>{const body=z.object({title:z.string().trim().min(1).max(160)}).strict().parse(req.body);res.status(201).json(await service.copy(user(res),id(req.params.id),body.title))})
  router.delete('/dashboards/:id',async(req,res)=>{const body=z.object({revision:z.number().int().positive()}).strict().parse(req.body);await service.remove(user(res),id(req.params.id),body.revision);res.status(204).end()})
  return router
}
