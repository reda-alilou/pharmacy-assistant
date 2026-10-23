import type pg from 'pg'
import type { Definition } from './contracts.js'
import { Query, column, compatible, invalid, numericType, quantile, unique, type Loaded } from './sql.js'

async function summary(db:pg.PoolClient,loaded:Loaded,id:string) {
  const q=new Query(loaded),selected=column(loaded,id),value=q.value(id)
  const numeric=numericType(selected)
  const result=await db.query(`WITH observations AS (SELECT ${value} v FROM platform.dataset_rows r WHERE ${q.where}),
    stats AS (SELECT count(*)::int total,count(v)::int present,count(DISTINCT v)::int distinct_count,
      ${numeric?'min(v)::text minimum,max(v)::text maximum,sum(v)::text sum,avg(v::numeric(80,24))::text mean,stddev_samp(v::numeric(80,24))::text stddev_sample,array_agg(v ORDER BY v) FILTER(WHERE v IS NOT NULL) nums':'NULL::text minimum,NULL::text maximum,NULL::text sum,NULL::text mean,NULL::text stddev_sample,NULL::numeric[] nums'} FROM observations)
    SELECT total,present,(total-present)::int missing,distinct_count AS "distinct",(100.0*(total-present)/nullif(total,0))::text missing_rate,
      minimum,maximum,sum,mean,stddev_sample,${quantile('nums','0.25')}::text q1,${quantile('nums','0.5')}::text median,${quantile('nums','0.75')}::text q3 FROM stats`,q.parameters)
  return result.rows[0]
}

export async function comparison(db:pg.PoolClient,left:Loaded,right:Loaded,definition:Extract<Definition,{kind:'compare'}>,page:number,pageSize:number) {
  unique(definition.mappings.map(pair=>pair.left));unique(definition.mappings.map(pair=>pair.right))
  unique(definition.keys.map(pair=>pair.left));unique(definition.keys.map(pair=>pair.right))
  const mapped=definition.mappings.map(pair=>({left:column(left,pair.left),right:column(right,pair.right)}))
  for(const pair of definition.keys)if(!compatible(column(left,pair.left),column(right,pair.right)))throw invalid('Les colonnes de clé doivent avoir des types compatibles, sans conversion implicite texte/nombre.')
  if(definition.keys.length&&mapped.some(pair=>!compatible(pair.left,pair.right)))throw invalid('La comparaison de lignes exige des correspondances de colonnes de types compatibles.')
  const count=async(source:Loaded)=>{const q=new Query(source);return (await db.query(`SELECT count(*)::int n FROM platform.dataset_rows r WHERE ${q.where}`,q.parameters)).rows[0].n as number}
  const counts={left:await count(left),right:await count(right)}
  const statistics=[]
  for(const pair of definition.mappings)statistics.push({leftColumn:pair.left,rightColumn:pair.right,typeChanged:column(left,pair.left).type!==column(right,pair.right).type,left:await summary(db,left,pair.left),right:await summary(db,right,pair.right)})
  let rowComparison:null|{added:number;removed:number;changed:number;unchanged:number;page:number;pageSize:number;rows:pg.QueryResultRow[]}=null
  if(definition.keys.length) {
    const make=(loaded:Loaded,side:'left'|'right')=>{
      const q=new Query(loaded)
      const keys=definition.keys.map(pair=>q.text(pair[side])),values=definition.mappings.map(pair=>q.text(pair[side]))
      const sql=`SELECT row_number,source_line,jsonb_build_array(${keys.join(',')}) key,jsonb_build_array(${values.join(',')}) payload,
        jsonb_build_array(${definition.mappings.map(pair=>`r.original_values->>${q.parameter(pair[side])}`).join(',')}) original,
        (${keys.map(key=>`${key} IS NULL`).join(' OR ')}) missing_key FROM platform.dataset_rows r WHERE ${q.where}`
      return {q,sql}
    }
    const a=make(left,'left'),b=make(right,'right')
    for(const item of [a,b]) {
      const validation=(await db.query(`WITH rows AS (${item.sql}) SELECT (SELECT count(*)::int FROM rows WHERE missing_key) missing,
        (SELECT count(*)::int FROM (SELECT key FROM rows GROUP BY key HAVING count(*)>1) duplicate_keys) duplicates`,item.q.parameters)).rows[0]
      if(validation.missing||validation.duplicates)throw invalid('Clé de comparaison invalide : les clés doivent être complètes et uniques dans chaque sélection filtrée. Aucune correspondance approximative n’est utilisée.')
    }
    const shifted=b.sql.replace(/\$(\d+)/g,(_,n)=>'$'+(Number(n)+a.q.parameters.length))
    const cte=`WITH l AS (${a.sql}),r AS (${shifted}),paired AS (SELECT coalesce(l.key,r.key) key,
      CASE WHEN l.row_number IS NULL THEN 'added' WHEN r.row_number IS NULL THEN 'removed' WHEN l.payload IS DISTINCT FROM r.payload THEN 'changed' ELSE 'unchanged' END status,
      l.row_number left_row,r.row_number right_row,l.source_line left_line,r.source_line right_line,l.payload left_values,r.payload right_values,l.original left_original,r.original right_original
      FROM l FULL JOIN r ON l.key=r.key)`
    const parameters=[...a.q.parameters,...b.q.parameters]
    const totals=(await db.query(`${cte} SELECT count(*) FILTER(WHERE status='added')::int added,count(*) FILTER(WHERE status='removed')::int removed,
      count(*) FILTER(WHERE status='changed')::int changed,count(*) FILTER(WHERE status='unchanged')::int unchanged FROM paired`,parameters)).rows[0]
    const rows=await db.query(`${cte} SELECT * FROM paired WHERE status<>'unchanged' ORDER BY key LIMIT ${pageSize} OFFSET ${(page-1)*pageSize}`,parameters)
    rowComparison={added:totals.added,removed:totals.removed,changed:totals.changed,unchanged:totals.unchanged,page,pageSize,rows:rows.rows}
  }
  return {kind:'compare' as const,rowCounts:counts,schema:{left:left.columns,right:right.columns,mappings:definition.mappings,
    unmappedLeft:left.columns.filter(c=>!definition.mappings.some(pair=>pair.left===c.id)).map(c=>c.id),unmappedRight:right.columns.filter(c=>!definition.mappings.some(pair=>pair.right===c.id)).map(c=>c.id)},statistics,rowComparison}
}
