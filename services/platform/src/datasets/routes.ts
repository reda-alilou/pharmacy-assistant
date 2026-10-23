import express from 'express'
import { z } from 'zod'
import { ApiError, requireUser } from '../contracts.js'
import type { AccountStore } from '../store.js'
import { configureBody, LIMITS, patchBody, publishBody, querySchema } from './contracts.js'
import { reportCsv } from './csv.js'
import type { DatasetService } from './service.js'

export function datasetRoutes(service:DatasetService,accounts:AccountStore) {
  const router=express.Router()
  router.use((_req,res,next)=>{res.locals.datasetUser=requireUser(res.locals.auth?.session?.user ?? null);next()})
  const owner=(res:express.Response):string=>res.locals.datasetUser.id
  const id=(value:unknown)=>z.uuid().parse(value)
  const page=(value:unknown)=>z.coerce.number().int().min(1).max(100000).default(1).parse(value)
  router.get('/datasets/limits',(_req,res)=>{res.json(LIMITS)})
  router.post('/imports',async(_req,res,next)=>{await accounts.throttle('upload:'+owner(res),10);next()},express.raw({type:'application/octet-stream',limit:LIMITS.bytes}),async(req,res)=>{
    let filename:string
    try{filename=decodeURIComponent(req.get('X-Filename')??'')}catch{throw new ApiError(422,'invalid_filename','Nom de fichier invalide.')}
    if(!Buffer.isBuffer(req.body)) throw new ApiError(415,'csv_required','Envoyez les octets du fichier CSV.')
    res.status(201).json(await service.upload(owner(res),filename,req.body))
  })
  router.get('/imports/:id',async(req,res)=>{res.json(await service.getUpload(owner(res),id(req.params.id)))})
  for(const action of ['preview','validate']) router.post(`/imports/:id/${action}`,async(req,res)=>{
    await accounts.throttle('validate:'+owner(res),60)
    const body=configureBody.parse(req.body)
    res.json(await service.configure(owner(res),id(req.params.id),body.revision,body.options,body.columns,action==='validate'))
  })
  router.get('/imports/:id/report',async(req,res)=>{
    const report=await service.report(owner(res),id(req.params.id))
    res.setHeader('Content-Disposition','attachment; filename="validation.csv"')
    res.type('text/csv; charset=utf-8').send(reportCsv(report))
  })
  router.delete('/imports/:id',async(req,res)=>{z.object({}).strict().parse(req.body);await service.cancel(owner(res),id(req.params.id));res.status(204).end()})
  router.post('/imports/:id/publish',async(req,res)=>{
    const body=publishBody.parse(req.body)
    res.status(201).json(await service.publish(owner(res),id(req.params.id),body.revision,body.metadata,body.datasetId))
  })
  router.get('/datasets',async(req,res)=>{res.json(await service.list(owner(res),z.enum(['true','false']).default('false').parse(req.query.archived)==='true',page(req.query.page)))})
  router.get('/datasets/:id',async(req,res)=>{res.json(await service.detail(owner(res),id(req.params.id)))})
  router.patch('/datasets/:id',async(req,res)=>{
    const {revision,archived,...metadata}=patchBody.parse(req.body)
    res.json(await service.update(owner(res),id(req.params.id),revision,metadata,archived))
  })
  router.get('/datasets/:id/dependencies',async(req,res)=>{res.json(await service.dependencies(owner(res),id(req.params.id)))})
  router.delete('/datasets/:id',async(req,res)=>{
    const body=z.object({revision:z.number().int().positive(),confirmTitle:z.string().min(1).max(160)}).strict().parse(req.body)
    await service.remove(owner(res),id(req.params.id),body.revision,body.confirmTitle);res.status(204).end()
  })
  router.get('/datasets/:id/versions',async(req,res)=>{res.json(await service.versions(owner(res),id(req.params.id),page(req.query.page)))})
  router.get('/datasets/:id/versions/:version',async(req,res)=>{res.json(await service.version(owner(res),id(req.params.id),id(req.params.version)))})
  // POST carries a bounded filter AST; this read operation still requires CSRF.
  router.post('/datasets/:id/versions/:version/rows',async(req,res)=>{res.json(await service.rows(owner(res),id(req.params.id),id(req.params.version),querySchema.parse(req.body)))})
  return router
}
