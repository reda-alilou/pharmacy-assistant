import assert from 'node:assert/strict'
import { randomUUID,createHash } from 'node:crypto'
import { readFile,mkdtemp,rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { basename,dirname,join,resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { execFile } from 'node:child_process'
import { promisify } from 'node:util'
import test from 'node:test'
import request from 'supertest'
import { createPool } from '../src/database.js'
import { migrate,grantRuntime } from '../src/migrations.js'
import { DatasetService } from '../src/datasets/service.js'
import { AnalyticsService } from '../src/analytics/service.js'
import { DashboardService } from '../src/dashboards/service.js'
import { SharingService } from '../src/sharing/service.js'
import { definitionSchema,sourceSchema } from '../src/analytics/contracts.js'
import { configurationSchema,saveDashboardSchema } from '../src/dashboards/contracts.js'
import { optionsSchema } from '../src/datasets/contracts.js'
import { columnId } from '../src/datasets/csv.js'
import { PostgresStore } from '../src/store.js'
import { createApp } from '../src/app.js'
import { csrfFor,newToken } from '../src/security.js'

const clusterUrl=new URL('postgresql://platform_test_admin:isolated-test-only-password@127.0.0.1:55433/platform_checkpoint1_test')
const database='platform_cp4_'+randomUUID().replaceAll('-','')
test('Checkpoint 4 dashboards and adversarial sharing boundaries',async t=>{
  const cluster=createPool(clusterUrl.href)
  let db:ReturnType<typeof createPool>|undefined,runtime:ReturnType<typeof createPool>|undefined,created=false
  const owner=randomUUID(),analyst=randomUUID(),reader=randomUUID(),outsider=randomUUID(),admin=randomUUID()
  try{
    assert.deepEqual((await cluster.query('SELECT current_user,current_database()')).rows[0],{current_user:'platform_test_admin',current_database:'platform_checkpoint1_test'})
    assert.match(database,/^platform_cp4_[a-f0-9]{32}$/)
    await cluster.query(`CREATE DATABASE "${database}"`);created=true
    const adminUrl=new URL(clusterUrl);adminUrl.pathname='/'+database;db=createPool(adminUrl.href)
    for(const filename of ['0001_accounts.sql','0002_datasets.sql','0003_analyses.sql']){
      const sql=await readFile(new URL('../migrations/'+filename,import.meta.url),'utf8');await db.query(sql)
      await db.query('CREATE TABLE IF NOT EXISTS platform.schema_migrations(version text PRIMARY KEY,checksum text NOT NULL,applied_at timestamptz NOT NULL DEFAULT now())')
      await db.query('INSERT INTO platform.schema_migrations(version,checksum) VALUES($1,$2)',[filename,createHash('sha256').update(sql).digest('hex')])
    }
    for(const [id,email,role] of [[owner,'cp4-owner@example.test','analyst'],[analyst,'cp4-analyst@example.test','analyst'],[reader,'cp4-reader@example.test','analyst'],[outsider,'cp4-outsider@example.test','analyst'],[admin,'cp4-admin@example.test','admin']])await db.query('INSERT INTO platform.users(id,email,display_name,password_hash,role) VALUES($1,$2,$2,$3,$4)',[id,email,'synthetic-hash',role])
    const preservedAnalysis=randomUUID()
    await db.query('INSERT INTO platform.analyses(id,owner_id,title,definition) VALUES($1,$2,$3,$4)',[preservedAnalysis,owner,'Preserved CP3',definitionSchema.parse({kind:'aggregate',source:{datasetId:randomUUID(),versionId:randomUUID()},measures:[{operation:'rows'}]})])
    await t.test('explicit populated CP3 upgrade preserves revisions and restricted grants',async()=>{
      await migrate(db!);await migrate(db!);await grantRuntime(db!,'platform-test-runtime-password-at-least-32-characters')
      assert.equal((await db!.query('SELECT count(*)::int n FROM platform.schema_migrations')).rows[0].n,5)
      assert.equal((await db!.query('SELECT title,revision FROM platform.analyses WHERE id=$1',[preservedAnalysis])).rows[0].revision,1)
      const url=new URL(adminUrl);url.username='pharmacy_platform';url.password='platform-test-runtime-password-at-least-32-characters';runtime=createPool(url.href)
      for(const sql of ['UPDATE platform.dataset_rows SET source_line=source_line','DELETE FROM platform.activity','UPDATE platform.schema_migrations SET checksum=checksum','CREATE TABLE platform.forbidden(id integer)'])await assert.rejects(runtime.query(sql),{code:'42501'})
      assert.equal((await runtime.query("SELECT has_schema_privilege(current_user,'platform','CREATE') allowed")).rows[0].allowed,false)
    })
    const datasets=new DatasetService(runtime!),analytics=new AnalyticsService(runtime!),dashboards=new DashboardService(runtime!,analytics),sharing=new SharingService(runtime!)
    const imported=async(actor=owner,target?:string)=>{
      const upload=await datasets.upload(actor,'cp4.csv',Buffer.from('id,category,amount,day,secret\n001,A,1,2026-01-01,private-1\n002,A,2,2026-01-02,private-2\n003,B,3,2026-02-01,private-3\n004,B,4,2026-02-02,private-4\n005,C,5,2026-03-01,private-5\n006,C,6,2026-03-02,private-6\n'))
      const preview=await datasets.getUpload(actor,upload.id);if(!('configuration'in preview))throw new Error('No configuration')
      const validation=await datasets.configure(actor,upload.id,0,optionsSchema.parse({}),preview.configuration.columns,true)
      return datasets.publish(actor,upload.id,validation.revision,{title:'CP4 fixture',description:'',category:'',source:'Synthetic',observationDate:null},target)
    }
    const original=await imported(),source=sourceSchema.parse(original)
    const widgetId=randomUUID(),categoryFilter=randomUUID(),numericFilter=randomUUID(),dateFilter=randomUUID()
    const definition=definitionSchema.parse({kind:'aggregate',source,measures:[{operation:'rows'}],groupBy:[{column:columnId('category')}],chart:'bar'})
    const config=configurationSchema.parse({widgets:[{id:widgetId,title:'Category counts',definition}],filters:[{id:categoryFilter,label:'Category',kind:'category',choices:['A','B'],mappings:[{widgetId,column:columnId('category')}]}]})
    const save=(configuration=config,title='Saved dashboard')=>saveDashboardSchema.parse({title,configuration})
    let ownDashboard:Awaited<ReturnType<typeof dashboards.save>>,borrowedDashboard:Awaited<ReturnType<typeof dashboards.save>>,dataGrant:string,resultGrant:string
    await t.test('private dashboard lifecycle, effective filters, revisions and dependencies',async()=>{
      ownDashboard=await dashboards.save(owner,save())
      const id=ownDashboard.dashboard.id
      assert.equal((await dashboards.list(owner,1)).dashboards.length,1)
      assert.equal((await dashboards.list(reader,1)).dashboards.length,0)
      const defaults=await dashboards.execute(owner,id,widgetId,1,[]) as any
      assert.equal(defaults.result.filteredRows,4) // reset stays inside the authorized A/B perimeter
      const filtered=await dashboards.execute(owner,id,widgetId,1,[{filterId:categoryFilter,values:['A']}]) as any
      assert.equal(filtered.result.filteredRows,2)
      await assert.rejects(dashboards.execute(owner,id,widgetId,1,[{filterId:categoryFilter,values:['C'] }]),{status:422})
      await assert.rejects(dashboards.execute(owner,id,widgetId,1,[{filterId:randomUUID(),values:['A']}]),{status:403})
      assert.equal((await datasets.dependencies(owner,original.datasetId)).canDelete,false)
      for(const actor of [reader,admin])await assert.rejects(dashboards.get(actor,id),{status:404})
      await assert.rejects(dashboards.save(reader,save(),id,1),{status:404})
      await assert.rejects(dashboards.save(owner,save(),id,2),{status:409})
      await assert.rejects(dashboards.execute(owner,id,widgetId,2,[]),{status:409})
    })
    await t.test('numeric/date ranges, explicit mapping validation and unchanged saved defaults',async()=>{
      const ranged=configurationSchema.parse({...config,filters:[{id:numericFilter,label:'Amount',kind:'numeric',minimum:'2',maximum:'5',mappings:[{widgetId,column:columnId('amount')}]},{id:dateFilter,label:'Day',kind:'date',mappings:[{widgetId,column:columnId('day')}]}]})
      assert.equal((await dashboards.preview(owner,ranged,widgetId,[] ) as any).result.filteredRows,4)
      assert.equal((await dashboards.preview(owner,ranged,widgetId,[{filterId:dateFilter,values:['2026-02-01','2026-02-02']}]) as any).result.filteredRows,2)
      await assert.rejects(dashboards.preview(owner,ranged,widgetId,[{filterId:numericFilter,values:['1','6']}]),{status:422})
      await assert.rejects(dashboards.preview(owner,ranged,widgetId,[{filterId:dateFilter,values:['2026-02-30','2026-03-01']}]),{status:422})
      const upload=await datasets.upload(owner,'utc-boundary.csv',Buffer.from('id,moment\n001,2026-01-01T00:00:00.000000Z\n002,2026-01-01T23:59:59.999999Z\n003,2026-01-02T00:00:00.000000Z\n'))
      const preview=await datasets.getUpload(owner,upload.id);if(!('configuration'in preview))throw new Error('No timestamp fixture')
      const validated=await datasets.configure(owner,upload.id,0,optionsSchema.parse({}),preview.configuration.columns,true)
      const timestampSource=await datasets.publish(owner,upload.id,validated.revision,{title:'UTC boundary',description:'',category:'',source:'Synthetic',observationDate:null})
      const utc=configurationSchema.parse({widgets:[{id:widgetId,title:'UTC count',definition:{kind:'aggregate',source:timestampSource,measures:[{operation:'rows'}],chart:'kpi'}}],filters:[{id:dateFilter,label:'UTC day',kind:'date',mappings:[{widgetId,column:columnId('moment')}]}]})
      assert.equal((await dashboards.preview(owner,utc,widgetId,[{filterId:dateFilter,values:['2026-01-01','2026-01-01']}]) as any).result.filteredRows,2)
      await assert.rejects(dashboards.save(owner,save(configurationSchema.parse({...ranged,filters:[{...ranged.filters[0]!,mappings:[{widgetId,column:columnId('secret')}]}]}))),{status:422})
      assert.deepEqual((await dashboards.get(owner,ownDashboard.dashboard.id)).dashboard.configuration,config)
    })
    await t.test('dataset grants permit exploration and personal analyses, retain original ownership',async()=>{
      await assert.rejects(sharing.grant(owner,'dataset',source.datasetId,'unknown-account@example.test'),{status:422})
      await assert.rejects(sharing.grant(owner,'dataset',source.datasetId,'cp4-owner@example.test'),{status:422})
      await assert.rejects(sharing.grant(outsider,'dataset',source.datasetId,'cp4-reader@example.test'),{status:404})
      dataGrant=(await sharing.grant(owner,'dataset',source.datasetId,'cp4-analyst@example.test')).id
      assert.equal((await sharing.grant(owner,'dataset',source.datasetId,'cp4-analyst@example.test')).id,dataGrant)
      assert.equal((await datasets.list(analyst,false)).datasets[0]!.ownerId,owner)
      assert.equal((await datasets.rows(analyst,source.datasetId,source.versionId,{page:1,pageSize:25,search:'',filters:[],sort:null})).total,6)
      for(const actor of [analyst,reader,admin])await assert.rejects(datasets.remove(actor,source.datasetId,1,'CP4 fixture'),{status:404})
      await assert.rejects(datasets.update(analyst,source.datasetId,1,{title:'No',description:'',category:'',source:'',observationDate:null},false),{status:404})
      await assert.rejects(datasets.dependencies(analyst,source.datasetId),{status:404})
      const personal=await analytics.save(analyst,{title:'Personal borrowed analysis',description:'',definition})
      assert.equal(personal.analysis.ownerId,analyst)
      borrowedDashboard=await dashboards.save(analyst,save(config,'Borrowed dashboard'))
      await assert.rejects(sharing.grant(analyst,'dashboard',borrowedDashboard.dashboard.id,'cp4-reader@example.test'),{status:403,code:'onward_authorization_required'})
    })
    await t.test('presentation-only grants restrict raw access, query tampering, edits and copies',async()=>{
      resultGrant=(await sharing.grant(owner,'dashboard',ownDashboard.dashboard.id,'cp4-reader@example.test')).id
      const record=await dashboards.get(reader,ownDashboard.dashboard.id);assert.equal(record.dashboard.access,'shared')
      assert.equal((await dashboards.execute(reader,record.dashboard.id,widgetId,1,[{filterId:categoryFilter,values:['B']}]) as any).result.filteredRows,2)
      await assert.rejects(datasets.detail(reader,source.datasetId),{status:404})
      await assert.rejects(analytics.execute(reader,definition),{status:404})
      await assert.rejects(dashboards.copy(reader,record.dashboard.id,'Forbidden raw copy'),{status:404})
      await assert.rejects(dashboards.save(reader,save(),record.dashboard.id,1),{status:404})
      await assert.rejects(sharing.list(reader,'dashboard',record.dashboard.id),{status:404})
      await assert.rejects(sharing.grant(reader,'dashboard',record.dashboard.id,'cp4-outsider@example.test'),{status:404})
      const fixed=configurationSchema.parse({...config,filters:config.filters.map(filter=>({...filter,readerEditable:false}))})
      const locked=await dashboards.save(owner,save(fixed,'Fixed filters'))
      await sharing.grant(owner,'dashboard',locked.dashboard.id,'cp4-reader@example.test')
      await assert.rejects(dashboards.execute(reader,locked.dashboard.id,widgetId,1,[{filterId:categoryFilter,values:[]}]),{status:403})
      await dashboards.remove(owner,locked.dashboard.id,1)
    })
    await t.test('original-owner authorization binds to revision, revokes immediately and cannot be copied onward',async()=>{
      const id=borrowedDashboard.dashboard.id
      const review=await sharing.review(owner,source.datasetId)
      assert.ok(review.resources.some(resource=>resource.id===id&&resource.authorized===false))
      await assert.rejects(sharing.authorize(reader,source.datasetId,'dashboard',id,1,true),{status:404})
      await sharing.authorize(owner,source.datasetId,'dashboard',id,1,true)
      await sharing.grant(analyst,'dashboard',id,'cp4-reader@example.test')
      assert.equal((await dashboards.execute(reader,id,widgetId,1,[]) as any).result.filteredRows,4)
      const copied=await dashboards.copy(analyst,id,'Independent copy')
      await assert.rejects(sharing.grant(analyst,'dashboard',copied.dashboard.id,'cp4-reader@example.test'),{status:403})
      await dashboards.remove(analyst,copied.dashboard.id,1)
      await sharing.authorize(owner,source.datasetId,'dashboard',id,1,false)
      await assert.rejects(dashboards.execute(reader,id,widgetId,1,[]),{status:403})
      await sharing.authorize(owner,source.datasetId,'dashboard',id,1,true)
      const updated=await dashboards.save(analyst,save(config,'Borrowed revision 2'),id,1)
      assert.equal(updated.dashboard.revision,2)
      await assert.rejects(dashboards.get(reader,id),{status:403})
      await assert.rejects(sharing.authorize(owner,source.datasetId,'dashboard',id,1,true),{status:409})
      await sharing.authorize(owner,source.datasetId,'dashboard',id,2,true)
      assert.equal((await dashboards.get(reader,id)).dashboard.revision,2)
    })
    await t.test('analysis sharing derives only saved queries; no raw inspection without dataset grant',async()=>{
      const missing=definitionSchema.parse({kind:'missing',source,columns:[columnId('amount')]})
      const saved=await analytics.save(owner,{title:'Shared advanced summary',description:'',definition:missing})
      await sharing.grant(owner,'analysis',saved.analysis.id,'cp4-reader@example.test')
      assert.equal((await analytics.get(reader,saved.analysis.id)).analysis.access,'shared')
      const execution=await analytics.executeSaved(reader,saved.analysis.id,1)
      assert.equal(execution.inspectionAvailable,false)
      assert.deepEqual((execution.result as any).rows,[])
      assert.deepEqual(execution.columns.map(column=>column.id),[columnId('amount')])
      await assert.rejects(analytics.copy(reader,saved.analysis.id,'No raw access'),{status:404})
      await analytics.remove(owner,saved.analysis.id,1)
      await assert.rejects(analytics.get(reader,saved.analysis.id),{status:404})
    })
    await t.test('dataset/result revocation and disabled-owner policy preserve definitions without access bypass',async()=>{
      await sharing.revoke(owner,'dashboard',ownDashboard.dashboard.id,resultGrant)
      await assert.rejects(dashboards.get(reader,ownDashboard.dashboard.id),{status:404})
      await sharing.revoke(owner,'dataset',source.datasetId,dataGrant)
      await assert.rejects(datasets.version(analyst,source.datasetId,source.versionId),{status:404})
      await assert.rejects(dashboards.execute(analyst,borrowedDashboard.dashboard.id,widgetId,2,[]),{status:404})
      await assert.rejects(dashboards.execute(reader,borrowedDashboard.dashboard.id,widgetId,2,[]),{status:404})
      assert.ok((await dashboards.get(analyst,borrowedDashboard.dashboard.id)).dashboard.configuration.widgets.length)
      await sharing.grant(owner,'dashboard',ownDashboard.dashboard.id,'cp4-reader@example.test')
      await db!.query('UPDATE platform.users SET active=false WHERE id=$1',[owner])
      assert.equal((await dashboards.execute(reader,ownDashboard.dashboard.id,widgetId,1,[]) as any).result.filteredRows,4)
      await assert.rejects(dashboards.save(owner,save()),{status:401})
      await db!.query('UPDATE platform.users SET active=true WHERE id=$1',[owner])
    })
    await t.test('HTTP CSRF and strict contracts reject arbitrary reader columns, filters and resources',async()=>{
      const store=new PostgresStore(runtime!),app=createApp(store,{origin:'http://127.0.0.1:8080',secureCookie:false,trustProxy:false},datasets)
      const token=newToken();await store.issue(token,reader)
      const headers={'Cookie':'platform_session='+token,'Origin':'http://127.0.0.1:8080','X-CSRF-Token':csrfFor(token)}
      const path='/dashboards/'+ownDashboard.dashboard.id+'/widgets/'+widgetId+'/execute'
      assert.equal((await request(app).post(path).set(headers).send({revision:1,values:[],definition:{...definition,source:{...source,search:'private'}}})).status,422)
      assert.equal((await request(app).post(path).set(headers).send({revision:1,values:[{filterId:categoryFilter,values:['C']}]})).status,422)
      assert.equal((await request(app).post(path).set('Cookie',headers.Cookie).set('Origin',headers.Origin).send({revision:1})).status,403)
      assert.equal((await request(app).post('/analytics/execute').set(headers).send({definition})).status,404)
      assert.equal((await request(app).get('/datasets/'+source.datasetId).set(headers)).status,404)
      assert.equal((await request(app).get('/dashboards/'+randomUUID()).set(headers)).status,404)
    })
    await t.test('real dependencies block deletion and all new lifecycle activity excludes content',async()=>{
      const metadata=await datasets.detail(owner,source.datasetId)
      await assert.rejects(datasets.remove(owner,source.datasetId,metadata.dataset.revision,metadata.dataset.title),{status:409})
      const activity=await db!.query("SELECT action,details FROM platform.activity WHERE action LIKE 'sharing.%' OR action LIKE 'dashboard.%'")
      assert.ok(activity.rows.some(row=>row.action==='sharing.authorization_revoked'))
      assert.ok(!JSON.stringify(activity.rows).includes('private-1'))
      assert.ok(!JSON.stringify(activity.rows).includes('password'))
    })
    await t.test('maintained real backup restores dashboards, grants and onward boundaries without sessions/staging',async()=>{
      await sharing.grant(owner,'dataset',source.datasetId,'cp4-analyst@example.test')
      const savedAnalysis=await analytics.save(owner,{title:'Backup analysis',description:'',definition})
      await sharing.grant(owner,'analysis',savedAnalysis.analysis.id,'cp4-reader@example.test')
      await datasets.upload(owner,'abandoned.csv',Buffer.from('id\n001\n'))
      const root=fileURLToPath(new URL('../../../',import.meta.url)),directory=await mkdtemp(join(tmpdir(),'platform-cp4-backup-')),restoreName='platform_cp4_'+randomUUID().replaceAll('-','')
      let restored:ReturnType<typeof createPool>|undefined,restoredRuntime:ReturnType<typeof createPool>|undefined,restoreCreated=false
      try{
        const dump=join(directory,'collaboration.dump'),python=join(root,process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python')
        await promisify(execFile)(python,['-c','import os,sys; from pharmacy_ops.backup import backup; backup({"MIGRATION_DATABASE_URL":os.environ["CP4_BACKUP_DATABASE_URL"]},sys.argv[1])',dump],{cwd:root,env:{...process.env,CP4_BACKUP_DATABASE_URL:adminUrl.href.replace('postgresql:','postgresql+psycopg:')},timeout:30000})
        assert.match(restoreName,/^platform_cp4_[a-f0-9]{32}$/);await cluster.query(`CREATE DATABASE "${restoreName}"`);restoreCreated=true
        const tool=process.platform==='win32'?join(process.env.ProgramFiles??'C:/Program Files','PostgreSQL/17/bin/pg_restore.exe'):'pg_restore'
        await promisify(execFile)(tool,['--host','127.0.0.1','--port','55433','--username','platform_test_admin','--dbname',restoreName,'--exit-on-error','--no-owner','--no-privileges',dump],{env:{...process.env,PGPASSWORD:clusterUrl.password},timeout:30000})
        const url=new URL(clusterUrl);url.pathname='/'+restoreName;restored=createPool(url.href)
        for(const table of ['dashboards','dashboard_sources','dataset_grants','dashboard_grants','analysis_grants','dashboard_authorizations','analysis_authorizations','dataset_dependencies','analyses','analysis_sources','dataset_rows']){
          const sql=`SELECT row_to_json(t)::text data FROM platform.${table} t ORDER BY row_to_json(t)::text`
          assert.deepEqual((await db!.query(sql)).rows,(await restored.query(sql)).rows)
        }
        for(const table of ['sessions','auth_throttles','import_uploads'])assert.equal((await restored.query(`SELECT count(*)::int n FROM platform.${table}`)).rows[0].n,0)
        await grantRuntime(restored,'platform-test-runtime-password-at-least-32-characters')
        url.username='pharmacy_platform';url.password='platform-test-runtime-password-at-least-32-characters';restoredRuntime=createPool(url.href)
        const restoredAnalytics=new AnalyticsService(restoredRuntime),restoredDashboards=new DashboardService(restoredRuntime,restoredAnalytics),restoredSharing=new SharingService(restoredRuntime)
        assert.equal((await restoredDashboards.execute(reader,borrowedDashboard.dashboard.id,widgetId,2,[]) as any).result.filteredRows,4)
        await assert.rejects(restoredDashboards.copy(reader,ownDashboard.dashboard.id,'Unauthorized restored copy'),{status:404})
        assert.equal((await restoredAnalytics.executeSaved(reader,savedAnalysis.analysis.id,1)).inspectionAvailable,false)
        await restoredSharing.authorize(owner,source.datasetId,'dashboard',borrowedDashboard.dashboard.id,2,false)
        await assert.rejects(restoredDashboards.execute(reader,borrowedDashboard.dashboard.id,widgetId,2,[]),{status:403})
        assert.equal((await dashboards.execute(reader,borrowedDashboard.dashboard.id,widgetId,2,[]) as any).result.filteredRows,4)
      }finally{
        await restoredRuntime?.end();await restored?.end()
        if(restoreCreated){assert.match(restoreName,/^platform_cp4_[a-f0-9]{32}$/);await cluster.query(`DROP DATABASE "${restoreName}" WITH (FORCE)`)}
        if(dirname(resolve(directory))!==resolve(tmpdir())||!basename(directory).startsWith('platform-cp4-backup-'))throw new Error('Unexpected temporary backup cleanup path')
        await rm(directory,{recursive:true,force:true})
      }
    })
    await t.test('concurrent saves and original-owner approval cannot authorize an unreviewed revision',async()=>{
      const saved=await dashboards.save(analyst,save(config,'Concurrent review'))
      await sharing.authorize(owner,source.datasetId,'dashboard',saved.dashboard.id,1,true)
      await sharing.grant(analyst,'dashboard',saved.dashboard.id,'cp4-reader@example.test')
      const results=await Promise.allSettled([
        dashboards.save(analyst,save(config,'Concurrent revision 2'),saved.dashboard.id,1),
        sharing.authorize(owner,source.datasetId,'dashboard',saved.dashboard.id,1,true),
      ])
      assert.equal(results[0].status,'fulfilled')
      if(results[1].status==='rejected')assert.equal(results[1].reason.status,409)
      assert.equal((await dashboards.get(analyst,saved.dashboard.id)).dashboard.revision,2)
      await assert.rejects(dashboards.execute(reader,saved.dashboard.id,widgetId,2,[]),{status:403})
      const attempts=await Promise.allSettled([
        dashboards.save(analyst,save(config,'Concurrent winner A'),saved.dashboard.id,2),
        dashboards.save(analyst,save(config,'Concurrent winner B'),saved.dashboard.id,2),
      ])
      assert.equal(attempts.filter(result=>result.status==='fulfilled').length,1)
      const failed=attempts.find(result=>result.status==='rejected') as PromiseRejectedResult
      assert.equal(failed.reason.status,409)
      assert.equal((await dashboards.get(analyst,saved.dashboard.id)).dashboard.revision,3)
      await dashboards.remove(analyst,saved.dashboard.id,3)
    })
    await t.test('recipient and original-owner review lists are bounded, paginated and owner-only',async()=>{
      for(let index=0;index<26;index++){
        const recipient=randomUUID(),email=`page-${index}@example.test`
        await db!.query('INSERT INTO platform.users(id,email,display_name,password_hash) VALUES($1,$2,$2,$3)',[recipient,email,'synthetic-hash'])
        await sharing.grant(owner,'dataset',source.datasetId,email)
      }
      const first=await sharing.list(owner,'dataset',source.datasetId,1),second=await sharing.list(owner,'dataset',source.datasetId,2)
      assert.equal(first.grants.length,25);assert.equal(first.hasMore,true);assert.equal(second.grants.length,2)
      assert.equal(second.hasMore,false)
      assert.ok(!second.grants.some(grant=>first.grants.some(previous=>previous.id===grant.id)))
      await assert.rejects(sharing.list(reader,'dataset',source.datasetId),{status:404})
      for(let index=0;index<12;index++)await dashboards.save(analyst,save(config,'Review page '+index))
      const page1=await sharing.review(owner,source.datasetId,1),page2=await sharing.review(owner,source.datasetId,2)
      assert.equal(page1.resources.length,10);assert.equal(page1.hasMore,true)
      assert.ok(page2.resources.length>=2)
      assert.ok(!page2.resources.some(resource=>page1.resources.some(previous=>previous.id===resource.id)))
      const description=JSON.stringify(page1.resources)
      assert.ok(description.includes('category'))
      assert.ok(description.includes('Nombre de lignes'))
      assert.ok(!description.includes('private-alpha'))
      await assert.rejects(sharing.review(analyst,source.datasetId),{status:404})
    })
  }finally{
    await runtime?.end();await db?.end()
    if(created){assert.match(database,/^platform_cp4_[a-f0-9]{32}$/);await cluster.query(`DROP DATABASE "${database}" WITH (FORCE)`)}
    await cluster.end()
  }
})
