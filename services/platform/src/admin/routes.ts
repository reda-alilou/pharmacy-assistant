import express from 'express'
import { z } from 'zod'
import { requireRole } from '../contracts.js'
import type { AccountStore } from '../store.js'
import { querySchema } from '../datasets/contracts.js'
import { activityQuery, datasetsQuery, permissionsBody, reason, suspensionBody, usersQuery } from './contracts.js'
import type { AdminService } from './service.js'
export function adminRoutes(service:AdminService,accounts:AccountStore){
  const router=express.Router(),id=(value:unknown)=>z.uuid().parse(value)
  router.use('/admin',async(_req,res,next)=>{res.locals.admin=requireRole(res.locals.auth?.session?.user??null,'admin');await accounts.throttle('admin:'+res.locals.admin.id,300);next()})
  const actor=(res:express.Response):string=>res.locals.admin.id
  router.get('/admin/overview',async(_req,res)=>res.json(await service.overview(actor(res))))
  router.get('/admin/users',async(req,res)=>res.json(await service.users(actor(res),usersQuery.parse(req.query))))
  router.patch('/admin/users/:id/permissions',async(req,res)=>{const body=permissionsBody.parse(req.body);res.json(await service.permissions(actor(res),id(req.params.id),body.revision,body.role,body.active))})
  router.get('/admin/datasets',async(req,res)=>res.json(await service.datasets(actor(res),datasetsQuery.parse(req.query))))
  router.get('/admin/datasets/:id',async(req,res)=>res.json(await service.dataset(actor(res),id(req.params.id),z.coerce.number().int().min(1).max(100000).default(1).parse(req.query.page))))
  router.post('/admin/datasets/:id/suspension',async(req,res)=>{const body=suspensionBody.parse(req.body);await service.suspend(actor(res),id(req.params.id),body.revision,body.suspended,body.reason);res.status(204).end()})
  router.post('/admin/datasets/:id/versions/:version/inspect',async(req,res)=>{await accounts.throttle('admin-inspect:'+actor(res),60);const body=z.object({reason,confirm:z.literal(true),query:querySchema}).strict().parse(req.body);res.json(await service.inspect(actor(res),id(req.params.id),id(req.params.version),body.reason,body.query))})
  router.get('/admin/activity',async(req,res)=>res.json(await service.activity(actor(res),activityQuery.parse(req.query))))
  return router
}
