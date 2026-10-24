import assert from 'node:assert/strict'
import { createHash,randomUUID } from 'node:crypto'
import { readFile,writeFile,mkdir,mkdtemp,rm } from 'node:fs/promises'
import { execFile } from 'node:child_process'
import { promisify } from 'node:util'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import test from 'node:test'
import request from 'supertest'
import { createPool } from '../src/database.js'
import { migrate,grantRuntime } from '../src/migrations.js'
import { PostgresStore } from '../src/store.js'
import { createApp } from '../src/app.js'
import { DatasetService } from '../src/datasets/service.js'
import { metadataSchema,optionsSchema,querySchema } from '../src/datasets/contracts.js'
import { columnId } from '../src/datasets/csv.js'

const root=fileURLToPath(new URL('../../../',import.meta.url))
const clusterUrl=new URL('postgresql://platform_test_admin:isolated-test-only-password@127.0.0.1:55433/platform_checkpoint1_test')
const name='platform_cp2_'+randomUUID().replaceAll('-','')
const metadata=metadataSchema.parse({title:'Dataset test',source:'Synthetic fixture'})
const options=optionsSchema.parse({})
const fixture='code,amount,label,active,day\n001,100,Alpha,true,2026-01-01\n002,2,Beta,false,2026-02-01\n003,,NA,false,2026-03-01\n004,0,Alpha,true,2026-04-01\n005,10,Gamma,true,2026-05-01\n'

