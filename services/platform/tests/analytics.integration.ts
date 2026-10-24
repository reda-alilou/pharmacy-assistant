import assert from 'node:assert/strict'
import { randomUUID,createHash } from 'node:crypto'
import { readFile,writeFile,mkdir,mkdtemp,rm } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { join,resolve,dirname,basename } from 'node:path'
import { tmpdir } from 'node:os'
import { execFile } from 'node:child_process'
import { promisify } from 'node:util'
import test from 'node:test'
import request from 'supertest'
import { createPool } from '../src/database.js'
import { migrate,grantRuntime } from '../src/migrations.js'
import { DatasetService } from '../src/datasets/service.js'
import { PostgresStore } from '../src/store.js'
import { AnalyticsService } from '../src/analytics/service.js'
import { definitionSchema,sourceSchema } from '../src/analytics/contracts.js'
import { optionsSchema, type Column } from '../src/datasets/contracts.js'
import { columnId, inferColumns, parseCsv, validateRows } from '../src/datasets/csv.js'
import { expression } from '../src/datasets/query.js'
import { createApp } from '../src/app.js'
import { csrfFor,newToken } from '../src/security.js'

const root=fileURLToPath(new URL('../../../',import.meta.url))
const clusterUrl=new URL('postgresql://platform_test_admin:isolated-test-only-password@127.0.0.1:55433/platform_checkpoint1_test')
const database='platform_cp3_'+randomUUID().replaceAll('-','')
const id=columnId
test('Checkpoint 3 exact analytics, advanced features, private saved definitions and upgrade/restore',async t=>{
  const cluster=createPool(clusterUrl.href)
  let db:ReturnType<typeof createPool>|undefined,runtime:ReturnType<typeof createPool>|undefined,created=false
  const owner=randomUUID(),other=randomUUID(),administrator=randomUUID()
  try{
    assert.deepEqual((await cluster.query('SELECT current_user,current_database()')).rows[0],{current_user:'platform_test_admin',current_database:'platform_checkpoint1_test'})
    assert.match(database,/^platform_cp3_[a-f0-9]{32}$/)
    await cluster.query(`CREATE DATABASE "${database}"`);created=true
    const adminUrl=new URL(clusterUrl);adminUrl.pathname='/'+database;db=createPool(adminUrl.href)
    // Populated Checkpoint 2, using the preserved exact SQL/checksums.
    for(const filename of ['0001_accounts.sql','0002_datasets.sql']){
      const sql=await readFile(new URL('../migrations/'+filename,import.meta.url),'utf8');await db.query(sql)
      await db.query('CREATE TABLE IF NOT EXISTS platform.schema_migrations(version text PRIMARY KEY,checksum text NOT NULL,applied_at timestamptz NOT NULL DEFAULT now())')
      await db.query('INSERT INTO platform.schema_migrations(version,checksum) VALUES($1,$2)',[filename,createHash('sha256').update(sql).digest('hex')])
    }
    for(const [user,email,role] of [[owner,'owner@example.test','analyst'],[other,'other@example.test','analyst'],[administrator,'admin@example.test','admin']])await db.query('INSERT INTO platform.users(id,email,display_name,password_hash,role) VALUES($1,$2,$2,$3,$4)',[user,email,'synthetic-hash',role])
    await grantRuntime(db,'platform-test-runtime-password-at-least-32-characters')
    const runtimeUrl=new URL(adminUrl);runtimeUrl.username='pharmacy_platform';runtimeUrl.password='platform-test-runtime-password-at-least-32-characters';runtime=createPool(runtimeUrl.href)
    const datasets=new DatasetService(runtime),analytics=new AnalyticsService(runtime)
    const imported=async(csv:string,target?:string,types:Record<string,Column['type']>={},actor=owner)=>{
      const upload=await datasets.upload(actor,'analytics.csv',Buffer.from(csv))
      const preview=await datasets.getUpload(actor,upload.id);if(!('configuration'in preview))throw new Error('Missing configuration')
      const validated=await datasets.configure(actor,upload.id,0,optionsSchema.parse({}),preview.configuration.columns.map(c=>({...c,type:types[c.name]??c.type})),true)
      assert.equal(validated.validation?.valid,true)
      return datasets.publish(actor,upload.id,validated.revision,{title:'Analytics fixture',description:'',category:'',source:'Synthetic exact fixture',observationDate:null},target)
    }
    const fixture='id,group,amount,second,empty,day,form,ppv_price_mad,recorded_conflicts,source\n'+[
      '001,A,0,10,,2026-01-01,Tablet,0,0,Alpha','002,A,1,11,,2026-01-02,Tablet,1,1,Alpha','003,A,2,12,,2026-02-01,Tablet,2,0,Beta',
      '004,A,3,13,,2026-02-02,Tablet,3,0,Beta','005,A,100,110,,2026-03-01,Tablet,100,2,Alpha','006,A,,14,,2026-03-02,Tablet,,0,Beta',
      '007,B,4,14,,2026-01-03,Capsule,4,0,Alpha','008,B,4,14,,2026-02-03,Capsule,4,0,Beta','009,B,4,14,,2026-03-03,Capsule,4,0,Alpha',
      '010,B,4,14,,2026-03-04,Capsule,4,0,Beta','011,C,5,15,,2026-03-05,Syrup,5,0,Alpha','012,C,,16,,2026-03-06,Syrup,,0,Beta',
    ].join('\n')+'\n'
    // Seed the actual CP2 representation before upgrading. Current production
    // code intentionally requires its current migration and emits newer events;
    // it must not be run against this historical two-revision schema.
    const parsed=await parseCsv(Buffer.from(fixture),optionsSchema.parse({})),configuration={...optionsSchema.parse({}),delimiter:parsed.delimiter,columns:inferColumns(parsed,optionsSchema.parse({}))}
    const checked=await validateRows(parsed,configuration);assert.equal(checked.report.valid,true)
    const first={datasetId:randomUUID(),versionId:randomUUID()},receiptId=randomUUID(),checksum=createHash('sha256').update(fixture).digest('hex')
    await db.query('INSERT INTO platform.datasets(id,owner_id,title,source,revision) VALUES($1,$2,$3,$4,2)',[first.datasetId,owner,'Analytics fixture','Synthetic exact fixture'])
    await db.query("INSERT INTO platform.import_receipts(id,owner_id,dataset_id,filename,source_sha256,byte_count,status,completed_at) VALUES($1,$2,$3,'analytics.csv',$4,$5,'imported',now())",[receiptId,owner,first.datasetId,checksum,Buffer.byteLength(fixture)])
    await db.query("INSERT INTO platform.dataset_versions(id,dataset_id,receipt_id,version_number,row_count,column_count,configuration,source_sha256,filename) VALUES($1,$2,$3,1,$4,$5,$6,$7,'analytics.csv')",[first.versionId,first.datasetId,receiptId,checked.rows.length,configuration.columns.length,configuration,checksum])
    for(const row of checked.rows)await db.query('INSERT INTO platform.dataset_rows(version_id,row_number,source_line,values,original_values) VALUES($1,$2,$3,$4,$5)',[first.versionId,row.rowNumber,row.sourceLine,row.values,row.original])
    for(const [ordinal,column] of configuration.columns.entries()){
      const value=expression(column,'$2'),numeric=['integer','decimal'].includes(column.type),comparable=column.type==='boolean'?`(${value})::text`:value
      const stats=(await db.query(`SELECT count(*)::int total,count(${value})::int present,count(DISTINCT ${value})::int distinct,min(${comparable})::text minimum,max(${comparable})::text maximum ${numeric?`,avg(${value})::text mean`:''} FROM platform.dataset_rows r WHERE r.version_id=$1`,[first.versionId,column.id])).rows[0]
      await db.query('INSERT INTO platform.dataset_columns(version_id,id,ordinal,original_name,display_name,data_type,interpretation,profile) VALUES($1,$2,$3,$4,$5,$6,$7,$8)',[first.versionId,column.id,ordinal,column.originalName,column.name,column.type,column,{...stats,missing:stats.total-stats.present}])
    }
    const source=sourceSchema.parse(first),preserved=new Map<string,unknown>()
    for(const table of ['dataset_versions','dataset_columns','dataset_rows'])preserved.set(table,(await db.query(`SELECT row_to_json(t)::text data FROM platform.${table} t ORDER BY row_to_json(t)::text`)).rows)
    await t.test('populated dataset upgrade preserves versions/prices and restricted grants',async()=>{
      await assert.rejects(analytics.ready())
      await migrate(db!);await migrate(db!);await grantRuntime(db!,'platform-test-runtime-password-at-least-32-characters')
      assert.equal((await db!.query('SELECT count(*)::int n FROM platform.schema_migrations')).rows[0].n,5)
      for(const [table,before] of preserved)assert.deepEqual((await db!.query(`SELECT row_to_json(t)::text data FROM platform.${table} t ORDER BY row_to_json(t)::text`)).rows,before)
      assert.equal((await datasets.rows(owner,first.datasetId,first.versionId,{page:1,pageSize:25,search:'',filters:[],sort:null})).total,12)
      for(const sql of ['UPDATE platform.dataset_rows SET source_line=source_line','DELETE FROM platform.dataset_versions','DELETE FROM platform.activity','UPDATE platform.schema_migrations SET checksum=checksum'])await assert.rejects(runtime!.query(sql),{code:'42501'})
    })
    const run=(definition:Record<string,unknown>,page=1,pageSize=25)=>analytics.execute(owner,definitionSchema.parse({source,...definition}),page,pageSize) as Promise<any>
    await t.test('hand-calculable aggregates, missing denominators, rankings, date buckets and empty selections',async()=>{
      const filtered={...source,filters:[{column:id('group'),op:'equals',values:['A']}]}
      const result=await run({kind:'aggregate',source:filtered,measures:['sum','mean','median','min','max','q1','q3','stddev_sample'].map(operation=>({operation,column:id('amount')})),chart:'kpi'})
      assert.equal(result.filteredRows,6)
      assert.deepEqual(result.rows[0].metrics.slice(0,7).map((m:any)=>Number(m.value)),[106,21.2,2,0,100,1,3])
      assert.equal(result.rows[0].metrics[1].present,5);assert.equal(result.rows[0].metrics[1].missing,1)
      assert.ok(Math.abs(Number(result.rows[0].metrics[7].value)-Math.sqrt(1941.7))<1e-10)
      const ranking=await run({kind:'aggregate',measures:[{operation:'rows'}],groupBy:[{column:id('group')}],limit:1,chart:'bar'})
      assert.equal(ranking.groupsTotal,3);assert.equal(ranking.omittedGroups,2);assert.equal(Number(ranking.rows[0].share),50)
      const monthly=await run({kind:'aggregate',measures:[{operation:'rows'}],groupBy:[{column:id('day'),interval:'month'}],chart:'line',order:{by:'group',index:0,direction:'asc'}})
      assert.deepEqual(monthly.rows.map((r:any)=>r.groups[0]),['2026-01','2026-02','2026-03'])
      const empty=await run({kind:'aggregate',source:{...source,search:'absent-fixture-value'},measures:[{operation:'mean',column:id('amount')}]})
      assert.equal(empty.filteredRows,0);assert.equal(empty.rows[0].metrics[0].value,null)
      await assert.rejects(run({kind:'aggregate',measures:[{operation:'mean',column:id('form')}]}),{code:'invalid_analysis'})
      await assert.rejects(run({kind:'aggregate',measures:[{operation:'rows'}],groupBy:[{column:id('form')}],chart:'line'}),{code:'invalid_analysis'})
      await assert.rejects(run({kind:'aggregate',measures:[{operation:'rows'}],groupBy:[{column:id('form')}],chart:'pie',limit:1}),{code:'invalid_analysis'})
      const numericGroups=sourceSchema.parse(await imported('key,group\n001,10\n002,2\n'))
      const ordered=await run({kind:'aggregate',source:numericGroups,measures:[{operation:'rows'}],groupBy:[{column:id('group')}],order:{by:'group',index:0,direction:'asc'}})
      assert.deepEqual(ordered.rows.map((row:any)=>row.groups[0]),['2','10'])
    })
    await t.test('exact large decimals, type-7 quartiles, histogram edges and scatter coordinates',async()=>{
      const exact=sourceSchema.parse(await imported('id,x,y\n001,90071992547409931234567890.01,0\n002,90071992547409931234567890.03,2\n'))
      const result=await run({kind:'aggregate',source:exact,measures:['mean','q1','median','q3'].map(operation=>({operation,column:id('x')}))})
      assert.match(result.rows[0].metrics[0].value,/^90071992547409931234567890\.020*$/)
      assert.match(result.rows[0].metrics[1].value,/^90071992547409931234567890\.0150*$/)
      assert.match(result.rows[0].metrics[3].value,/^90071992547409931234567890\.0250*$/)
      const close=sourceSchema.parse(await imported('id,x\n001,90071992547409931234567890.01\n002,90071992547409931234567890.02\n'))
      const closeMean=await run({kind:'aggregate',source:close,measures:[{operation:'mean',column:id('x')}]})
      assert.match(closeMean.rows[0].metrics[0].value,/^90071992547409931234567890\.0150*$/)
      const hist=await run({kind:'histogram',source:exact,column:id('x'),bins:2})
      assert.deepEqual(hist.bins.map((bin:any)=>bin.count),[1,1]);assert.equal(hist.maximum,'90071992547409931234567890.03')
      const points=await run({kind:'scatter',source:exact,x:id('x'),y:id('y'),pointLimit:1})
      assert.equal(points.pairedRows,2);assert.equal(points.omittedPoints,1);assert.equal(Number(points.points[0].px),0)
      const singleton=await run({kind:'aggregate',source:{...exact,filters:[{column:id('id'),op:'equals',values:['001']}]},measures:[{operation:'stddev_sample',column:id('x')},{operation:'stddev_population',column:id('x')},{operation:'q1',column:id('x')}]})
      assert.equal(singleton.rows[0].metrics[0].value,null);assert.equal(Number(singleton.rows[0].metrics[1].value),0)
    })
    await t.test('advanced missingness groups and affected rows; IQR flags, zero IQR and small groups',async()=>{
      const missing=await run({kind:'missing',columns:[id('amount')],groupBy:{column:id('group')}},1,1)
      assert.equal(missing.filteredRows,12);assert.equal(missing.affectedRows,2);assert.equal(missing.rows.length,1)
      assert.equal(missing.groups.find((g:any)=>g.key==='A').cells[0].missing,1)
      const all=await run({kind:'missing',columns:[id('empty')]})
      assert.equal(all.affectedRows,12);assert.equal(Number(all.columns[0].missingRate),100)
      const flagged=await run({kind:'outliers',column:id('amount'),groupBy:{column:id('group')}})
      assert.equal(flagged.flaggedRows,1);assert.equal(flagged.rows[0].values[id('id')],'005')
      assert.equal(flagged.groups.find((g:any)=>g.key==='B').status,'zero_iqr')
      assert.equal(flagged.groups.find((g:any)=>g.key==='C').status,'insufficient')
      assert.equal(flagged.insufficientRows,1)
      assert.equal(Number(flagged.groups.find((g:any)=>g.key==='A').upper),6)
    })
    await t.test('empty/all-missing/constant inputs, strict fences, zero-IQR tails and null group identity',async()=>{
      const none=sourceSchema.parse(await imported('key,amount\n001,\n002,\n',undefined,{amount:'decimal'}))
      const allNull=await run({kind:'outliers',source:none,column:id('amount')})
      assert.equal(allNull.present,0);assert.equal(allNull.missing,2);assert.equal(allNull.flaggedRows,0)
      const noRows=await run({kind:'missing',source:{...none,search:'no-row-can-match'},columns:[id('amount')]})
      assert.equal(noRows.filteredRows,0);assert.equal(noRows.columns[0].missingRate,null);assert.equal(noRows.groups.length,0)
      const strict=sourceSchema.parse(await imported('key,group,amount\n001,,0\n002,,1\n003,,2\n004,,3\n005,,6\n006,null,1\n007,null,1\n008,null,1\n009,null,1\n010,null,3\n'))
      const edge=await run({kind:'outliers',source:strict,column:id('amount'),groupBy:{column:id('group')}})
      assert.equal(edge.groupsTotal,2);assert.equal(edge.flaggedRows,1)
      assert.equal(edge.groups.find((g:any)=>g.key===null).flagged,0)
      assert.equal(edge.groups.find((g:any)=>g.key==='null').status,'zero_iqr')
      const constant=await run({kind:'histogram',source:{...strict,filters:[{column:id('amount'),op:'equals',values:['1']}]},column:id('amount'),bins:10})
      assert.equal(constant.constant,true);assert.equal(constant.bins.length,1);assert.equal(constant.bins[0].count,5)
      const emptyHistogram=await run({kind:'histogram',source:none,column:id('amount'),bins:10});assert.equal(emptyHistogram.bins.length,0)
      const noTime=sourceSchema.parse(await imported('key,day\n001,2026-01-01\n002,2026-01-02\n'))
      const recommendation=await run({kind:'recommend',source:noTime,columns:[id('day')]})
      assert.equal(recommendation.options.length,0);assert.ok(recommendation.notes.some((note:string)=>note.includes('moins de deux mois')))
    })
    let compareDefinition:ReturnType<typeof definitionSchema.parse>
    await t.test('explicit schema/statistic comparison, exact unique keys, added/removed/changed rows and duplicate refusal',async()=>{
      const l=sourceSchema.parse(await imported('key,price\n001,1\n002,2\n003,\n'))
      const r=sourceSchema.parse(await imported('key,price,extra\n001,10,new\n003,,new\n004,4,new\n',l.datasetId))
      compareDefinition=definitionSchema.parse({kind:'compare',source:l,right:r,mappings:[{left:id('price'),right:id('price')}],keys:[{left:id('key'),right:id('key')}]})
      const result:any=await analytics.execute(owner,compareDefinition)
      assert.deepEqual([result.rowComparison.added,result.rowComparison.removed,result.rowComparison.changed,result.rowComparison.unchanged],[1,1,1,1])
      assert.equal(result.statistics[0].left.missing,1);assert.equal(result.statistics[0].right.missing,1)
      assert.equal(result.schema.right.length,3)
      const keyOnly=await run({...compareDefinition,mappings:[]})
      assert.deepEqual([keyOnly.rowComparison.added,keyOnly.rowComparison.removed,keyOnly.rowComparison.changed,keyOnly.rowComparison.unchanged],[1,1,0,2])
      const duplicates=sourceSchema.parse(await imported('key,price\n001,1\n001,2\n'))
      await assert.rejects(run({...compareDefinition,right:duplicates}),{code:'invalid_analysis'})
      const missingKeys=sourceSchema.parse(await imported('key,price\n,1\n001,2\n'))
      await assert.rejects(run({...compareDefinition,right:missingKeys}),{code:'invalid_analysis'})
      const foreign=sourceSchema.parse(await imported('key,price\n001,1\n',undefined,{},other))
      await assert.rejects(run({...compareDefinition,right:foreign}),{code:'analysis_source_unavailable'})
    })
    await t.test('recommendations create executable editable configs; pharmaceutical templates share the engine',async()=>{
      for(const selected of [['form'],['amount'],['amount','second'],['day','amount']]){
        const recommendations=await run({kind:'recommend',columns:selected.map(id)})
        assert.ok(recommendations.options.length)
        for(const option of recommendations.options)await analytics.execute(owner,definitionSchema.parse(option.definition))
      }
      const configured=await analytics.templates(owner,source)
      for(const template of configured.templates){assert.ok(template.definition);await analytics.execute(owner,template.definition!)}
      const disagree:any=await analytics.execute(owner,configured.templates.find(t=>t.id==='disagreements')!.definition!)
      assert.equal(disagree.filteredRows,2)
    })
    let savedId:string
    await t.test('private saved analyses pin sources/settings; dependencies, optimistic revisions and disabled accounts',async()=>{
      const saved=await analytics.save(owner,{title:'Pinned comparison',description:'Exact keys',definition:compareDefinition!});savedId=saved.analysis.id
      assert.equal((await db!.query('SELECT count(*)::int n FROM platform.analysis_sources WHERE analysis_id=$1',[savedId])).rows[0].n,2)
      const ownDataset=compareDefinition!.source.datasetId
      const dependencies=await datasets.dependencies(owner,ownDataset);assert.equal(dependencies.canDelete,false)
      await assert.rejects(datasets.remove(owner,ownDataset,dependencies.revision,dependencies.title),{code:'dataset_dependencies'})
      await assert.rejects(analytics.get(other,savedId),{code:'analysis_not_found'});await assert.rejects(analytics.get(administrator,savedId),{code:'analysis_not_found'})
      await assert.rejects(analytics.execute(other,compareDefinition!),{code:'analysis_source_unavailable'})
      const updated=await analytics.save(owner,{title:'Renamed comparison',description:'',definition:compareDefinition!},savedId,1)
      assert.equal(updated.analysis.revision,2)
      await assert.rejects(analytics.save(owner,{title:'Stale',description:'',definition:compareDefinition!},savedId,1),{code:'analysis_changed'})
      const invalidDefinition=definitionSchema.parse({kind:'aggregate',source:compareDefinition!.source,measures:[{operation:'mean',column:'absent-column'}]})
      await assert.rejects(analytics.save(owner,{title:'Invalid migration',description:'',definition:invalidDefinition},savedId,2),{code:'invalid_analysis'})
      assert.equal((await analytics.get(owner,savedId)).analysis.revision,2)
      const oneSource=definitionSchema.parse({kind:'aggregate',source:compareDefinition!.source,measures:[{operation:'mean',column:id('price')}]})
      await analytics.save(owner,{title:'Single source',description:'',definition:oneSource},savedId,2)
      assert.equal((await db!.query('SELECT count(*)::int n FROM platform.analysis_sources WHERE analysis_id=$1',[savedId])).rows[0].n,1)
      assert.equal((await db!.query("SELECT count(*)::int n FROM platform.dataset_dependencies WHERE resource_id=$1 AND version_id=$2",[savedId,(compareDefinition! as Extract<typeof compareDefinition,{kind:'compare'}>).right.versionId])).rows[0].n,0)
      await analytics.save(owner,{title:'Restored explicit comparison',description:'',definition:compareDefinition!},savedId,3)
      await db!.query('UPDATE platform.users SET active=false WHERE id=$1',[owner])
      await assert.rejects(analytics.save(owner,{title:'Disabled',description:'',definition:compareDefinition!}),{code:'authentication_required'})
      await db!.query('UPDATE platform.users SET active=true WHERE id=$1',[owner])
      const old=await analytics.get(owner,savedId);assert.deepEqual(old.analysis.definition,compareDefinition!)
    })
    await t.test('HTTP roles, ownership, CSRF and source tampering are enforced by Express',async()=>{
      const accounts=new PostgresStore(runtime!),app=createApp(accounts,{origin:'http://127.0.0.1:5177',secureCookie:false,trustProxy:false},datasets)
      const token=newToken();await accounts.issue(token,owner);const csrf=csrfFor(token),cookie='platform_session='+token
      await request(app).get('/analyses').expect(401)
      await request(app).post('/analytics/execute').set('Origin','http://127.0.0.1:5177').set('Cookie',cookie).send({definition:compareDefinition!}).expect(403)
      await request(app).post('/analytics/execute').set('Origin','http://127.0.0.1:5177').set('Cookie',cookie).set('X-CSRF-Token',csrf).send({definition:compareDefinition!}).expect(200)
      const foreignToken=newToken();await accounts.issue(foreignToken,other)
      await request(app).get('/analyses/'+savedId!).set('Cookie','platform_session='+foreignToken).expect(404)
      await request(app).post('/analytics/execute').set('Origin','http://127.0.0.1:5177').set('Cookie','platform_session='+foreignToken).set('X-CSRF-Token',csrfFor(foreignToken)).send({definition:compareDefinition!}).expect(404)
    })
    await t.test('catalogue and larger fixture measured analysis bounds and exact missing-price counts',async()=>{
      const records=(await readFile(join(root,'data/imports/ammps_medications_enriched.jsonl'),'utf8')).trim().split('\n').map(line=>JSON.parse(line))
      const quote=(value:unknown)=>'"'+String(value??'').replaceAll('"','""')+'"'
      const catalogue='source_record_id,form,ppv_price_mad,recorded_conflicts\n'+records.map(record=>[record.source_record_id,record.form,record.ppv_price_mad,record.data_conflicts.length].map(quote).join(',')).join('\n')+'\n'
      const large='key,group,amount,second\n'+Array.from({length:25000},(_,i)=>`${i},G${i%20},${i%1000},${i%17}`).join('\n')+'\n'
      const measurements=[]
      for(const [title,csv,rows,priceColumn] of [['Catalogue 9936',catalogue,9936,'ppv_price_mad'],['Larger 25000',large,25000,'amount']] as const){
        const importedSource=sourceSchema.parse(await imported(csv)),start=performance.now()
        const result=await run({kind:'aggregate',source:importedSource,measures:['mean','median','q1','q3','stddev_sample'].map(operation=>({operation,column:id(priceColumn)}))})
        assert.equal(result.filteredRows,rows)
        const statsMs=Math.round(performance.now()-start),advancedStart=performance.now()
        const outlier=await run({kind:'outliers',source:importedSource,column:id(priceColumn)})
        assert.equal(outlier.filteredRows,rows)
        const missing=await run({kind:'missing',source:importedSource,columns:[id(priceColumn)]})
        if(rows===9936)assert.equal(missing.affectedRows,1126)
        const advancedMs=Math.round(performance.now()-advancedStart)
        let highCardinalityMs:number|undefined
        if(rows===25000){
          const highStart=performance.now()
          const many=await run({kind:'outliers',source:importedSource,column:id(priceColumn),groupBy:{column:id('key')}})
          assert.equal(many.groupsTotal,25000);assert.equal(many.flaggedRows,0);assert.equal(many.insufficientRows,25000)
          const ranked=await run({kind:'aggregate',source:importedSource,measures:[{operation:'rows'}],groupBy:[{column:id('key')}],limit:200})
          assert.equal(ranked.groupsTotal,25000);assert.equal(ranked.omittedGroups,24800)
          highCardinalityMs=Math.round(performance.now()-highStart)
        }
        measurements.push({title,rows,statsMs,advancedMs,...(highCardinalityMs===undefined?{}:{highCardinalityMs})})
      }
      await mkdir(join(root,'artifacts/platform-cp3'),{recursive:true});await writeFile(join(root,'artifacts/platform-cp3/analytics-benchmarks.json'),JSON.stringify({measuredAt:new Date().toISOString(),measurements},null,2))
    })
    await t.test('maintained backup retains saved algorithms and real dependency relationships without sessions',async()=>{
      const directory=await mkdtemp(join(tmpdir(),'platform-cp3-backup-')),restoreName='platform_cp3_'+randomUUID().replaceAll('-','')
      let restored:ReturnType<typeof createPool>|undefined,restoreCreated=false
      try{
        const dump=join(directory,'analyses.dump'),python=join(root,process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python')
        await promisify(execFile)(python,['-c','import os,sys; from pharmacy_ops.backup import backup; backup({"MIGRATION_DATABASE_URL":os.environ["CP3_BACKUP_DATABASE_URL"]},sys.argv[1])',dump],{cwd:root,env:{...process.env,CP3_BACKUP_DATABASE_URL:adminUrl.href.replace('postgresql:','postgresql+psycopg:')},timeout:30000})
        await cluster.query(`CREATE DATABASE "${restoreName}"`);restoreCreated=true
        const tool=process.platform==='win32'?join(process.env.ProgramFiles??'C:/Program Files','PostgreSQL/17/bin/pg_restore.exe'):'pg_restore'
        await promisify(execFile)(tool,['--host','127.0.0.1','--port','55433','--username','platform_test_admin','--dbname',restoreName,'--exit-on-error','--no-owner','--no-privileges',dump],{env:{...process.env,PGPASSWORD:clusterUrl.password},timeout:30000})
        const restoredUrl=new URL(clusterUrl);restoredUrl.pathname='/'+restoreName;restored=createPool(restoredUrl.href)
        for(const table of ['analyses','analysis_sources','dataset_dependencies','dataset_rows']){
          const sql=`SELECT row_to_json(t)::text data FROM platform.${table} t ORDER BY row_to_json(t)::text`
          assert.deepEqual((await db!.query(sql)).rows,(await restored.query(sql)).rows)
        }
        assert.equal((await restored.query('SELECT count(*)::int n FROM platform.sessions')).rows[0].n,0)
        const reopened=await new AnalyticsService(restored).get(owner,savedId!)
        assert.deepEqual(reopened.analysis.definition,compareDefinition!)
      }finally{await restored?.end();if(restoreCreated)await cluster.query(`DROP DATABASE "${restoreName}" WITH (FORCE)`);if(dirname(resolve(directory))!==resolve(tmpdir())||!basename(directory).startsWith('platform-cp3-backup-'))throw new Error('Refusing unexpected temporary cleanup path');await rm(directory,{recursive:true,force:true})}
      const saved=await analytics.get(owner,savedId!);await analytics.remove(owner,savedId!,saved.analysis.revision)
      assert.equal((await db!.query("SELECT count(*)::int n FROM platform.dataset_dependencies WHERE kind='analysis' AND resource_id=$1",[savedId!])).rows[0].n,0)
    })
  }finally{await runtime?.end();await db?.end();if(created)await cluster.query(`DROP DATABASE "${database}" WITH (FORCE)`);await cluster.end()}
})
