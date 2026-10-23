import type pg from 'pg'
import { definitionSchema,sources,type Definition } from '../analytics/contracts.js'
import { load } from '../analytics/sql.js'
import { configurationSchema } from '../dashboards/contracts.js'
import type { ResourceKind } from '../access.js'

const operations:Record<string,string>={rows:'Nombre de lignes',present:'Présents',missing:'Manquants',distinct:'Valeurs distinctes',sum:'Somme',mean:'Moyenne',median:'Médiane',min:'Minimum',max:'Maximum',q1:'Premier quartile',q3:'Troisième quartile',stddev_sample:'Écart-type échantillon',stddev_population:'Écart-type population'}
const kinds:Record<Definition['kind'],string>={aggregate:'Agrégats et indicateurs',histogram:'Histogramme',scatter:'Nuage de points',missing:'Complétude',outliers:'Signalements IQR',compare:'Comparaison explicite',recommend:'Recommandations de graphiques'}
const comparisons:Record<string,string>={contains:'contient',equals:'égal à',starts_with:'commence par',in:'parmi',gt:'supérieur à',gte:'supérieur ou égal à',lt:'inférieur à',lte:'inférieur ou égal à',between:'entre',before:'avant',after:'après',missing:'manquant',present:'présent'}
export async function reviewConfiguration(db:pg.PoolClient,user:string,datasetId:string,kind:ResourceKind,row:pg.QueryResultRow){
  const configuration=kind==='dashboard'?configurationSchema.parse(row.configuration):null
  const definitions=configuration?configuration.widgets.map(widget=>({id:widget.id,title:widget.title,definition:widget.definition as Definition})):[{id:row.id as string,title:row.title as string,definition:definitionSchema.parse(row.definition)}]
  const reviewed=[]
  for(const view of definitions)for(const source of sources(view.definition).filter(source=>source.datasetId===datasetId)){
    const loaded=await load(db,user,source),definition=view.definition,name=(id:string|null)=>id?loaded.columns.find(column=>column.id===id)?.name??'Colonne absente':'toutes les lignes'
    const side=definition.kind==='compare'&&source===definition.right?'right':'left'
    const settings:string[]=[]
    if(definition.kind==='aggregate'){
      settings.push(...definition.measures.map(measure=>`${measure.label||operations[measure.operation]} : ${operations[measure.operation]} · ${name(measure.column)}`))
      settings.push('Groupes : '+(definition.groupBy.map(group=>`${name(group.column)} (${group.interval==='value'?'valeur exacte':group.interval==='day'?'jour UTC':group.interval==='month'?'mois UTC':'année UTC'})`).join(' ; ')||'ensemble de la sélection'))
      settings.push(`Visualisation : ${definition.chart} ; au maximum ${definition.limit} groupes ; classement ${definition.order.direction==='asc'?'croissant':'décroissant'} par ${definition.order.by==='group'?'groupe':'mesure'} ${definition.order.index+1}`)
    }else if(definition.kind==='histogram')settings.push(`${name(definition.column)} ; ${definition.bins} intervalles de même largeur`)
    else if(definition.kind==='scatter')settings.push(`X : ${name(definition.x)} ; Y : ${name(definition.y)} ; ${definition.pointLimit} premières paires au maximum`)
    else if(definition.kind==='missing'||definition.kind==='recommend')settings.push('Colonnes : '+definition.columns.map(id=>name(id)).join(' ; '))
    else if(definition.kind==='outliers')settings.push(`${name(definition.column)} ; ${definition.factor} × IQR ; minimum 4 observations présentes par groupe`)
    else{
      settings.push('Côté de votre source : '+(side==='left'?'gauche':'droite'))
      settings.push('Colonnes de valeur explicitement mappées : '+(definition.mappings.map(pair=>name(pair[side])).join(' ; ')||'aucune'))
      settings.push('Clés uniques : '+(definition.keys.map(pair=>name(pair[side])).join(' ; ')||'aucune comparaison ligne par ligne'))
    }
    if((definition.kind==='missing'||definition.kind==='outliers')&&definition.groupBy)settings.push('Groupe comparable : '+name(definition.groupBy.column))
    if('style'in definition)settings.push(`Libellés : ${definition.style.xLabel||'axe X par défaut'} / ${definition.style.yLabel||'axe Y par défaut'} ; unité ${definition.style.unit||'aucune'} ; ${definition.style.precision} décimales d’affichage`)
    const interactive=configuration?.filters.filter(filter=>filter.mappings.some(mapping=>mapping.widgetId===view.id)).map(filter=>{
      const columns=filter.mappings.filter(mapping=>mapping.widgetId===view.id).map(mapping=>name(mapping.column)).join(' ; ')
      const perimeter=filter.kind==='category'?'Catégories autorisées : '+filter.choices.join(' ; '):filter.kind==='numeric'||filter.kind==='date'?`Bornes autorisées : ${filter.minimum||'sans minimum'} à ${filter.maximum||'sans maximum'}`:'Valeurs manquantes ou présentes'
      return `${filter.label} → ${columns}. ${perimeter}. Valeurs initiales : ${filter.defaultValues.join(' ; ')||'tout le périmètre autorisé'}. ${filter.readerEditable?'Ajustable par le lecteur':'Fixé par le propriétaire'}.`
    })??[]
    reviewed.push({title:view.title,sourceTitle:loaded.title,version:loaded.number,kind:kinds[definition.kind],settings,
      baseFilters:source.filters.map(filter=>`${name(filter.column)} ${comparisons[filter.op]} ${filter.values.join(' ; ')}`),search:source.search,interactive})
  }
  return {sources:reviewed}
}
