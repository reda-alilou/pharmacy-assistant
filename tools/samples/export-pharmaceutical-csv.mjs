// Explicit, offline export from the preserved import input. No database access.
import { readFile,writeFile,mkdir } from 'node:fs/promises'
import { dirname,resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { parseArgs } from 'node:util'

const {values}=parseArgs({options:{output:{type:'string'},sample:{type:'boolean'},help:{type:'boolean'}}})
if(values.help||!values.output){console.log('Usage: node tools/samples/export-pharmaceutical-csv.mjs --output <new.csv> [--sample]. Reads the preserved AMMPS JSONL input; never overwrites an existing output.');process.exit(values.help?0:1)}
try{
  const root=fileURLToPath(new URL('../../',import.meta.url))
  const all=(await readFile(resolve(root,'data/imports/ammps_medications_enriched.jsonl'),'utf8')).trim().split('\n').map(line=>JSON.parse(line))
  const selected=values.sample?[...new Map([...all.slice(0,24),...all.filter(record=>record.ppv_price_mad===null).slice(0,8),...all.filter(record=>record.source_observations.length>0).slice(0,8)].map(record=>[record.source_record_id,record])).values()]:all
  const fields=['source_record_id','brand_name','active_substance','dosage','form','presentation','ppv_price_mad','hospital_price_mad','pfht_price_mad','commercialization_status','source','source_url','source_fetched_at_utc','linked_observations','recorded_conflicts','source_observations_json','data_conflicts_json']
  const quote=value=>'"'+String(value??'').replaceAll('"','""')+'"'
  const lines=selected.map(record=>{
    const extra={linked_observations:record.source_observations.length,recorded_conflicts:record.data_conflicts.length,source_observations_json:JSON.stringify(record.source_observations),data_conflicts_json:JSON.stringify(record.data_conflicts)}
    return fields.map(field=>quote(field in extra?extra[field]:record[field])).join(',')
  })
  const output=resolve(values.output);await mkdir(dirname(output),{recursive:true})
  await writeFile(output,fields.join(',')+'\n'+lines.join('\n')+'\n',{flag:'wx'})
  console.log(JSON.stringify({output,rows:selected.length,source:'Preserved AMMPS snapshot 2026-10-18; linked secondary observations retained',networkUsed:false,existingInputsChanged:false}))
}catch{console.error('Export failed. Check the input and use a new output path. Existing files were not overwritten.');process.exitCode=1}
