import { useState, type ReactNode } from 'react'
import { ArrowDown, ArrowUpRight, Check, ChevronDown, MapPin, Phone, Pill } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Badge } from '@/components/ui/badge'
import type { ChatRequest } from '@/api/client'
import type { Medication, MedicationResult, PatientResponse } from '@/api/schema'
import { collected, medicationLabel, money, phoneLink, safeLink, shortAnswer } from '@/lib/presentation'

type Action = (action: Omit<ChatRequest, 'request_id'>, label: string) => void
const fields = { strength: 'Dosage', form: 'Forme', presentation: 'Présentation', brand_name: 'Nom commercial' }

function SourceLink({ url, children }: { url: string; children: ReactNode }) {
  const href = safeLink(url)
  return href ? <a className="source-link" href={href} target="_blank" rel="noopener noreferrer" referrerPolicy="no-referrer">
    {children}<ArrowUpRight aria-hidden="true" size={13} /><span className="sr-only"> (nouvel onglet)</span>
  </a> : <span>{children}</span>
}

function MedicationCard({ record, result }: { record: Medication; result: MedicationResult }) {
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

function Clarification({ result, continuation, active, disabled, onAction }: { result: MedicationResult; continuation?: string | null; active: boolean; disabled: boolean; onAction: Action }) {
  const [value, setValue] = useState('')
  const question = result.clarification
  const refine = question?.field && question.options.length > 0
  const showCandidates = result.candidates.length > 0 && !(refine && result.candidate_count > 5)
  const name = result.mention.name ?? 'ce médicament'
  if (!refine && !showCandidates && result.next_candidate_offset == null) return null
  return <section className="clarification" aria-label={`Préciser ${name}`}>
    <div className="clarification-heading"><h3>{result.status === 'suggestions' ? 'Confirmer une présentation' : 'Choisir une présentation'}</h3>{result.candidate_count > 1 && <span className="muted text-xs">{result.candidate_count} correspondances</span>}</div>
    {!active && <p className="muted text-xs mb-3">Choix d’une étape précédente</p>}
    {refine && question?.field && <div className="refinement-row"><label className="refinement-label"><span>{fields[question.field]} pour {name}</span>
      <select aria-label={`${fields[question.field]} pour ${name}`} value={value} onChange={event => setValue(event.target.value)} disabled={!active || disabled}><option value="">Choisir une valeur enregistrée</option>{question.options.map(option => <option key={option.value} value={option.value}>{option.value} · {option.candidate_count} présentation{option.candidate_count > 1 ? 's' : ''}</option>)}</select></label>
      <Button variant="secondary" disabled={!active || disabled || !value || !continuation} onClick={() => onAction({ continuation_id: continuation, refinements: [{ mention_index: result.mention_index, field: question.field!, value }] }, `${fields[question.field!]} : ${value}`)}>Préciser<Check size={15} aria-hidden="true" /></Button>
    </div>}
    {showCandidates && <div className="candidate-list">{result.candidates.map(record => <Button key={record.source_record_id} variant="outline" className="candidate-button" disabled={!active || disabled || !continuation}
      onClick={() => onAction({ continuation_id: continuation, selections: [{ mention_index: result.mention_index, record_id: record.source_record_id }] }, `Présentation choisie : ${medicationLabel(record)}`)}>
      <span className="sr-only">Choisir </span><span className="candidate-description"><span className="candidate-name">{record.brand_name}{' '}<span>{record.dosage}</span></span><span className="candidate-presentation">{record.presentation}</span></span><span className="candidate-price">{money(record.ppv_price_mad)}<ArrowUpRight size={15} aria-hidden="true" /></span>
    </Button>)}</div>}
    {result.next_candidate_offset != null && <Button variant="ghost" className="more-button" disabled={!active || disabled || !continuation} onClick={() => onAction({ continuation_id: continuation, refinements: [{ mention_index: result.mention_index, field: 'page', value: String(result.next_candidate_offset) }] }, 'Afficher d’autres présentations')}>Présentations suivantes<ArrowDown size={14} aria-hidden="true" /></Button>}
  </section>
}

function Sources({ response }: { response: PatientResponse }) {
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

export function Results({ response, active, disabled, token, onAction }: { response: PatientResponse; active: boolean; disabled: boolean; token: string | null; onAction: Action }) {
  return <div className="assistant-content"><p className="answer-text" dir={response.interpretation.reply_script === 'arabic' ? 'rtl' : 'auto'}>{shortAnswer(response)}</p>
    {response.context?.needs_reference && <div className="reference-choices">{response.context.reference_options.map(option => { const label = [option.medication.name, option.medication.strength, option.medication.presentation].filter(Boolean).join(' · '); return <Button key={option.mention_index} variant="outline" disabled={!active || disabled || !token} onClick={() => onAction({ session_id: token, reference_index: option.mention_index }, `À propos de : ${label}`)}>À propos de {label}</Button> })}</div>}
    <div className="medication-results">{response.medications.map(result => <div key={result.mention_index}>{result.medication && <MedicationCard record={result.medication} result={result} />}<Clarification key={`${result.mention_index}-${response.continuation_id ?? ''}`} result={result} continuation={response.continuation_id} active={active} disabled={disabled} onAction={onAction} /></div>)}</div>
    {response.medications.length > 1 && response.order_pricing.status === 'calculated' && response.order_pricing.total_price_mad != null && <div className="order-total"><span>Total de votre sélection</span><strong>{money(response.order_pricing.total_price_mad)}</strong></div>}
    {response.medications.length > 1 && response.order_pricing.status === 'incomplete' && <p className="incomplete-total">Le total de la sélection ne peut pas encore être calculé. Certaines lignes sont à préciser.</p>}
    {response.pharmacy && response.pharmacy.pharmacies.length > 0 && <section className="pharmacy-results" aria-label="Pharmacies trouvées"><p className="directory-notice">Annuaire partiel de Rabat · Classement par nom, sans calcul de distance</p>{response.pharmacy.city_defaulted && <p className="muted text-sm">La recherche a été limitée à Rabat, la ville couverte par cet annuaire.</p>}
      {response.pharmacy.pharmacies.map(pharmacy => <article className="pharmacy-card" key={pharmacy.pharmacy_id}><h3>{pharmacy.name}</h3><p className="pharmacy-address"><MapPin size={16} aria-hidden="true" /><span>{pharmacy.address ?? 'Adresse non renseignée'} · {pharmacy.city}</span></p><div className="pharmacy-contact">{phoneLink(pharmacy.phone) ? <a href={phoneLink(pharmacy.phone)} className="phone-link"><Phone size={15} aria-hidden="true" />{pharmacy.phone}</a> : <span className="muted text-sm">{pharmacy.phone ?? 'Téléphone non renseigné'}</span>}<SourceLink url={pharmacy.source_url}>{pharmacy.source}</SourceLink></div><p className="collection-date">{collected(pharmacy.fetched_at_utc)}</p></article>)}
      {response.pharmacy.results_truncated && <p className="muted text-sm">{response.pharmacy.pharmacies.length} résultats affichés sur {response.pharmacy.result_count}. Précisez le nom ou le quartier pour affiner.</p>}<p className="directory-notice">Horaires inconnus · Garde non vérifiée · Stock non vérifié</p>
    </section>}<Sources response={response} />
  </div>
}
