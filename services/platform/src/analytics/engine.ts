import type pg from 'pg'
import type { Aggregate, Definition } from './contracts.js'
import { Query, column, invalid, numericType, quantile, rowsShape, unique, type Loaded } from './sql.js'

export async function aggregate(db:pg.PoolClient,loaded:Loaded,definition:Aggregate) {
  unique(definition.groupBy.map(item=>item.column))
  const q=new Query(loaded)
  const groups=definition.groupBy.map(group=>q.group(group))
  const groupNames=groups.map((_,i)=>`g${i}`)
  const groupOrder=(i:number)=>numericType(column(loaded,definition.groupBy[i]!.column))?`g${i}::numeric`:`g${i}`
  const groupSql=groupNames.length?' GROUP BY '+groupNames.join(','):''
  const groupSelect=groupNames.length?groupNames.join(',')+',':''
  const raw:string[]=[],values:string[]=[],select:string[]=[]
  definition.measures.forEach((measure,i)=>{
    const countOperation=['rows','present','missing','distinct'].includes(measure.operation)
    if(measure.operation==='rows'&&measure.column!==null)throw invalid('Le compte des lignes ne prend pas de colonne.')
    if(measure.operation!=='rows'&&!measure.column)throw invalid('Choisissez une colonne pour chaque mesure.')
    const value=measure.column?q.value(measure.column,!countOperation):'1'
    select.push(`${value} AS x${i}`)
    raw.push(`count(x${i})::int AS p${i}`)
    const op=measure.operation
    if(['q1','median','q3'].includes(op)) {
      raw.push(`array_agg(x${i} ORDER BY x${i}) FILTER(WHERE x${i} IS NOT NULL) AS a${i}`)
      values.push(`${quantile('a'+i,op==='q1'?'0.25':op==='q3'?'0.75':'0.5')}::text AS v${i}`)
    }else{
      const expression=op==='rows'?'count(*)':op==='present'?`count(x${i})`:op==='missing'?`count(*)-count(x${i})`:op==='distinct'?`count(DISTINCT x${i})`:
        `${{sum:'sum',mean:'avg',min:'min',max:'max',stddev_sample:'stddev_samp',stddev_population:'stddev_pop'}[op as 'sum']} (${['mean','stddev_sample','stddev_population'].includes(op)?`x${i}::numeric(80,24)`:`x${i}`})`
      raw.push(`${expression} AS a${i}`);values.push(`a${i}::text AS v${i}`)
    }
  })
  if(definition.order.by==='group'&&definition.order.index>=groups.length||definition.order.by==='measure'&&definition.order.index>=definition.measures.length)
    throw invalid('Critère de classement absent de cette analyse.')
  if(definition.chart==='kpi'&&groups.length)throw invalid('Une carte KPI exige un résultat sans regroupement.')
  if(['bar','pie','line'].includes(definition.chart)&&!groups.length)throw invalid('Ce graphique exige un regroupement.')
  if(definition.chart==='line'&&(groups.length!==1||definition.groupBy[0]?.interval==='value'||!['date','datetime'].includes(column(loaded,definition.groupBy[0]!.column).type)))
    throw invalid('Une courbe exige un regroupement temporel explicite par jour, mois ou année.')
  if(definition.chart==='pie'&&(groups.length!==1||!['rows','present','missing','distinct'].includes(definition.measures[0]!.operation)))
    throw invalid('Le graphique circulaire exige un seul regroupement et une mesure de comptage.')
  // Distinct counts can overlap across categories: they are not parts of a whole.
  if(definition.chart==='pie'&&definition.measures[0]!.operation==='distinct')throw invalid('Les comptes distincts par groupe ne constituent pas une répartition additive.')
  const cte=`WITH base AS (SELECT ${[...groups.map((g,i)=>`${g} AS g${i}`),...select].join(',')} FROM platform.dataset_rows r WHERE ${q.where}),
    grouped AS (SELECT ${groupSelect}count(*)::int n,${raw.join(',')} FROM base${groupSql}),
    calculated AS (SELECT *,${values.join(',')},sum(n) OVER()::int filtered_rows,count(*) OVER()::int groups_total,
      (100.0*n/nullif(sum(n) OVER(),0))::text share FROM grouped)`
  // Numeric calculated values are text only at the transport boundary.
  const ordering=definition.order.by==='measure'?`v${definition.order.index}::numeric`:groupOrder(definition.order.index)
  const tie=groupNames.length?','+groupNames.map((_,i)=>`${groupOrder(i)} ASC NULLS LAST`).join(','):''
  const rows=await db.query(`${cte} SELECT * FROM calculated ORDER BY ${ordering} ${definition.order.direction==='asc'?'ASC':'DESC'} NULLS LAST${tie} LIMIT ${definition.limit}`,q.parameters)
  const results=rows.rows.map(row=>({groups:groupNames.map(name=>row[name] as string|null),rowCount:row.n as number,share:row.share as string|null,
    metrics:definition.measures.map((measure,i)=>({value:row['v'+i] as string|null,present:row['p'+i] as number,missing:measure.column?row.n-row['p'+i]:0}))}))
  const groupsTotal=rows.rows[0]?.groups_total??0,filteredRows=rows.rows[0]?.filtered_rows??0
  if(definition.chart==='pie'&&(groupsTotal>8||groupsTotal>definition.limit))throw invalid('Un graphique circulaire doit montrer tous les groupes (8 maximum). Choisissez des barres ou un tableau.')
  // Exact numeric coordinates avoid loss of small differences between large values.
  const plot=await db.query(`${cte}, limited AS (SELECT * FROM calculated ORDER BY ${ordering} ${definition.order.direction==='asc'?'ASC':'DESC'} NULLS LAST${tie} LIMIT ${definition.limit}),
    extent AS (SELECT least(0,min(v0::numeric)) lo,greatest(0,max(v0::numeric)) hi FROM limited)
    SELECT coalesce((0-lo)/nullif(hi-lo,0),0)::text zero,
      (SELECT coalesce(jsonb_agg(CASE WHEN v0 IS NULL THEN NULL ELSE coalesce((v0::numeric-lo)/nullif(hi-lo,0),0)::text END ORDER BY ${ordering} ${definition.order.direction==='asc'?'ASC':'DESC'} NULLS LAST${tie}),'[]'::jsonb) FROM limited) positions FROM extent`,q.parameters)
  return {kind:'aggregate' as const,filteredRows,groupsTotal,omittedGroups:Math.max(0,groupsTotal-results.length),rows:results,plot:plot.rows[0]}
}

