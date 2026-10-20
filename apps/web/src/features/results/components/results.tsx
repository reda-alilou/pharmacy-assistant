import { Button } from '@/shared/ui/button'
import type { PatientResponse } from '@/shared/api/schema'
import { money, shortAnswer } from '../lib/presentation'
import type { ResultAction } from '../types'
import { Clarification } from './clarification'
import { MedicationCard } from './medication-card'
import { PharmacyResults } from './pharmacy-results'
import { Sources } from './sources'

export function Results({ response, active, disabled, token, onAction }: { response: PatientResponse; active: boolean; disabled: boolean; token: string | null; onAction: ResultAction }) {
  return <div className="assistant-content"><p className="answer-text" dir={response.interpretation.reply_script === 'arabic' ? 'rtl' : 'auto'}>{shortAnswer(response)}</p>
    {response.context?.needs_reference && <div className="reference-choices">{response.context.reference_options.map(option => { const label = [option.medication.name, option.medication.strength, option.medication.presentation].filter(Boolean).join(' · '); return <Button key={option.mention_index} variant="outline" disabled={!active || disabled || !token} onClick={() => onAction({ session_id: token, reference_index: option.mention_index }, `À propos de : ${label}`)}>À propos de {label}</Button> })}</div>}
    <div className="medication-results">{response.medications.map(result => <div key={result.mention_index}>{result.medication && <MedicationCard record={result.medication} result={result} />}<Clarification key={`${result.mention_index}-${response.continuation_id ?? ''}`} result={result} continuation={response.continuation_id} active={active} disabled={disabled} onAction={onAction} /></div>)}</div>
    {response.medications.length > 1 && response.order_pricing.status === 'calculated' && response.order_pricing.total_price_mad != null && <div className="order-total"><span>Total de votre sélection</span><strong>{money(response.order_pricing.total_price_mad)}</strong></div>}
    {response.medications.length > 1 && response.order_pricing.status === 'incomplete' && <p className="incomplete-total">Le total de la sélection ne peut pas encore être calculé. Certaines lignes sont à préciser.</p>}
    <PharmacyResults response={response} /><Sources response={response} />
  </div>
}