test('Checkpoint 2 real PostgreSQL lifecycle, ownership, filtering and measured limits',async t=>{
  const cluster=createPool(clusterUrl.href)
  let admin:ReturnType<typeof createPool>|undefined,runtime:ReturnType<typeof createPool>|undefined,created=false
  const owner=randomUUID(),other=randomUUID(),administrator=randomUUID()
  try{
    const identity=await cluster.query('SELECT current_user,current_database()')
    assert.deepEqual(identity.rows[0],{current_user:'platform_test_admin',current_database:'platform_checkpoint1_test'})
    assert.match(name,/^platform_cp2_[a-f0-9]{32}$/)
    await cluster.query(`CREATE DATABASE "${name}"`);created=true
    const url=new URL(clusterUrl);url.pathname='/'+name
    admin=createPool(url.href)
    const db=admin
    await t.test('upgrade from Checkpoint 1 preserves accounts and sessions, repeated migrations/grants stay safe',async()=>{
      const sql=await readFile(new URL('../migrations/0001_accounts.sql',import.meta.url),'utf8')
      await db.query(sql)
      await db.query('CREATE TABLE platform.schema_migrations(version text PRIMARY KEY,checksum text NOT NULL,applied_at timestamptz NOT NULL DEFAULT now())')
      await db.query("INSERT INTO platform.schema_migrations(version,checksum) VALUES('0001_accounts.sql',$1)",[createHash('sha256').update(sql).digest('hex')])
      for(const [id,email,role] of [[owner,'owner@example.test','analyst'],[other,'other@example.test','analyst'],[administrator,'admin@example.test','admin']])await db.query('INSERT INTO platform.users(id,email,display_name,password_hash,role) VALUES($1,$2,$2,$3,$4)',[id,email,'preserved-synthetic-hash',role])
      await db.query("INSERT INTO platform.sessions(token_hash,user_id,expires_at,absolute_expires_at) VALUES($1,$2,now()+interval '30 minutes',now()+interval '12 hours')",['a'.repeat(64),owner])
      await migrate(db);await migrate(db);await grantRuntime(db,'platform-test-runtime-password-at-least-32-characters');await grantRuntime(db,'platform-test-runtime-password-at-least-32-characters')
      assert.equal((await db.query('SELECT count(*)::int n FROM platform.users')).rows[0].n,3)
      assert.equal((await db.query('SELECT count(*)::int n FROM platform.sessions')).rows[0].n,1)
      assert.equal((await db.query('SELECT count(*)::int n FROM platform.schema_migrations')).rows[0].n,5)
      url.username='pharmacy_platform';url.password='platform-test-runtime-password-at-least-32-characters';runtime=createPool(url.href)
    })
    if(!runtime)throw new Error('Migration failed')
    const service=new DatasetService(runtime),accounts=new PostgresStore(runtime)
    const app=createApp(accounts,{origin:'http://127.0.0.1:5177',secureCookie:false,trustProxy:false},service)
    const imported=async(content:string,title='Dataset test',target?:string)=>{
      const upload=await service.upload(owner,'fixture.csv',Buffer.from(content))
      const preview=await service.getUpload(owner,upload.id)
      if(!('configuration'in preview))throw new Error('Missing configuration')
      const configured=await service.configure(owner,upload.id,0,options,preview.configuration.columns,true)
      assert.equal(configured.validation?.valid,true)
      const result=await service.publish(owner,upload.id,configured.revision,{...metadata,title},target)
      return {...result,uploadId:upload.id,revision:configured.revision}
    }
    let first:Awaited<ReturnType<typeof imported>>
    await t.test('private upload/validation/publication, exact values, immutable rows, safe retry and restart persistence',async()=>{
      first=await imported(fixture)
      const detail=await service.detail(owner,first.datasetId)
      assert.equal(detail.versions[0]?.number,1)
      const result=await service.rows(owner,first.datasetId,first.versionId,querySchema.parse({}))
      assert.equal(result.total,5)
      assert.equal(result.rows[0]?.values[columnId('code')],'001')
      assert.equal(result.rows[0]?.values[columnId('amount')],'100')
      assert.equal(result.rows[2]?.values[columnId('amount')],null)
      assert.equal(result.rows[3]?.values[columnId('amount')],'0')
      assert.equal(result.rows[1]?.values[columnId('active')],false)
      assert.equal(result.rows[2]?.values[columnId('label')],'NA')
      assert.deepEqual(await service.publish(owner,first.uploadId,first.revision,metadata),{datasetId:first.datasetId,versionId:first.versionId})
      assert.equal((await new DatasetService(runtime!).detail(owner,first.datasetId)).versions.length,1)
      for(const table of ['dataset_versions','dataset_rows','dataset_columns']){
        await assert.rejects(runtime!.query(`UPDATE platform.${table} SET ${table==='dataset_versions'?'filename=filename':table==='dataset_columns'?'display_name=display_name':'source_line=source_line'}`),{code:'42501'})
        await assert.rejects(runtime!.query(`DELETE FROM platform.${table}`),{code:'42501'})
      }
      assert.equal((await db.query('SELECT count(*)::int n FROM platform.import_uploads WHERE receipt_id=$1',[first.uploadId])).rows[0].n,0)
      const columns=await service.version(owner,first.datasetId,first.versionId)
      const profile=columns.columns.find(column=>column.definition.id===columnId('amount'))!.profile
      assert.equal(profile.missing,1);assert.equal(profile.present,4);assert.equal(profile.distinct,4);assert.equal(Number(profile.mean),28)
    })
    await t.test('malformed/invalid files never create datasets or versions; complete validation catches late errors',async()=>{
      const before=(await service.list(owner,false)).datasets.length
      for(const content of ['a,a\n1,2\n','a,b\n1\n','a,b\n"bad,2\n']){
        const upload=await service.upload(owner,'invalid.csv',Buffer.from(content))
        const checked=await service.configure(owner,upload.id,0,options,undefined,true)
        assert.equal(checked.validation?.valid,false)
        await assert.rejects(service.publish(owner,upload.id,checked.revision,metadata),{code:'not_validated'})
        await service.cancel(owner,upload.id)
      }
      const upload=await service.upload(owner,'late.csv',Buffer.from('amount\n'+'1\n'.repeat(210)+'invalid\n'))
      const preview=await service.configure(owner,upload.id,0,options)
      const checked=await service.configure(owner,upload.id,preview.revision,options,preview.configuration.columns,true)
      assert.equal(checked.validation?.issueCount,1);assert.equal(checked.validation?.issues[0]?.row,211)
      await assert.rejects(service.publish(owner,upload.id,checked.revision,metadata),{code:'not_validated'})
      const corrected=checked.configuration.columns.map(column=>({...column,type:'text' as const}))
      const valid=await service.configure(owner,upload.id,checked.revision,options,corrected,true)
      assert.equal(valid.validation?.valid,true)
      await assert.rejects(service.publish(owner,upload.id,checked.revision,metadata),{code:'not_validated'})
      await service.cancel(owner,upload.id)
      assert.equal((await service.list(owner,false)).datasets.length,before)
    })
    await t.test('server-side pagination/search, numeric order, typed filters, AND/OR and SQL injection rejection',async()=>{
      const run=(body:unknown)=>service.rows(owner,first!.datasetId,first!.versionId,querySchema.parse(body))
      const sorted=await run({pageSize:2,sort:{column:columnId('amount'),direction:'asc'}})
      assert.equal(sorted.total,5);assert.deepEqual(sorted.rows.map(row=>row.values[columnId('amount')]),['0','2'])
      const page=await run({page:2,pageSize:2,sort:{column:columnId('amount'),direction:'asc'}})
      assert.deepEqual(page.rows.map(row=>row.values[columnId('amount')]),['10','100'])
      assert.equal((await run({search:'Gamma',pageSize:1})).total,1)
      const filters=[{column:columnId('label'),op:'in',values:['Alpha','Beta']},{column:columnId('amount'),op:'lte',values:['10']}]
      assert.equal((await run({filters})).total,2)
      for(const [filter,expected] of [
        [{column:columnId('amount'),op:'missing'},1],[{column:columnId('amount'),op:'present'},4],
        [{column:columnId('active'),op:'equals',values:['false']},2],[{column:columnId('day'),op:'between',values:['2026-02-01','2026-04-01']},3],
        [{column:columnId('label'),op:'contains',values:['ALP']},2],[{column:columnId('label'),op:'starts_with',values:['Be']},1],
      ] as const) assert.equal((await run({filters:[filter]})).total,expected)
      await assert.rejects(run({filters:[{column:columnId('amount'),op:'contains',values:['1']}]}),{code:'invalid_filter'})
      await assert.rejects(run({sort:{column:"c_'; DROP TABLE platform.users;--",direction:'asc'}}),{code:'unknown_column'})
      assert.equal((await run({search:"' OR 1=1 --"})).total,0)
      assert.equal((await run({filters:[{column:columnId('label'),op:'contains',values:['%']}]})).total,0)
    })
    await t.test('API ownership, admin boundaries, upload CSRF, archive/metadata concurrency, dependencies and deletion',async()=>{
      const browser=async(userId:string)=>{const token=(await import('../src/security.js')).newToken();await accounts.issue(token,userId);return{cookie:'platform_session='+token,csrf:(await import('../src/security.js')).csrfFor(token)}}
      const own=await browser(owner),foreign=await browser(other),adminBrowser=await browser(administrator)
      await request(app).get('/datasets').expect(401)
      for(const actor of [foreign,adminBrowser]){
        await request(app).get('/datasets/'+first!.datasetId).set('Cookie',actor.cookie).expect(404)
        await request(app).get(`/datasets/${first!.datasetId}/versions/${first!.versionId}`).set('Cookie',actor.cookie).expect(404)
        await request(app).post(`/datasets/${first!.datasetId}/versions/${first!.versionId}/rows`).set('Cookie',actor.cookie).set('Origin','http://127.0.0.1:5177').set('X-CSRF-Token',actor.csrf).send({}).expect(404)
      }
      await request(app).post('/imports').set('Cookie',own.cookie).set('Content-Type','application/octet-stream').set('Origin','http://127.0.0.1:5177').set('X-Filename','test.csv').send(Buffer.from(fixture)).expect(403)
      const uploaded=await request(app).post('/imports').set('Cookie',own.cookie).set('Content-Type','application/octet-stream').set('Origin','http://127.0.0.1:5177').set('X-CSRF-Token',own.csrf).set('X-Filename','test.csv').send(Buffer.from(fixture)).expect(201)
      await request(app).get('/imports/'+uploaded.body.id).set('Cookie',foreign.cookie).expect(404)
      await service.cancel(owner,uploaded.body.id)
      const headers=Array.from({length:100},(_,index)=>'column_'+index+'_'+'x'.repeat(100))
      const wideCsv=headers.join(',')+'\n'+headers.map(()=>1).join(',')+'\n'
      const wide=await request(app).post('/imports').set('Cookie',own.cookie).set('Content-Type','application/octet-stream').set('Origin','http://127.0.0.1:5177').set('X-CSRF-Token',own.csrf).set('X-Filename','wide.csv').send(Buffer.from(wideCsv)).expect(201)
      const widePreview=await service.getUpload(owner,wide.body.id)
      if(!('configuration'in widePreview))throw new Error('Missing wide preview')
      await request(app).post(`/imports/${wide.body.id}/validate`).set('Cookie',own.cookie).set('Origin','http://127.0.0.1:5177').set('X-CSRF-Token',own.csrf).send({revision:0,options,columns:widePreview.configuration.columns}).expect(200)
      await service.cancel(owner,wide.body.id)
      const before=(await service.detail(owner,first!.datasetId)).dataset
      await service.update(owner,first!.datasetId,before.revision,{...metadata,title:'Edited'},true)
      assert.equal((await service.list(owner,false)).datasets.length,0);assert.equal((await service.list(owner,true)).datasets.length,1)
      await assert.rejects(service.update(owner,first!.datasetId,before.revision,metadata,false),{code:'dataset_changed'})
      const archived=(await service.detail(owner,first!.datasetId)).dataset
      await service.update(owner,first!.datasetId,archived.revision,metadata,false)
      const dependency=randomUUID()
      await db.query("INSERT INTO platform.dataset_dependencies(id,dataset_id,version_id,kind,resource_id,label) VALUES($1,$2,$3,'analysis',$4,'Synthetic dependency')",[dependency,first!.datasetId,first!.versionId,randomUUID()])
      const review=await service.dependencies(owner,first!.datasetId)
      assert.equal(review.canDelete,false)
      await assert.rejects(service.remove(owner,first!.datasetId,review.revision,review.title),{code:'dataset_dependencies'})
      await db.query('DELETE FROM platform.dataset_dependencies WHERE id=$1',[dependency])
    })
    await t.test('versions are immutable and pinned; stable column IDs survive reordering; expiry and cancellation do not publish',async()=>{
      const second=await imported('label,code,amount,active,day\nChanged,009,77,false,2026-06-01\n','Ignored metadata',first!.datasetId)
      const detail=await service.detail(owner,first!.datasetId)
      assert.deepEqual(detail.versions.map(version=>version.number),[2,1]);assert.equal(detail.dataset.title,'Dataset test')
      assert.equal((await service.rows(owner,first!.datasetId,first!.versionId,querySchema.parse({}))).total,5)
      assert.equal((await service.rows(owner,second.datasetId,second.versionId,querySchema.parse({}))).rows[0]?.values[columnId('code')],'009')
      const upload=await service.upload(owner,'expired.csv',Buffer.from(fixture))
      await db.query("UPDATE platform.import_uploads SET expires_at=now()-interval '1 second' WHERE receipt_id=$1",[upload.id])
      await assert.rejects(service.getUpload(owner,upload.id),{code:'upload_expired'});await service.cleanup()
      assert.equal((await db.query('SELECT status FROM platform.import_receipts WHERE id=$1',[upload.id])).rows[0].status,'expired')
      assert.equal((await db.query('SELECT count(*)::int n FROM platform.import_uploads WHERE receipt_id=$1',[upload.id])).rows[0].n,0)
    })
    await t.test('catalogue-size and larger known fixtures benchmark import/query, limits and complete counts',async()=>{
      const records=(await readFile(join(root,'data/imports/ammps_medications_enriched.jsonl'),'utf8')).trim().split('\n').map(line=>JSON.parse(line))
      const quote=(value:unknown)=>'"'+String(value??'').replaceAll('"','""')+'"'
      const keys=['source_record_id','brand_name','active_substance','dosage','form','presentation','ppv_price_mad','source_url','source_fetched_at_utc']
      const csv=keys.join(',')+'\n'+records.map(row=>keys.map(key=>quote(row[key])).join(',')).join('\n')+'\n'
      const measurements=[]
      for(const [title,content,count] of [
        ['Catalogue 9936',csv,9936],
        ['Larger 25000','code,amount,label,active,day\n'+Array.from({length:25000},(_,index)=>`${String(index).padStart(6,'0')},${index%1000},Group ${index%10},${index%2===0},2026-10-23`).join('\n')+'\n',25000],
        ['Wide 1000000 cells',Array.from({length:100},(_,index)=>'column_'+index).join(',')+'\n'+Array.from({length:10000},(_,index)=>Array.from({length:100},(_,column)=>(index+column)%100).join(',')).join('\n')+'\n',10000],
      ] as const){
        const start=performance.now(),importedVersion=await imported(content,title),importMs=performance.now()-start
        const queryStart=performance.now()
        const data=await service.rows(owner,importedVersion.datasetId,importedVersion.versionId,querySchema.parse({pageSize:25}))
        const queryMs=performance.now()-queryStart
        assert.equal(data.total,count);assert.equal(data.rows.length,25)
        if(count===9936){const missing=await service.rows(owner,importedVersion.datasetId,importedVersion.versionId,querySchema.parse({filters:[{column:columnId('ppv_price_mad'),op:'missing'}]}));assert.equal(missing.total,1126)}
        measurements.push({title,rows:count,bytes:Buffer.byteLength(content),importMs:Math.round(importMs),queryMs:Math.round(queryMs)})
      }
      const oversized=await service.upload(owner,'too-many.csv',Buffer.from('a\n'+'1\n'.repeat(25001)))
      const invalid=await service.configure(owner,oversized.id,0,options,undefined,true)
      assert.equal(invalid.validation?.valid,false);await service.cancel(owner,oversized.id)
      const output=join(root,'artifacts/platform-cp2');await mkdir(output,{recursive:true});await writeFile(join(output,'dataset-benchmarks.json'),JSON.stringify({measuredAt:new Date().toISOString(),limits:'10 MiB; 25000 rows; 100 columns; 1000000 cells',measurements},null,2)+'\n')
    })
    await t.test('atomic publication rollback preserves prior versions and dataset deletion cascades only after review',async()=>{
      const upload=await service.upload(owner,'rollback.csv',Buffer.from(fixture))
      const validated=await service.configure(owner,upload.id,0,options,undefined,true)
      await db.query("CREATE FUNCTION platform.test_reject_row() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.row_number=3 THEN RAISE EXCEPTION 'synthetic write failure'; END IF; RETURN NEW; END $$; CREATE TRIGGER test_reject_row BEFORE INSERT ON platform.dataset_rows FOR EACH ROW EXECUTE FUNCTION platform.test_reject_row()")
      const before=(await service.detail(owner,first!.datasetId)).versions.length
      await assert.rejects(service.publish(owner,upload.id,validated.revision,metadata,first!.datasetId))
      assert.equal((await service.detail(owner,first!.datasetId)).versions.length,before)
      assert.equal((await db.query('SELECT status FROM platform.import_receipts WHERE id=$1',[upload.id])).rows[0].status,'validated')
      await db.query('DROP TRIGGER test_reject_row ON platform.dataset_rows; DROP FUNCTION platform.test_reject_row()')
      await service.cancel(owner,upload.id)
      const disabledUpload=await service.upload(owner,'disabled.csv',Buffer.from(fixture))
      const disabledValidation=await service.configure(owner,disabledUpload.id,0,options,undefined,true)
      await db.query('UPDATE platform.users SET active=false WHERE id=$1',[owner])
      await assert.rejects(service.publish(owner,disabledUpload.id,disabledValidation.revision,metadata),{code:'authentication_required'})
      await db.query('UPDATE platform.users SET active=true WHERE id=$1',[owner])
      await service.cancel(owner,disabledUpload.id)
      const review=await service.dependencies(owner,first!.datasetId)
      await assert.rejects(service.remove(owner,first!.datasetId,review.revision,'wrong title'),{code:'dataset_changed'})
      await service.remove(owner,first!.datasetId,review.revision,review.title)
      await assert.rejects(service.detail(owner,first!.datasetId),{code:'dataset_not_found'})
      assert.equal((await db.query('SELECT count(*)::int n FROM platform.dataset_rows WHERE version_id=$1',[first!.versionId])).rows[0].n,0)
    })
    await t.test('maintained backup preserves dataset versions/originals and does not revive staged uploads',async()=>{
      const temporary=await service.upload(owner,'unfinished.csv',Buffer.from(fixture))
      await service.configure(owner,temporary.id,0,options,undefined,true)
      const directory=await mkdtemp(join(tmpdir(),'platform-cp2-backup-')),restoreName='platform_cp2_'+randomUUID().replaceAll('-','')
      let restored:ReturnType<typeof createPool>|undefined,restoreCreated=false
      try{
        const dump=join(directory,'datasets.dump'),url=new URL(clusterUrl);url.pathname='/'+name
        const python=join(root,process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python')
        await promisify(execFile)(python,['-c','import os,sys; from pharmacy_ops.backup import backup; backup({"MIGRATION_DATABASE_URL":os.environ["CP2_BACKUP_DATABASE_URL"]},sys.argv[1])',dump],{cwd:root,env:{...process.env,CP2_BACKUP_DATABASE_URL:url.href.replace('postgresql:','postgresql+psycopg:')},timeout:30000})
        await cluster.query(`CREATE DATABASE "${restoreName}"`);restoreCreated=true
        const restore=process.platform==='win32'?join(process.env.ProgramFiles??'C:/Program Files','PostgreSQL/17/bin/pg_restore.exe'):'pg_restore'
        await promisify(execFile)(restore,['--host','127.0.0.1','--port','55433','--username','platform_test_admin','--dbname',restoreName,'--exit-on-error','--no-owner','--no-privileges',dump],{env:{...process.env,PGPASSWORD:clusterUrl.password},timeout:30000})
        const restoredUrl=new URL(clusterUrl);restoredUrl.pathname='/'+restoreName;restored=createPool(restoredUrl.href)
        for(const table of ['datasets','dataset_versions','dataset_columns','dataset_rows','import_receipts','activity']){
          const sql=`SELECT row_to_json(t)::text data FROM platform.${table} t ORDER BY row_to_json(t)::text`
          assert.deepEqual((await db.query(sql)).rows,(await restored.query(sql)).rows)
        }
        for(const table of ['sessions','auth_throttles','import_uploads'])assert.equal((await restored.query(`SELECT count(*)::int n FROM platform.${table}`)).rows[0].n,0)
        await assert.rejects(new DatasetService(restored).getUpload(owner,temporary.id),{code:'upload_expired'})
      }finally{await restored?.end();if(restoreCreated)await cluster.query(`DROP DATABASE "${restoreName}" WITH (FORCE)`);await rm(directory,{recursive:true,force:true})}
      await service.cancel(owner,temporary.id)
    })
  }finally{await runtime?.end();await admin?.end();if(created)await cluster.query(`DROP DATABASE "${name}" WITH (FORCE)`);await cluster.end()}
})
