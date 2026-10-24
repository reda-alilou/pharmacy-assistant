import assert from 'node:assert/strict'
import test from 'node:test'
import { randomUUID, createHash } from 'node:crypto'
import { readFile, mkdtemp, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { basename, dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { execFile } from 'node:child_process'
import { promisify } from 'node:util'
import request from 'supertest'
import { createPool } from '../src/database.js'
import { migrate, grantRuntime } from '../src/migrations.js'
import { AdminService } from '../src/admin/service.js'
import { activityQuery, datasetsQuery, usersQuery } from '../src/admin/contracts.js'
import { DatasetService } from '../src/datasets/service.js'
import { AnalyticsService } from '../src/analytics/service.js'
import { DashboardService } from '../src/dashboards/service.js'
import { SharingService } from '../src/sharing/service.js'
import { optionsSchema } from '../src/datasets/contracts.js'
import { definitionSchema } from '../src/analytics/contracts.js'
import { saveDashboardSchema } from '../src/dashboards/contracts.js'
import { PostgresStore } from '../src/store.js'
import { createApp } from '../src/app.js'
import { csrfFor, newToken } from '../src/security.js'
import { permissions as cliPermissions } from '../src/administration.js'

const clusterUrl=new URL('postgresql://platform_test_admin:isolated-test-only-password@127.0.0.1:55433/platform_checkpoint1_test')
const name='platform_cp5_'+randomUUID().replaceAll('-','')
test('Checkpoint 5 administration and lifecycle boundaries',async t=>{
  const cluster=createPool(clusterUrl.href),adminId=randomUUID(),secondId=randomUUID(),owner=randomUUID(),reader=randomUUID()
  let db:ReturnType<typeof createPool>|undefined,runtime:ReturnType<typeof createPool>|undefined,created=false
  try{
    assert.deepEqual((await cluster.query('SELECT current_user,current_database()')).rows[0],{current_user:'platform_test_admin',current_database:'platform_checkpoint1_test'})
    assert.match(name,/^platform_cp5_[a-f0-9]{32}$/);await cluster.query(`CREATE DATABASE "${name}"`);created=true
    const adminUrl=new URL(clusterUrl);adminUrl.pathname='/'+name;db=createPool(adminUrl.href)
    for(const filename of ['0001_accounts.sql','0002_datasets.sql','0003_analyses.sql','0004_dashboards_sharing.sql']){
      const sql=await readFile(new URL('../migrations/'+filename,import.meta.url),'utf8');await db.query(sql)
      await db.query('CREATE TABLE IF NOT EXISTS platform.schema_migrations(version text PRIMARY KEY,checksum text NOT NULL,applied_at timestamptz NOT NULL DEFAULT now())')
      await db.query('INSERT INTO platform.schema_migrations(version,checksum) VALUES($1,$2)',[filename,createHash('sha256').update(sql).digest('hex')])
    }
    for(const [id,email,role] of [[adminId,'cp5-admin@example.test','admin'],[secondId,'cp5-second@example.test','admin'],[owner,'cp5-owner@example.test','analyst'],[reader,'cp5-reader@example.test','analyst']])await db.query('INSERT INTO platform.users(id,email,display_name,password_hash,role) VALUES($1,$2,$2,$3,$4)',[id,email,'synthetic-private-password-hash',role])
    await db.query("INSERT INTO platform.activity(actor_id,action,resource_kind,resource_id) VALUES($1,'import.validation_failed','import',$2)",[owner,randomUUID()])
    await t.test('populated CP4 upgrade, migration checksums, failure outcomes and least privilege',async()=>{
      const before=(await db!.query('SELECT version,checksum FROM platform.schema_migrations ORDER BY version')).rows
      await migrate(db!);await migrate(db!);await grantRuntime(db!,'platform-test-runtime-password-at-least-32-characters')
      assert.equal((await db!.query('SELECT count(*)::int n FROM platform.schema_migrations')).rows[0].n,5)
      assert.deepEqual((await db!.query('SELECT version,checksum FROM platform.schema_migrations ORDER BY version LIMIT 4')).rows,before)
      assert.equal((await db!.query("SELECT outcome FROM platform.activity WHERE action='import.validation_failed'")).rows[0].outcome,'failure')
      const url=new URL(adminUrl);url.username='pharmacy_platform';url.password='platform-test-runtime-password-at-least-32-characters';runtime=createPool(url.href)
      for(const sql of ['DELETE FROM platform.activity','UPDATE platform.dataset_rows SET source_line=source_line','UPDATE platform.schema_migrations SET checksum=checksum','CREATE TABLE platform.forbidden(id integer)'])await assert.rejects(runtime.query(sql),{code:'42501'})
    })
    const service=new AdminService(runtime!),datasets=new DatasetService(runtime!),analytics=new AnalyticsService(runtime!),dashboards=new DashboardService(runtime!,analytics),sharing=new SharingService(runtime!),store=new PostgresStore(runtime!)
    const importCsv=async(target?:string)=>{
      const upload=await datasets.upload(owner,'cp5.csv',Buffer.from('id,amount,private_note\n001,1,synthetic-secret-cell\n002,3,other-private-cell\n'))
      const preview=await datasets.getUpload(owner,upload.id);if(!('configuration'in preview))throw Error('No fixture configuration')
      const validation=await datasets.configure(owner,upload.id,0,optionsSchema.parse({}),preview.configuration.columns,true)
      return datasets.publish(owner,upload.id,validation.revision,{title:'CP5 lifecycle',description:'Synthetic',category:'Tests',source:'Synthetic fixture',observationDate:null},target)
    }
    const source=await importCsv(),widget=randomUUID(),definition=definitionSchema.parse({kind:'aggregate',source,measures:[{operation:'rows'}],chart:'kpi'})
    const analysis=await analytics.save(owner,{title:'Saved CP5 analysis',description:'',definition}),dashboard=await dashboards.save(owner,saveDashboardSchema.parse({title:'Saved CP5 dashboard',configuration:{widgets:[{id:widget,title:'Rows',definition}]}}))
    const dataGrant=await sharing.grant(owner,'dataset',source.datasetId,'cp5-reader@example.test')
    await sharing.grant(owner,'dashboard',dashboard.dashboard.id,'cp5-reader@example.test')
    await sharing.grant(owner,'analysis',analysis.analysis.id,'cp5-reader@example.test')
    const query={page:1,pageSize:25,search:'',filters:[],sort:null}
    await t.test('admin-only metadata, exact overview and no implicit content ownership',async()=>{
      for(const actor of [owner,reader,randomUUID()])await assert.rejects(service.overview(actor),{status:403})
      const overview=await service.overview(adminId)
      assert.equal(overview.totals.users,4);assert.equal(overview.totals.datasets,1);assert.equal(overview.totals.imported_rows,'2');assert.equal(overview.totals.failures_last_week,1)
      assert.equal(overview.recentImports.length,1)
      const metadata=await service.dataset(adminId,source.datasetId)
      assert.equal(metadata.dataset.ownerId,owner);assert.equal(metadata.versions[0].rowCount,2)
      assert.ok(!JSON.stringify(metadata).includes('synthetic-secret-cell'));assert.ok(!JSON.stringify(metadata).includes('profile'))
      await assert.rejects(datasets.rows(adminId,source.datasetId,source.versionId,query),{status:404})
      await assert.rejects(datasets.remove(adminId,source.datasetId,2,'CP5 lifecycle'),{status:404})
    })
    await t.test('explicit bounded inspection is audited atomically, including empty pages and typed sorting',async()=>{
      const inspected=await service.inspect(adminId,source.datasetId,source.versionId,'Contrôle de cohérence',query)
      assert.equal(inspected.rows.length,2);assert.equal(inspected.rows[0].originalValues[inspected.columns[0]!.definition!.id],'001')
      const events=await service.activity(adminId,activityQuery.parse({action:'dataset.inspected',actor:adminId,resource:source.datasetId}))
      assert.equal(events.events.length,1);assert.equal(events.events[0].details.returnedRows,2)
      assert.ok(!JSON.stringify(events).includes('synthetic-secret-cell'));assert.ok(!JSON.stringify(events).includes('password_hash'))
      await service.inspect(adminId,source.datasetId,source.versionId,'Vérification sans résultat',{...query,search:'unmatched'})
      assert.equal((await service.activity(adminId,activityQuery.parse({action:'dataset.inspected'}))).events[0].details.returnedRows,0)
      await db!.query("CREATE FUNCTION platform.test_deny_inspection() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.action='dataset.inspected' THEN RAISE EXCEPTION 'synthetic audit outage'; END IF; RETURN NEW; END $$; CREATE TRIGGER test_audit BEFORE INSERT ON platform.activity FOR EACH ROW EXECUTE FUNCTION platform.test_deny_inspection()")
      try{await assert.rejects(service.inspect(adminId,source.datasetId,source.versionId,'Vérification audit indisponible',query))}finally{await db!.query('DROP TRIGGER test_audit ON platform.activity; DROP FUNCTION platform.test_deny_inspection()')}
      assert.equal((await service.activity(adminId,activityQuery.parse({action:'dataset.inspected'}))).events.length,2)
    })
    await t.test('suspension blocks owner/grantee content, calculations, publication, mutation and new sharing without deletion',async()=>{
      const before=await service.dataset(adminId,source.datasetId)
      await service.suspend(adminId,source.datasetId,before.dataset.revision,true,'Contrôle administratif en cours')
      for(const actor of [owner,reader]){
        assert.equal((await datasets.detail(actor,source.datasetId)).dataset.suspended,true)
        await assert.rejects(datasets.version(actor,source.datasetId,source.versionId),{status:423})
        await assert.rejects(datasets.rows(actor,source.datasetId,source.versionId,query),{status:423})
        await assert.rejects(analytics.execute(actor,definition),{status:423})
        await assert.rejects(dashboards.execute(actor,dashboard.dashboard.id,widget,1,[]),{status:423})
        await assert.rejects(analytics.executeSaved(actor,analysis.analysis.id,1),{status:423})
        await assert.rejects(dashboards.copy(actor,dashboard.dashboard.id,'Blocked copy'),{status:423})
      }
      await assert.rejects(importCsv(source.datasetId),{status:423})
      await assert.rejects(datasets.update(owner,source.datasetId,3,{title:'Changed',description:'',category:'',source:'',observationDate:null},false),{status:423})
      await assert.rejects(datasets.remove(owner,source.datasetId,3,'CP5 lifecycle'),{status:423})
      await assert.rejects(sharing.grant(owner,'dataset',source.datasetId,'cp5-second@example.test'),{status:423})
      await assert.rejects(sharing.grant(owner,'dashboard',dashboard.dashboard.id,'cp5-second@example.test'),{status:423})
      assert.equal((await service.inspect(adminId,source.datasetId,source.versionId,'Inspection pendant suspension',query)).rows.length,2)
      assert.equal((await db!.query('SELECT count(*)::int n FROM platform.dataset_versions WHERE dataset_id=$1',[source.datasetId])).rows[0].n,1)
    })
    await t.test('revoke while suspended; resume preserves configurations but never recreates revoked access',async()=>{
      await sharing.revoke(owner,'dataset',source.datasetId,dataGrant.id)
      const suspended=await service.dataset(adminId,source.datasetId)
      await assert.rejects(service.suspend(adminId,source.datasetId,1,false,'Ancienne révision'),{status:409})
      await service.suspend(adminId,source.datasetId,suspended.dataset.revision,false,'Contrôle terminé')
      assert.equal((await analytics.executeSaved(reader,analysis.analysis.id,1)).inspectionAvailable,false)
      assert.equal((await dashboards.execute(reader,dashboard.dashboard.id,widget,1,[]) as any).result.filteredRows,2)
      await assert.rejects(datasets.rows(reader,source.datasetId,source.versionId,query),{status:404})
      assert.equal((await datasets.rows(owner,source.datasetId,source.versionId,query)).total,2)
    })
    await t.test('suspension blocks borrowed-source onward sharing; approval revocation survives resume',async()=>{
      await sharing.grant(owner,'dataset',source.datasetId,'cp5-reader@example.test')
      const borrowed=await analytics.save(reader,{title:'Borrowed CP5 source',description:'',definition})
      await sharing.authorize(owner,source.datasetId,'analysis',borrowed.analysis.id,1,true)
      await sharing.grant(reader,'analysis',borrowed.analysis.id,'cp5-second@example.test')
      assert.equal((await analytics.executeSaved(secondId,borrowed.analysis.id,1)).result.kind,'aggregate')
      const before=await service.dataset(adminId,source.datasetId);await service.suspend(adminId,source.datasetId,before.dataset.revision,true,'Contrôle de la diffusion indirecte')
      await assert.rejects(analytics.get(secondId,borrowed.analysis.id),{status:423})
      await assert.rejects(sharing.grant(reader,'analysis',borrowed.analysis.id,'cp5-admin@example.test'),{status:423})
      await sharing.authorize(owner,source.datasetId,'analysis',borrowed.analysis.id,1,false)
      const suspended=await service.dataset(adminId,source.datasetId);await service.suspend(adminId,source.datasetId,suspended.dataset.revision,false,'Contrôle indirect terminé')
      await assert.rejects(analytics.executeSaved(secondId,borrowed.analysis.id,1),{status:403})
      await sharing.authorize(owner,source.datasetId,'analysis',borrowed.analysis.id,1,true)
      assert.equal((await analytics.executeSaved(secondId,borrowed.analysis.id,1)).result.kind,'aggregate')
      const grant=(await sharing.list(owner,'dataset',source.datasetId)).grants.find(g=>g.email==='cp5-reader@example.test')!
      await sharing.revoke(owner,'dataset',source.datasetId,grant.id)
    })
    await t.test('optimistic permissions, session revocation, self-change and disabled-owner recipient policy',async()=>{
      const token=newToken();await store.issue(token,owner)
      await service.permissions(adminId,owner,1,'analyst',false)
      assert.equal(await store.session(token),null)
      await assert.rejects(service.permissions(adminId,owner,1,'admin',true),{status:409})
      assert.equal((await dashboards.execute(reader,dashboard.dashboard.id,widget,1,[]) as any).result.filteredRows,2)
      await service.permissions(adminId,owner,2,'analyst',true)
      const adminToken=newToken();await store.issue(adminToken,secondId)
      const result=await service.permissions(secondId,secondId,1,'analyst',true)
      assert.equal(result.sessionInvalidated,true);assert.equal(await store.session(adminToken),null)
      await assert.rejects(service.overview(secondId),{status:403})
      await assert.rejects(service.permissions(adminId,adminId,1,'analyst',true),{status:409,code:'last_admin'})
      await cliPermissions(db!,'cp5-second@example.test','admin',true)
    })
    await t.test('concurrent last-admin changes leave exactly one active administrator',async()=>{
      const users=(await service.users(adminId,usersQuery.parse({role:'admin'}))).users
      const results=await Promise.allSettled(users.map(u=>service.permissions(u.id,u.id,u.revision,'analyst',true)))
      assert.equal(results.filter(r=>r.status==='fulfilled').length,1)
      assert.equal((await db!.query("SELECT count(*)::int n FROM platform.users WHERE active AND role='admin'")).rows[0].n,1)
      await cliPermissions(db!,'cp5-admin@example.test','admin',true)
    })
    await t.test('bounded search/pagination, activity filters and safe explicit fields',async()=>{
      for(let i=0;i<27;i++)await db!.query('INSERT INTO platform.users(id,email,display_name,password_hash) VALUES($1,$2,$2,$3)',[randomUUID(),`cp5-page-${String(i).padStart(2,'0')}@example.test`,'private-synthetic-password'])
      assert.equal((await service.users(adminId,usersQuery.parse({search:'cp5-page-'}))).users.length,25)
      assert.equal((await service.users(adminId,usersQuery.parse({search:'cp5-page-',page:2}))).users.length,2)
      assert.ok(!JSON.stringify(await service.users(adminId,usersQuery.parse({}))).includes('password'))
      assert.equal((await service.datasets(adminId,datasetsQuery.parse({search:'CP5 lifecycle',owner,state:'available'}))).datasets.length,1)
      assert.equal((await service.datasets(adminId,datasetsQuery.parse({state:'suspended'}))).datasets.length,0)
      const today=new Date().toISOString().slice(0,10)
      const events=await service.activity(adminId,activityQuery.parse({actor:adminId,action:'dataset.suspended',kind:'dataset',resource:source.datasetId,outcome:'success',from:today,to:today}))
      assert.equal(events.events.length,2) // Direct-use and borrowed-source suspension scenarios.
      assert.equal(activityQuery.safeParse({from:'2026-02-30'}).success,false)
      assert.equal(activityQuery.safeParse({from:'0000-01-01'}).success,false)
      assert.equal(activityQuery.safeParse({from:'2026-03-01',to:'2026-01-01'}).success,false)
      assert.equal(usersQuery.safeParse({search:'x',password:'oops'}).success,false)
    })
    await t.test('HTTP admin role/CSRF/strict input/inspection consent and stale-session rejection',async()=>{
      const app=createApp(store,{origin:'http://127.0.0.1:5183',secureCookie:false,trustProxy:false},datasets)
      const token=newToken();await store.issue(token,adminId)
      const readerToken=newToken();await store.issue(readerToken,reader)
      const headers={'Cookie':'platform_session='+token,'Origin':'http://127.0.0.1:5183','X-CSRF-Token':csrfFor(token)}
      await request(app).get('/admin/users').expect(401)
      await request(app).get('/admin/users').set('Cookie','platform_session='+readerToken).expect(403)
      await request(app).get('/admin/overview').set(headers).expect(200)
      await request(app).get('/admin/activity?from=0000-01-01').set(headers).expect(422)
      const path=`/admin/datasets/${source.datasetId}/versions/${source.versionId}/inspect`
      await request(app).get(path).set(headers).expect(404)
      await request(app).post(path).set(headers).send({reason:'Inspect',query}).expect(422)
      await request(app).post(path).set({...headers,'X-CSRF-Token':'invalid'}).send({reason:'Inspect',confirm:true,query}).expect(403)
      await request(app).post(path).set(headers).send({reason:'Inspect',confirm:true,query:{...query,pageSize:101}}).expect(422)
      await request(app).post(path).set(headers).send({reason:'Inspect',confirm:true,query}).expect(200)
      await request(app).post(`/admin/datasets/${source.datasetId}/suspension`).set(headers).send({revision:1,suspended:true,reason:'Inspect',confirm:true,ownerId:reader}).expect(422)
      await cliPermissions(db!,'cp5-admin@example.test','admin',false).catch(async()=>{await cliPermissions(db!,'cp5-second@example.test','admin',true);await cliPermissions(db!,'cp5-admin@example.test','admin',false)})
      await request(app).get('/admin/overview').set(headers).expect(401)
      await cliPermissions(db!,'cp5-admin@example.test','admin',true)
    })
    await t.test('maintained backup restores suspension/activity/permission revisions and excludes sessions/staging',async()=>{
      const current=await service.dataset(adminId,source.datasetId);await service.suspend(adminId,source.datasetId,current.dataset.revision,true,'Suspendu pour test de restauration')
      const root=fileURLToPath(new URL('../../../',import.meta.url)),directory=await mkdtemp(join(tmpdir(),'platform-cp5-backup-')),restoreName='platform_cp5_'+randomUUID().replaceAll('-','')
      let restored:ReturnType<typeof createPool>|undefined,restoredRuntime:ReturnType<typeof createPool>|undefined,restoreCreated=false
      try{
        const dump=join(directory,'administration.dump'),python=join(root,process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python')
        await promisify(execFile)(python,['-c','import os,sys; from pharmacy_ops.backup import backup; backup({"MIGRATION_DATABASE_URL":os.environ["CP5_BACKUP_DATABASE_URL"]},sys.argv[1])',dump],{cwd:root,env:{...process.env,CP5_BACKUP_DATABASE_URL:adminUrl.href.replace('postgresql:','postgresql+psycopg:')},timeout:30000})
        assert.match(restoreName,/^platform_cp5_[a-f0-9]{32}$/);await cluster.query(`CREATE DATABASE "${restoreName}"`);restoreCreated=true
        const tool=process.platform==='win32'?join(process.env.ProgramFiles??'C:/Program Files','PostgreSQL/17/bin/pg_restore.exe'):'pg_restore'
        await promisify(execFile)(tool,['--host','127.0.0.1','--port','55433','--username','platform_test_admin','--dbname',restoreName,'--exit-on-error','--no-owner','--no-privileges',dump],{env:{...process.env,PGPASSWORD:clusterUrl.password},timeout:30000})
        const url=new URL(clusterUrl);url.pathname='/'+restoreName;restored=createPool(url.href)
        for(const table of ['users','datasets','activity','dataset_rows','dashboards','dataset_dependencies','dashboard_grants']){const sql=`SELECT row_to_json(t)::text data FROM platform.${table} t ORDER BY row_to_json(t)::text`;assert.deepEqual((await db!.query(sql)).rows,(await restored.query(sql)).rows)}
        for(const table of ['sessions','auth_throttles','import_uploads'])assert.equal((await restored.query(`SELECT count(*)::int n FROM platform.${table}`)).rows[0].n,0)
        await grantRuntime(restored,'platform-test-runtime-password-at-least-32-characters');url.username='pharmacy_platform';url.password='platform-test-runtime-password-at-least-32-characters';restoredRuntime=createPool(url.href)
        const restoredAdmin=new AdminService(restoredRuntime),restoredData=new DatasetService(restoredRuntime)
        await assert.rejects(restoredData.rows(owner,source.datasetId,source.versionId,query),{status:423})
        const snapshot=await restoredAdmin.dataset(adminId,source.datasetId);await restoredAdmin.suspend(adminId,source.datasetId,snapshot.dataset.revision,false,'Reprise contrôlée après restauration')
        assert.equal((await restoredData.rows(owner,source.datasetId,source.versionId,query)).total,2)
        assert.equal((await service.dataset(adminId,source.datasetId)).dataset.suspended,true)
      }finally{await restoredRuntime?.end();await restored?.end();if(restoreCreated){assert.match(restoreName,/^platform_cp5_[a-f0-9]{32}$/);await cluster.query(`DROP DATABASE "${restoreName}" WITH (FORCE)`)}if(dirname(resolve(directory))!==resolve(tmpdir())||!basename(directory).startsWith('platform-cp5-backup-'))throw Error('Unexpected temporary backup path');await rm(directory,{recursive:true,force:true})}
    })
  }finally{await runtime?.end();await db?.end();if(created){assert.match(name,/^platform_cp5_[a-f0-9]{32}$/);await cluster.query(`DROP DATABASE "${name}" WITH (FORCE)`)}await cluster.end()}
})
