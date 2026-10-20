import { Pill } from 'lucide-react'
import { Badge } from '@/shared/ui/badge'
import type { Medication, MedicationResult } from '@/shared/api/schema'
import { collected, money } from '../lib/presentation'
import { SourceLink } from './source-link'

export function MedicationCard({ record, result }: { record: Medication; result: MedicationResult }) {
  const pricing = result.pricing
  return <article className="medication-card" aria-label={`${record.brand_name}, ${record.dosage}, ${record.presentation}`}>
    <div className="card-title-row"><div className="medicine-heading"><span className="medicine-icon"><Pill size={19} aria-hidden="true" /></span><h3>{record.brand_name}</h3></div><Badge variant="outline" className="dose-badge">{record.dosage}</Badge></div>
    <p className="substance">{record.active_substance}</p><p className="presentation">{record.presentation}</p><p className="muted text-sm">{record.form}</p>
    <div className="price-row"><div><p className="price-label">Prix public enregistré</p><p className={record.ppv_price_mad == null ? 'missing-price' : 'unit-price'}>{money(record.ppv_price_mad)}</p></div>
      {pricing?.status === 'calculated' && pricing.presentation_count != null && pricing.total_price_mad != null && <div className="total-price"><p className="price-label">Total · {pricing.presentation_count} présentation{pricing.presentation_count > 1 ? 's' : ''}</p><p>{money(pricing.total_price_mad)}</p></div>}
    </div>
    {pricing?.status === 'needs_quantity_clarification' && <p className="quantity-notice">Quantité à préciser en présentations complètes.</p>}
    <p className="commercialization">Commercialisation enregistrée : {record.commercialization_status}</p>
    <div className="card-source"><span>Stock en pharmacie non vérifié</span><SourceLink url={record.source_url}>AMMPS</SourceLink></div>
    <p className="collection-date">{collected(record.source_fetched_at_utc)}</p>
    {record.data_conflicts.length > 0 && <p className="conflict-note">Les sources présentent des différences. Les valeurs AMMPS sont conservées ; voir les détails ci-dessous.</p>}
  </article>
}