export async function histogram(db:pg.PoolClient,loaded:Loaded,definition:Extract<Definition,{kind:'histogram'}>) {
  const q=new Query(loaded),value=q.value(definition.column,true),bins=definition.bins
  const result=await db.query(`WITH base AS (SELECT ${value} v FROM platform.dataset_rows r WHERE ${q.where}),
    extent AS (SELECT count(*)::int total,count(v)::int present,min(v) lo,max(v) hi FROM base),
    bucketed AS (SELECT CASE WHEN hi=lo THEN 1 WHEN v=hi THEN ${bins} ELSE floor((v-lo)/(hi-lo)*${bins})::int+1 END bucket FROM base CROSS JOIN extent WHERE v IS NOT NULL),
    counts AS (SELECT bucket,count(*)::int n FROM bucketed GROUP BY bucket)
    SELECT total,present,(total-present)::int missing,lo::text minimum,hi::text maximum,lo=hi constant,
      coalesce((SELECT jsonb_agg(jsonb_build_object('index',i,'lower',(lo+(hi-lo)*(i-1)/${bins})::text,
        'upper',(CASE WHEN lo=hi THEN hi ELSE lo+(hi-lo)*i/${bins} END)::text,'count',coalesce(n,0)) ORDER BY i)
        FROM generate_series(1,CASE WHEN present=0 THEN 0 WHEN lo=hi THEN 1 ELSE ${bins} END) i LEFT JOIN counts ON bucket=i),'[]'::jsonb) bins FROM extent`,q.parameters)
  return {kind:'histogram' as const,...result.rows[0]}
}

