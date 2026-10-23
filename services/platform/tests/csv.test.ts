import assert from 'node:assert/strict'
import test from 'node:test'
import { optionsSchema, querySchema } from '../src/datasets/contracts.js'
import { convert, inferColumns, parseCsv, reportCsv, validateRows } from '../src/datasets/csv.js'
import { buildQuery } from '../src/datasets/query.js'

test('strict CSV structure: BOM, quoted delimiters/newlines, duplicates, widths and malformed quotes',async()=>{
  const options=optionsSchema.parse({})
  const good=await parseCsv(Buffer.from('\uFEFFid;name;price\r\n001;"a; b\nsecond line";0\r\n002;NA;\r\n'),options)
  assert.equal(good.issueCount,0);assert.equal(good.delimiter,';');assert.equal(good.rows[0]?.cells[1],'a; b\nsecond line')
  const columns=inferColumns(good,options)
  assert.equal(columns[0]?.type,'text');assert.equal(columns[2]?.type,'integer')
  const checked=await validateRows(good,{...options,columns})
  assert.equal(checked.rows[1]?.values[columns[1]!.id],'NA')
  assert.equal(checked.rows[0]?.values[columns[2]!.id],'0');assert.equal(checked.rows[1]?.values[columns[2]!.id],null)
  for(const csv of ['a,A\n1,2\n',',b\n1,2\n','a,b\n1\n','a,b\n"bad,2\n','a,b\n'])assert.ok((await parseCsv(Buffer.from(csv),options)).issueCount>0,csv)
  const text='𐍈'.repeat(16000)
  const unicode=await parseCsv(Buffer.from('value\n'+text+'\n'),options)
  assert.equal(unicode.rows[0]?.cells[0],text)
})
test('explicit types/conventions preserve exact decimals, raw text, missingness and reject invalid cells',async()=>{
  const options=optionsSchema.parse({delimiter:';',decimalSeparator:',',missingMarkers:['','NULL']})
  const parsed=await parseCsv(Buffer.from('ident;prix;jour;actif;instant\n001;12,50;01/02/2026;false;2026-10-23T10:30:00+01:00\n002;0;03/04/2026;true;2026-10-23T11:30:00Z\n003;NULL;31/02/2026;wrong;2026-10-23T10:30:00\n'),options)
  const columns=inferColumns(parsed,options)
  columns[1]!.type='decimal';columns[2]!.type='date';columns[2]!.dateFormat='dmy';columns[3]!.type='boolean';columns[4]!.type='datetime'
  const result=await validateRows(parsed,{...options,columns})
  assert.equal(result.report.valid,false);assert.equal(result.report.issueCount,3)
  assert.equal(result.rows[0]!.values[columns[1]!.id],'12.5');assert.equal(result.rows[0]!.original[columns[1]!.id],'12,50')
  assert.equal(result.rows[0]!.values[columns[2]!.id],'2026-02-01');assert.equal(result.rows[0]!.values[columns[3]!.id],false)
  assert.equal(result.rows[0]!.values[columns[4]!.id],'2026-10-23T09:30:00.000000Z')
  assert.equal(convert('2026-10-18T16:17:23.815325+00:00',columns[4]!,options),'2026-10-18T16:17:23.815325Z')
  assert.equal(result.rows[2]!.values[columns[1]!.id],null)
  assert.equal(convert('',{...columns[0]!,type:'text'},optionsSchema.parse({missingMarkers:[]})),'')
  assert.equal(convert('9007199254740993',{...columns[0]!,type:'integer'},options),'9007199254740993')
  for(const invalid of ['NaN','Infinity','1e4','1 200','12 MAD','1.1234567890123'])assert.throws(()=>convert(invalid,{...columns[1]!,type:'decimal'},options))
})
test('full-file validation catches late failures, limits reports, and query values cannot become SQL',async()=>{
  const options=optionsSchema.parse({})
  const parsed=await parseCsv(Buffer.from('amount\n'+Array.from({length:1300},(_,index)=>index<201?'12':'bad').join('\n')+'\n'),options)
  const columns=inferColumns(parsed,options),config={...options,columns}
  assert.equal(columns[0]!.type,'integer')
  const result=await validateRows(parsed,config)
  assert.equal(result.report.issueCount,1099);assert.equal(result.report.issues.length,1000);assert.equal(result.report.truncated,true)
  const query=querySchema.parse({filters:[{column:columns[0]!.id,op:'equals',values:["1'; DROP TABLE users;--"]}]})
  assert.throws(()=>buildQuery('version',columns,query),{code:'invalid_filter'})
  assert.throws(()=>buildQuery('version',columns,querySchema.parse({filters:[{column:'unknown',op:'missing'}]})),{code:'unknown_column'})
  const report=reportCsv({...result.report,issues:[{row:2,line:3,column:'=HYPERLINK("bad")',code:'invalid',message:'Reason'}]})
  assert.match(report,/"'=HYPERLINK/)
})
