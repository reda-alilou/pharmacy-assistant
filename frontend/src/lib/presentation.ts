import type { Medication, PatientResponse } from '@/api/schema'

export function money(value: number | string | null | undefined) {
  if (value == null) return 'Prix non renseigné'
  return new Intl.NumberFormat('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(value)) + ' MAD'
}

export function collected(value: string | null | undefined) {
  const date = value ? new Date(value) : null
  if (!date || !Number.isFinite(date.getTime())) return 'Date de collecte non renseignée'
  return `Collecté le ${new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' }).format(date)}`
}

export function safeLink(value: string | null | undefined) {
  if (!value) return undefined
  try {
    const url = new URL(value)
    return ['https:', 'http:'].includes(url.protocol) && !url.username && !url.password ? url.href : undefined
  } catch { return undefined }
}

export function phoneLink(value: string | null) {
  if (!value) return undefined
  const number = value.replace(/[\s().-]/g, '')
  return /^\+?\d{8,15}$/.test(number) ? 'tel:' + number : undefined
}

export function medicationLabel(record: Medication) { return `${record.brand_name} · ${record.dosage} · ${record.presentation}` }

/** Only shorten simple French factual answers when every needed fact is in cards.
 * Keep clarification, safety/unsupported notices, missing-price explanations and
 * existing Arabic/Darija replies intact. No client-side factual generation.
 */
export function shortAnswer(response: PatientResponse) {
  const simple = response.status === 'answered' && response.interpretation.reply_language === 'fr' &&
    response.interpretation.intents.every(intent => ['price', 'medication_information', 'medication_request'].includes(intent)) &&
    response.interpretation.entities.symptom === null && !response.pharmacy && response.medications.length > 0 &&
    response.medications.every(result => result.status === 'resolved' && result.medication?.ppv_price_mad != null &&
      result.pricing?.status !== 'needs_quantity_clarification') && !response.context?.needs_reference
  if (!simple) return response.answer
  if (response.interpretation.intents.includes('price')) return response.medications.length > 1
    ? 'Voici les prix enregistrés pour votre sélection.' : 'Voici le prix enregistré pour cette présentation.'
  return 'Voici les informations enregistrées pour votre sélection.'
}
