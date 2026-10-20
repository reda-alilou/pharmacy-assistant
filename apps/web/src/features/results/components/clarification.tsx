import { useState } from 'react'
import { ArrowDown, ArrowUpRight, Check } from 'lucide-react'
import { Button } from '@/shared/ui/button'
import type { MedicationResult } from '@/shared/api/schema'
import { medicationLabel, money } from '../lib/presentation'
import type { ResultAction } from '../types'

const fields = { strength: 'Dosage', form: 'Forme', presentation: 'Présentation', brand_name: 'Nom commercial' }

export function Clarification({ result, continuation, active, disabled, onAction }: { result: MedicationResult; continuation?: string | null; active: boolean; disabled: boolean; onAction: ResultAction }) {
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
