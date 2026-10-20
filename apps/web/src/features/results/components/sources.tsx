import { ChevronDown } from 'lucide-react'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/shared/ui/collapsible'
import type { PatientResponse } from '@/shared/api/schema'
import { collected, money } from '../lib/presentation'
import { SourceLink } from './source-link'

export function Sources({ response }: { response: PatientResponse }) {
  const records = response.medications.flatMap(result => result.medication ? [result.medication] : [])
  const conflicts = records.flatMap(record => record.data_conflicts.map(conflict => ({ record, conflict })))
  if (!response.sources.length && !conflicts.length) return null
  const labels: Record<string, string> = { ppv_price_mad: 'Prix public', hospital_price_mad: 'Prix hospitalier', commercialization_status: 'Commercialisation', atc_code: 'Code ATC', reimbursement_status: 'Remboursement' }
  const display = (value: string | number | boolean | null, field: string) => value == null ? 'Non renseigné' : typeof value === 'number' && field.endsWith('price_mad') ? money(value) : typeof value === 'boolean' ? value ? 'Oui' : 'Non' : String(value)
  return <Collapsible className="sources"><CollapsibleTrigger className="sources-trigger">Sources et détails<ChevronDown size={14} aria-hidden="true" /></CollapsibleTrigger><CollapsibleContent className="sources-content">
    <ul className="sources-list">{response.sources.map((source, index) => <li key={`${source.url}-${index}`}><SourceLink url={source.url}>{source.source}</SourceLink><span>{collected(source.fetched_at_utc)}</span></li>)}</ul>
    {records.map(record => <div className="record-details" key={record.source_record_id}><p className="font-medium">{record.brand_name} · {record.dosage}</p>{record.atc_code && <p>Code ATC : {record.atc_code}</p>}{record.reimbursement_status && <p>Remboursement renseigné : {record.reimbursement_status === 'yes' ? 'Oui' : 'Non'}</p>}</div>)}
    {conflicts.length > 0 && <div className="source-differences"><h4>Différences entre les sources</h4>{conflicts.map(({ record, conflict }, index) => <p key={index}><span className="font-medium">{record.brand_name} — {labels[conflict.field] ?? 'Information enregistrée'}</span><br />AMMPS : {display(conflict.reference_value, conflict.field)}. <SourceLink url={conflict.source_url}>{conflict.source}</SourceLink> : {display(conflict.observed_value, conflict.field)}.</p>)}</div>}
    <p className="source-limit">Ces informations correspondent aux dates de collecte et ne constituent pas une vérification du prix pratiqué aujourd’hui ou du stock.</p>
  </CollapsibleContent></Collapsible>
}
