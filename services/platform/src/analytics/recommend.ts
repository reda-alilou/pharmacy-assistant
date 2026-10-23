import type pg from 'pg'
import { definitionSchema, sourceSchema, type Definition } from './contracts.js'
import { Query, column, numericType, unique, type Loaded } from './sql.js'

export async function recommendations(db:pg.PoolClient,loaded:Loaded,definition:Extract<Definition,{kind:'recommend'}>) {
  unique(definition.columns)
  const columns=definition.columns.map(id=>column(loaded,id)),q=new Query(loaded)
  const fields=columns.map((col,i)=>{const value=q.text(col.id);return `count(DISTINCT ${value})::int c${i},count(${value})::int p${i}${['date','datetime'].includes(col.type)?`,count(DISTINCT left(${value},7))::int t${i}`:''}`})
  const stats=(await db.query(`SELECT count(*)::int total,${fields.join(',')} FROM platform.dataset_rows r WHERE ${q.where}`,q.parameters)).rows[0]!
  const options:{title:string;reason:string;definition:Definition}[]=[]
  const add=(title:string,reason:string,config:Record<string,unknown>)=>options.push({title,reason,definition:definitionSchema.parse({...config,source:definition.source,algorithm:'cp3-v1'})})
  const numeric=columns.filter(numericType),categories=columns.filter(c=>!numericType(c)&&!['date','datetime'].includes(c.type)),dates=columns.filter(c=>['date','datetime'].includes(c.type))
  for(const col of numeric.slice(0,1)) {
    add('Distribution numérique','Une colonne numérique : les intervalles de même largeur montrent la distribution, sans transformer les valeurs manquantes en zéros.',{kind:'histogram',column:col.id,bins:10})
    add('Indicateur numérique','La moyenne descriptive affiche aussi le nombre de valeurs présentes. Elle ne mesure pas une valeur thérapeutique.',{kind:'aggregate',measures:[{operation:'mean',column:col.id,label:'Moyenne'}],chart:'kpi'})
  }
  if(categories[0]) {
    const col=categories[0],count=stats['c'+columns.indexOf(col)]
    add('Répartition par catégorie',`${count} valeurs distinctes présentes ; un classement en barres accepte les catégories nombreuses et indique les groupes omis.`,{kind:'aggregate',measures:[{operation:'rows',label:'Lignes'}],groupBy:[{column:col.id}],chart:'bar'})
    if(count+(stats['p'+columns.indexOf(col)]<stats.total?1:0)<=8)add('Parts par catégorie','Huit groupes au maximum, valeurs manquantes incluses : tous les comptes peuvent former une répartition lisible.',{kind:'aggregate',measures:[{operation:'rows',label:'Lignes'}],groupBy:[{column:col.id}],limit:8,chart:'pie'})
    if(numeric[0])add('Mesure par catégorie','Une catégorie et un nombre : comparer des moyennes en indiquant leurs effectifs et les valeurs manquantes.',{kind:'aggregate',measures:[{operation:'mean',column:numeric[0].id,label:'Moyenne'}],groupBy:[{column:col.id}],chart:'bar'})
  }
  if(numeric.length>=2)add('Nuage de points','Deux mesures numériques : inspecter des paires observées, sans conclure à une causalité. Les points affichés sont bornés et les omissions annoncées.',{kind:'scatter',x:numeric[0]!.id,y:numeric[1]!.id})
  const date=dates[0]
  const timeSuitable=date&&stats['t'+columns.indexOf(date)]>=2
  if(timeSuitable)add('Regroupement temporel','Au moins deux mois observés : regrouper en UTC. La signification de la date doit être vérifiée ; une date de collecte ne prouve pas une évolution des prix.',{kind:'aggregate',measures:[numeric[0]?{operation:'mean',column:numeric[0].id,label:'Moyenne'}:{operation:'rows',label:'Lignes'}],groupBy:[{column:date.id,interval:'month'}],order:{by:'group',index:0,direction:'asc'},chart:'line',limit:200})
  return {kind:'recommend' as const,filteredRows:stats.total,columns:columns.map((col,i)=>({id:col.id,type:col.type,distinct:stats['c'+i],present:stats['p'+i]})),options,
    notes:[...(!options.length?['Aucune représentation graphique adaptée à cette sélection. Choisissez des colonnes numériques, catégorielles ou temporelles.']:[]),...(date&&!timeSuitable?['Une courbe mensuelle n’est pas proposée : moins de deux mois distincts sont observés. Aucun historique artificiel n’est créé.']:[])]}
}

export function templates(loaded:Loaded) {
  const named=(name:string,numeric=false)=>loaded.columns.find(c=>c.originalName===name&&(!numeric||numericType(c)))
  const form=named('form'),price=named('ppv_price_mad',true),conflicts=named('recorded_conflicts',true),source=named('source')
  const make=(id:string,title:string,reason:string,config:Record<string,unknown>|null)=>({id,title,reason,definition:config?definitionSchema.parse({source:loaded.source,...config,algorithm:'cp3-v1'}):null})
  return [
    make('forms','Présentations par forme',form?'Compte des lignes par forme enregistrée.':'Colonne « form » absente.',form?{kind:'aggregate',measures:[{operation:'rows',label:'Présentations'}],groupBy:[{column:form.id}],chart:'bar'}:null),
    make('missing-price','Prix publics manquants',price?'Complétude des prix déclarés, sans remplacer les valeurs manquantes par zéro.':'Colonne numérique « ppv_price_mad » absente.',price?{kind:'missing',columns:[price.id],groupBy:form?{column:form.id}:null}:null),
    make('prices','Distribution des prix publics',price?'Prix historiques observés en MAD ; aucune comparaison de valeur thérapeutique.':'Colonne numérique « ppv_price_mad » absente.',price?{kind:'histogram',column:price.id,bins:10,style:{unit:'MAD',xLabel:'Prix public observé'}}:null),
    make('disagreements','Désaccords entre sources',!conflicts?'Colonne numérique « recorded_conflicts » absente.':loaded.source.filters.length>=20?'Retirez un filtre avant d’ajouter la condition de désaccord (20 maximum).':'Lignes dont recorded_conflicts > 0, selon la provenance déclarée.',conflicts&&loaded.source.filters.length<20?{kind:'aggregate',source:sourceSchema.parse({...loaded.source,filters:[...loaded.source.filters,{column:conflicts.id,op:'gt',values:['0']}]}),measures:[{operation:'rows',label:'Présentations avec désaccord'}],groupBy:source?[{column:source.id}]:[],chart:source?'bar':'kpi'}:null),
  ]
}
