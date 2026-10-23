import { useId } from 'react'
import { decimalLabel, OP_NAMES, type Result } from './api'

const colors=['#17674f','#315ca8','#986515','#854c8f','#307c86','#a33e40','#5f6536','#655e86']
export function Chart({result}:{result:Result}){
  const caption=useId(),description=useId(),definition=result.definition
  if(!('style'in definition))return null
  const style=definition.style
  const measure=definition.kind==='aggregate'?definition.measures[0]:null
  const title=style.yLabel||measure?.label||(measure?OP_NAMES[measure.operation]:definition.kind==='histogram'?'Lignes par intervalle':'Observations appariées')
  const counts=['rows','present','missing','distinct']
  const unit=style.unit&&(!measure||!counts.includes(measure.operation))?' '+style.unit:''
  const label=(value:string|null)=>decimalLabel(value,style.precision)+unit
  if(result.kind==='aggregate'&&definition.kind==='aggregate'){
    if(definition.chart==='table')return null
    if(definition.chart==='kpi')return <div className="analytics-kpis" aria-label="Indicateurs">{result.rows[0]?.metrics.map((metric,i)=><article key={i}><h3>{definition.measures[i]?.label||OP_NAMES[definition.measures[i]!.operation]}</h3><p className="analytics-kpi-value">{decimalLabel(metric.value,style.precision)}{style.unit&&!counts.includes(definition.measures[i]!.operation)?' '+style.unit:''}</p><p>{metric.present} valeurs contributrices · {metric.missing} manquantes</p></article>)}</div>
    if(!result.rows.length)return <p>Aucun groupe à représenter.</p>
    const labels=result.rows.map(row=>row.groups.map(value=>value??'Manquant').join(' · '))
    if(definition.chart==='pie'){
      const counts=result.rows.map(row=>Number(row.metrics[0]?.value??0)),total=counts.reduce((a,b)=>a+b,0)
      if(!total)return <p>Aucune contribution à représenter dans le graphique circulaire.</p>
      const starts=counts.map((_,i)=>-Math.PI/2+counts.slice(0,i).reduce((sum,value)=>sum+value,0)/total*2*Math.PI)
      return <figure className="analytics-chart" aria-labelledby={caption}><figcaption id={caption}>{title} · {total} contributions</figcaption><svg viewBox="0 0 500 300" role="img" aria-labelledby={caption} aria-describedby={description}><desc id={description}>Répartition des comptes par groupe. Tous les groupes sont affichés ; le tableau fournit les valeurs exactes.</desc>{counts.map((value,i)=>{
        const start=starts[i]!,end=start+value/total*2*Math.PI
        if(value===total)return <circle key={i} cx={250} cy={150} r={120} fill={colors[i%colors.length]}><title>{labels[i]} : {value}</title></circle>
        const path=`M 250 150 L ${250+120*Math.cos(start)} ${150+120*Math.sin(start)} A 120 120 0 ${end-start>Math.PI?1:0} 1 ${250+120*Math.cos(end)} ${150+120*Math.sin(end)} Z`
        return value>0?<path key={i} d={path} fill={colors[i%colors.length]} stroke="white"><title>{labels[i]} : {value}</title></path>:null
      })}</svg>{style.legend&&<ul className="analytics-legend">{labels.map((text,i)=><li key={i}><span style={{background:colors[i%colors.length]}}/>{text} : {counts[i]}</li>)}</ul>}</figure>
    }
    if(definition.chart==='line'){
      const points=result.rows.map((row,i)=>{
        const date=row.groups[0],iso=date?date+(date.length===4?'-01-01':date.length===7?'-01':'')+'T00:00:00Z':''
        return {label:date,time:Date.parse(iso),position:result.plot.positions[i],value:row.metrics[0]?.value??null}
      }).filter(point=>Number.isFinite(point.time)).sort((a,b)=>a.time-b.time)
      if(!points.length)return <p>Aucune date présente à représenter.</p>
      if(!points.some(point=>point.position!==null&&point.position!==undefined))return <p>Aucune mesure présente pour ces dates. Consultez les effectifs dans le tableau.</p>
      const lo=points[0]!.time,hi=points.at(-1)!.time,x=(time:number)=>80+(hi===lo ? 0.5 :(time-lo)/(hi-lo))*740
      const path=points.map((point,i)=>point.position===null||point.position===undefined?'':`${i>0&&points[i-1]?.position!==null&&points[i-1]?.position!==undefined?'L':'M'} ${x(point.time)} ${320-Number(point.position)*260}`).join(' ')
      return <figure className="analytics-chart" aria-labelledby={caption}><figcaption id={caption}>{title}{unit} · première mesure</figcaption><svg viewBox="0 0 900 390" role="img" aria-labelledby={caption} aria-describedby={description}><desc id={description}>Courbe des groupes observés, espacés selon leurs dates UTC. Les valeurs manquantes interrompent la courbe. Le tableau contient les résultats exacts.</desc><path d="M80 40V320H840" fill="none" stroke="#70877d"/><path d={path} fill="none" stroke="#17674f" strokeWidth={3}/>{points.filter(p=>p.position!==null&&p.position!==undefined).map((point,i)=><circle key={i} cx={x(point.time)} cy={320-Number(point.position)*260} r={4} fill="#17674f"><title>{point.label} : {label(point.value)}</title></circle>)}<text x={80} y={345}>{points[0]?.label}</text><text x={820} y={345} textAnchor="end">{points.at(-1)?.label}</text><text x={450} y={377} textAnchor="middle">{style.xLabel||'Date du groupe (UTC)'}</text></svg><p>Les dates absentes ne sont pas inventées. Les groupes sans date restent dans le tableau. Une date de collecte ne démontre pas une évolution des prix.</p></figure>
    }
    if(result.plot.positions.every(position=>position===null))return <p>Aucune mesure définie à représenter. Les valeurs manquantes restent dans le tableau.</p>
    const height=Math.max(160,result.rows.length*34+65),zero=200+Number(result.plot.zero)*500
    return <figure className="analytics-chart" aria-labelledby={caption}><figcaption id={caption}>{title}{unit} · première mesure</figcaption><div className="analytics-chart-scroll" tabIndex={0} role="region" aria-label="Graphique en barres"><svg viewBox={`0 0 900 ${height}`} role="img" aria-labelledby={caption} aria-describedby={description}><desc id={description}>Classement des groupes. La ligne verticale marque zéro ; les valeurs négatives s’étendent à gauche. Le tableau contient toutes les valeurs exactes affichées.</desc><line x1={zero} x2={zero} y1={15} y2={height-45} stroke="#70877d"/>{result.rows.map((row,i)=>{const position=result.plot.positions[i],x=200+Number(position??result.plot.zero)*500,y=i*34+15;return <g key={i}><text x={190} y={y+17} textAnchor="end">{labels[i]!.length>25?labels[i]!.slice(0,22)+'…':labels[i]}<title>{labels[i]}</title></text>{position!==null&&<rect x={Math.min(zero,x)} y={y} width={Math.max(0,Math.abs(zero-x))} height={24} fill="#17674f"/>}<text x={725} y={y+17}>{label(row.metrics[0]?.value??null)}</text></g>})}<text x={450} y={height-10} textAnchor="middle">{style.xLabel||title}</text></svg></div></figure>
  }
  if(result.kind==='histogram'){
    if(!result.bins.length)return <p>Aucune valeur présente à représenter dans la distribution.</p>
    const max=Math.max(1,...result.bins.map(bin=>bin.count)),width=740/Math.max(1,result.bins.length)
    return <figure className="analytics-chart" aria-labelledby={caption}><figcaption id={caption}>{style.yLabel||'Distribution des valeurs présentes'}{unit}</figcaption><svg viewBox="0 0 900 390" role="img" aria-labelledby={caption} aria-describedby={description}><desc id={description}>Histogramme à intervalles de même largeur, borne inférieure incluse et supérieure exclue, sauf le dernier intervalle fermé. Les cellules manquantes sont exclues.</desc><path d="M80 40V320H840" fill="none" stroke="#70877d"/>{result.bins.map((bin,i)=><rect key={bin.index} x={80+i*width} y={320-bin.count/max*260} width={Math.max(1,width-2)} height={bin.count/max*260} fill="#17674f"><title>{label(bin.lower)} à {label(bin.upper)} : {bin.count} lignes</title></rect>)}<text x={80} y={345}>{label(result.minimum)}</text><text x={820} y={345} textAnchor="end">{label(result.maximum)}</text><text x={450} y={377} textAnchor="middle">{style.xLabel||'Valeur observée'}</text><text x={65} y={45} textAnchor="end">{max}</text></svg></figure>
  }
  if(result.kind==='scatter'&&!result.points.length)return <p>Aucune paire de valeurs présentes à représenter.</p>
  if(result.kind==='scatter')return <figure className="analytics-chart" aria-labelledby={caption}><figcaption id={caption}>Nuage de points · {result.points.length} paires affichées</figcaption><svg viewBox="0 0 900 390" role="img" aria-labelledby={caption} aria-describedby={description}><desc id={description}>Points observés selon deux colonnes numériques. Les coordonnées sont normalisées exactement côté serveur ; les nombres originaux figurent dans le tableau. Aucune relation causale n’est déduite.</desc><path d="M80 40V320H840" fill="none" stroke="#70877d"/>{result.points.map(point=><circle key={point.rowNumber} cx={80+Number(point.px)*740} cy={320-Number(point.py)*260} r={4} fill="#17674f" opacity={.65}><title>Ligne {point.sourceLine} : X {point.x} ; Y {point.y}</title></circle>)}<text x={450} y={370} textAnchor="middle">{style.xLabel||'X'}{unit}</text><text x={20} y={170} transform="rotate(-90 20 170)" textAnchor="middle">{style.yLabel||'Y'}{unit}</text></svg><p>Positions relatives aux minima/maxima des paires présentes ; axes constants centrés. Survolez les points ou utilisez le tableau pour les valeurs exactes.</p></figure>
  return null
}