export async function scatter(db:pg.PoolClient,loaded:Loaded,definition:Extract<Definition,{kind:'scatter'}>) {
  unique([definition.x,definition.y],'Choisissez deux colonnes numériques différentes.')
  const q=new Query(loaded),x=q.value(definition.x,true),y=q.value(definition.y,true)
  const cte=`WITH base AS (SELECT row_number,source_line,${x} x,${y} y FROM platform.dataset_rows r WHERE ${q.where}),
    extent AS (SELECT count(*)::int total,count(*) FILTER(WHERE x IS NOT NULL AND y IS NOT NULL)::int paired,
      min(x) FILTER(WHERE y IS NOT NULL) xmin,max(x) FILTER(WHERE y IS NOT NULL) xmax,
      min(y) FILTER(WHERE x IS NOT NULL) ymin,max(y) FILTER(WHERE x IS NOT NULL) ymax FROM base)`
  const counts=(await db.query(`${cte} SELECT total,paired FROM extent`,q.parameters)).rows[0]!
  const points=await db.query(`${cte} SELECT row_number,source_line,x::text,y::text,
      coalesce((x-xmin)/nullif(xmax-xmin,0),0.5)::text px,coalesce((y-ymin)/nullif(ymax-ymin,0),0.5)::text py
      FROM base CROSS JOIN extent WHERE x IS NOT NULL AND y IS NOT NULL ORDER BY row_number LIMIT ${definition.pointLimit}`,q.parameters)
  return {kind:'scatter' as const,filteredRows:counts.total,pairedRows:counts.paired,missingPairs:counts.total-counts.paired,omittedPoints:Math.max(0,counts.paired-points.rowCount!),points:points.rows.map(row=>({rowNumber:row.row_number,sourceLine:row.source_line,x:row.x,y:row.y,px:row.px,py:row.py}))}
}

export async function missingness(db:pg.PoolClient,loaded:Loaded,definition:Extract<Definition,{kind:'missing'}>,page:number,pageSize:number) {
  unique(definition.columns)
  const q=new Query(loaded),values=definition.columns.map(id=>q.text(id)),group=definition.groupBy?q.group(definition.groupBy):'NULL::text'
  const baseParameters=[...q.parameters]
  const cte=`WITH base AS (SELECT r.*,${group} g,${values.map((value,i)=>`${value} AS x${i}`).join(',')} FROM platform.dataset_rows r WHERE ${q.where})`
  const cells=values.map((_,i)=>`jsonb_build_object('column',${q.parameter(definition.columns[i])}::text,'present',count(x${i})::int,'missing',(count(*)-count(x${i}))::int,'missingRate',(100.0*(count(*)-count(x${i}))/nullif(count(*),0))::text)`)
  const select=`count(*)::int total,jsonb_build_array(${cells.join(',')}) cells`
  const summary=(await db.query(`${cte} SELECT ${select} FROM base`,q.parameters)).rows[0]
  // Each cell identifier is parameterized too; all projections use the same full parameter set.
  const total=summary?.total??0
  const groupOrdering=definition.groupBy&&numericType(column(loaded,definition.groupBy.column))?'g::numeric':'g'
  const grouped=await db.query(`${cte} SELECT g key,${select},count(*) OVER()::int groups_total FROM base GROUP BY g ORDER BY ${groupOrdering} NULLS LAST LIMIT ${definition.groupLimit}`,q.parameters)
  const affected=values.map((_,i)=>`x${i} IS NULL`).join(' OR ')
  const count=(await db.query(`${cte} SELECT count(*)::int n FROM base WHERE ${affected}`,baseParameters)).rows[0].n
  const rows=await db.query(`${cte} SELECT row_number,source_line,values,original_values FROM base WHERE ${affected} ORDER BY row_number LIMIT ${pageSize} OFFSET ${(page-1)*pageSize}`,baseParameters)
  return {kind:'missing' as const,filteredRows:total,columns:summary?.cells??[],groups:grouped.rows.map(row=>({key:row.key,rowCount:row.total,cells:row.cells})),groupsTotal:grouped.rows[0]?.groups_total??0,omittedGroups:Math.max(0,(grouped.rows[0]?.groups_total??0)-grouped.rows.length),affectedRows:count,page,pageSize,rows:rowsShape(rows.rows)}
}

