import type pg from 'pg'
import { ApiError } from '../contracts.js'
import type { Source } from '../analytics/contracts.js'
import { column, invalid, load } from '../analytics/sql.js'
import type { Configuration, DashboardFilter, FilterValues, Widget } from './contracts.js'

const fail=()=>invalid('Filtre invalide : vérifiez les valeurs autorisées, les bornes et les correspondances explicites.')
export async function validateValues(db:pg.PoolClient,filter:DashboardFilter,values:string[]){
  if(!values.length)return
  if(filter.kind==='category'){
    if(!filter.choices.length||new Set(values).size!==values.length||values.some(value=>!filter.choices.includes(value)))throw fail()
  }else if(filter.kind==='presence'){
    if(values.length!==1||!['missing','present'].includes(values[0]!))throw fail()
  }else{
    if(values.length!==2||!values.some(Boolean))throw fail()
    const all=[...values,filter.minimum,filter.maximum].filter(Boolean)
    if(filter.kind==='numeric'){
      if(all.some(value=>!/^[-+]?(?:\d{1,38}(?:\.\d{1,12})?|\.\d{1,12})$/.test(value)))throw fail()
    }else if(all.some(value=>!/^\d{4}-\d{2}-\d{2}$/.test(value)||!Number.isFinite(Date.parse(value+'T00:00:00Z'))||new Date(value+'T00:00:00Z').toISOString().slice(0,10)!==value))throw fail()
    const type=filter.kind==='numeric'?'numeric':'date'
    const [low,high]=values
    const result=await db.query(`SELECT
      (NULLIF($1,'')::${type} IS NOT NULL AND NULLIF($2,'')::${type} IS NOT NULL AND NULLIF($1,'')::${type}>NULLIF($2,'')::${type}) OR
      (NULLIF($3,'')::${type} IS NOT NULL AND (NULLIF($1,'')::${type} IS NULL OR NULLIF($1,'')::${type}<NULLIF($3,'')::${type})) OR
      (NULLIF($4,'')::${type} IS NOT NULL AND (NULLIF($2,'')::${type} IS NULL OR NULLIF($2,'')::${type}>NULLIF($4,'')::${type})) AS invalid`,[low,high,filter.minimum,filter.maximum])
    if(result.rows[0].invalid)throw fail()
  }
}
export async function validateConfiguration(db:pg.PoolClient,owner:string,configuration:Configuration){
  for(const widget of configuration.widgets){
    if(widget.variant==='horizontal'&&(widget.definition.kind!=='aggregate'||widget.definition.chart!=='bar')||widget.variant==='donut'&&(widget.definition.kind!=='aggregate'||widget.definition.chart!=='pie'))throw invalid('La variante choisie exige des barres ou un graphique circulaire.')
  }
  for(const filter of configuration.filters){
    if(filter.kind==='category'&&(!filter.choices.length||new Set(filter.choices).size!==filter.choices.length))throw fail()
    // Bounds are validated even when the initial filter is empty.
    if(['date','numeric'].includes(filter.kind)&&(filter.minimum||filter.maximum))await validateValues(db,filter,[filter.minimum,filter.maximum])
    await validateValues(db,filter,filter.defaultValues)
    for(const mapping of filter.mappings){
      const widget=configuration.widgets.find(item=>item.id===mapping.widgetId)!
      const selected=column(await load(db,owner,widget.definition.source),mapping.column)
      if(filter.kind==='numeric'&&!['integer','decimal'].includes(selected.type)||filter.kind==='date'&&!['date','datetime'].includes(selected.type))throw fail()
      if(filter.kind==='category'&&!['text','boolean','integer','decimal','date'].includes(selected.type))throw fail()
      // ISO date ranges on UTC timestamps include their entire last day.
      if(filter.kind==='category')for(const value of filter.choices){
        if(selected.type==='boolean'&&!['true','false'].includes(value))throw fail()
      }
    }
  }
}
export async function filteredDefinition(db:pg.PoolClient,configuration:Configuration,widget:Widget,values:FilterValues,reader:boolean){
  if(new Set(values.map(item=>item.filterId)).size!==values.length)throw fail()
  for(const item of values){
    const filter=configuration.filters.find(filter=>filter.id===item.filterId)
    if(!filter||reader&&!filter.readerEditable)throw new ApiError(403,'filter_not_permitted','Ce filtre n’est pas autorisé pour le lecteur.')
    await validateValues(db,filter,item.values)
  }
  const source:Source={...widget.definition.source,filters:[...widget.definition.source.filters]}
  for(const filter of configuration.filters){
    const requested=values.find(value=>value.filterId===filter.id)?.values??filter.defaultValues
    const selected=requested.length?requested:filter.kind==='category'?filter.choices:
      ['date','numeric'].includes(filter.kind)&&(filter.minimum||filter.maximum)?[filter.minimum,filter.maximum]:[]
    if(!selected.length)continue
    await validateValues(db,filter,selected)
    for(const mapping of filter.mappings.filter(mapping=>mapping.widgetId===widget.id)){
      if(filter.kind==='category')source.filters.push({column:mapping.column,op:'in',values:selected})
      else if(filter.kind==='presence')source.filters.push({column:mapping.column,op:selected[0] as 'missing'|'present',values:[]})
      else{
        // Date filters apply ISO day boundaries to date and timestamp columns alike.
        const metadata=await db.query('SELECT data_type FROM platform.dataset_columns WHERE version_id=$1 AND id=$2',[source.versionId,mapping.column])
        const timestamp=filter.kind==='date'&&metadata.rows[0]?.data_type==='datetime'
        if(selected[0])source.filters.push({column:mapping.column,op:'gte',values:[timestamp?selected[0]+'T00:00:00.000000Z':selected[0]!]})
        if(selected[1])source.filters.push({column:mapping.column,op:'lte',values:[timestamp?selected[1]+'T23:59:59.999999Z':selected[1]!]})
      }
    }
  }
  if(source.filters.length>20)throw invalid('La combinaison dépasse 20 conditions pour ce widget. Réduisez ses filtres ou correspondances.')
  return {...widget.definition,source}
}