export async function outliers(db:pg.PoolClient,loaded:Loaded,definition:Extract<Definition,{kind:'outliers'}>,page:number,pageSize:number) {
  const q=new Query(loaded),value=q.value(definition.column,true),group=definition.groupBy?q.group(definition.groupBy):'NULL::text'
  const cte=`WITH base AS (SELECT r.*,${value} v,${group} g FROM platform.dataset_rows r WHERE ${q.where}),
    summary AS (SELECT g,count(*)::int total,count(v)::int n,array_agg(v ORDER BY v) FILTER(WHERE v IS NOT NULL) nums FROM base GROUP BY g),
    quartiles AS MATERIALIZED (SELECT g,total,n,${quantile('nums','0.25')} q1,${quantile('nums','0.75')} q3 FROM summary),
    bounds AS MATERIALIZED (SELECT *,q1-${definition.factor}*(q3-q1) lower,q3+${definition.factor}*(q3-q1) upper FROM quartiles),
    flagged AS (SELECT b.row_number,b.source_line,b.values,b.original_values,s.g,s.q1,s.q3,s.lower,s.upper FROM base b JOIN bounds s ON coalesce(to_jsonb(b.g),'null'::jsonb)=coalesce(to_jsonb(s.g),'null'::jsonb) WHERE s.n>=4 AND (b.v<s.lower OR b.v>s.upper))`
  const summary=(await db.query(`${cte} SELECT coalesce(sum(total),0)::int total,coalesce(sum(n),0)::int present,count(*)::int groups_total,
    coalesce(sum(n) FILTER(WHERE n<4),0)::int insufficient,(SELECT count(*)::int FROM flagged) flagged FROM bounds`,q.parameters)).rows[0]
  const groupOrdering=definition.groupBy&&numericType(column(loaded,definition.groupBy.column))?'s.g::numeric':'s.g'
  const groups=await db.query(`${cte}, counts AS (SELECT g,count(*)::int flagged FROM flagged GROUP BY g)
    SELECT s.g key,s.total,s.n present,(s.total-s.n)::int missing,s.q1::text,s.q3::text,(s.q3-s.q1)::text iqr,s.lower::text,s.upper::text,
      CASE WHEN s.n<4 THEN 'insufficient' WHEN s.q1=s.q3 THEN 'zero_iqr' ELSE 'evaluated' END status,coalesce(c.flagged,0)::int flagged
    FROM bounds s LEFT JOIN counts c ON coalesce(to_jsonb(c.g),'null'::jsonb)=coalesce(to_jsonb(s.g),'null'::jsonb) ORDER BY ${groupOrdering} NULLS LAST LIMIT ${definition.groupLimit}`,q.parameters)
  const rows=await db.query(`${cte} SELECT row_number,source_line,values,original_values,jsonb_build_object('group',g,'q1',q1::text,'q3',q3::text,'lower',lower::text,'upper',upper::text) details
    FROM flagged ORDER BY row_number LIMIT ${pageSize} OFFSET ${(page-1)*pageSize}`,q.parameters)
  return {kind:'outliers' as const,filteredRows:summary.total,present:summary.present,missing:summary.total-summary.present,insufficientRows:summary.insufficient,flaggedRows:summary.flagged,groupsTotal:summary.groups_total,omittedGroups:Math.max(0,summary.groups_total-groups.rows.length),groups:groups.rows,page,pageSize,rows:rowsShape(rows.rows)}
}
