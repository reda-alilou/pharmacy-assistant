import { z } from 'zod'

const nullableText = z.string().nullable()
const money = z.string().regex(/^\d+\.\d{2}$/).nullable()
export const tokenSchema = z.string().min(20).max(100).regex(/^[\w-]+$/)
const timestamp = z.string().refine(value => Number.isFinite(Date.parse(value)), 'Date invalide')
const mention = z.object({ name: nullableText, strength: nullableText, quantity: nullableText, form: nullableText, presentation: nullableText })

export const medicationSchema = z.object({
  source_record_id: z.string().regex(/^\d+$/), brand_name: z.string(), active_substance: z.string(),
  dosage: z.string(), form: z.string(), presentation: z.string(), commercialization_status: z.string(),
  ppv_price_mad: z.number().finite().nonnegative().nullable(), source: z.literal('AMMPS'), source_url: z.string(),
  source_fetched_at_utc: nullableText.optional(), atc_code: nullableText.optional(),
  reimbursement_status: z.enum(['yes', 'no']).nullable().optional(),
  data_conflicts: z.array(z.object({ field: z.string(), reference_value: z.union([z.string(), z.number().finite(), z.boolean(), z.null()]),
    observed_value: z.union([z.string(), z.number().finite(), z.boolean(), z.null()]), source: z.string(), source_url: z.string() })).default([]),
})

const pricing = z.object({
  status: z.enum(['not_requested', 'calculated', 'needs_quantity_clarification', 'awaiting_medication', 'price_unavailable']),
  requested_quantity: nullableText.optional(), presentation_count: z.number().int().positive().nullable().optional(),
  unit_price_mad: money.optional(), total_price_mad: money.optional(), currency: z.literal('MAD'),
})

const resultSchema = z.object({
  mention_index: z.number().int().min(0).max(9), mention,
  status: z.enum(['resolved', 'ambiguous', 'suggestions', 'not_found', 'missing_name', 'filters_not_matched']),
  medication: medicationSchema.nullable(), candidates: z.array(medicationSchema), candidate_count: z.number().int().nonnegative(),
  clarification: z.object({ kind: z.enum(['refine_search', 'correct_filters', 'confirm_name', 'choose_record']),
    field: z.enum(['strength', 'form', 'presentation', 'brand_name']).nullable(),
    options: z.array(z.object({ value: z.string(), candidate_count: z.number().int().nonnegative() })) }).nullable(),
  next_candidate_offset: z.number().int().nonnegative().nullable(), pricing: pricing.nullable(),
})

export const responseSchema = z.object({
  status: z.enum(['answered', 'needs_clarification']), answer: z.string(),
  interpretation: z.object({ reply_language: z.enum(['fr', 'ar', 'darija']), reply_script: z.enum(['latin', 'arabic']),
    intents: z.array(z.string()), entities: z.object({ symptom: nullableText }) }),
  medications: z.array(resultSchema),
  pharmacy: z.object({ status: z.enum(['matches', 'ambiguous', 'not_found', 'outside_coverage']),
    applied_city: z.string(), city_defaulted: z.boolean(), result_count: z.number().int().nonnegative(),
    results_truncated: z.boolean(), pharmacies: z.array(z.object({ pharmacy_id: z.string(), name: z.string(), city: z.string(),
      address: nullableText, phone: nullableText, source: z.string(), source_url: z.string(), fetched_at_utc: z.string() })) }).nullable(),
  sources: z.array(z.object({ source: z.string(), url: z.string(), fetched_at_utc: nullableText, record_ids: z.array(z.string()) })),
  inference_performed: z.boolean(), continuation_id: tokenSchema.nullable().optional(),
  session_id: tokenSchema.nullable().optional(), session_expires_at_utc: timestamp.nullable().optional(),
  context: z.object({ needs_reference: z.boolean(), reference_options: z.array(z.object({ mention_index: z.number().int(), medication: mention })) }).nullable().optional(),
  order_pricing: z.object({ status: z.enum(['not_requested', 'calculated', 'incomplete']), total_price_mad: money, currency: z.literal('MAD') }),
})

export const messageSchema = z.object({
  sequence: z.number().int().nonnegative(), role: z.enum(['user', 'assistant']), outcome: z.enum(['pending', 'answered', 'failed']),
  text: nullableText, created_at_utc: timestamp, payload: z.record(z.string(), z.unknown()).nullable(),
})

export const conversationSchema = z.object({
  session_id: tokenSchema, expires_at_utc: timestamp, messages: z.array(messageSchema), response: responseSchema.nullable(),
})

export type PatientResponse = z.infer<typeof responseSchema>
export type Medication = z.infer<typeof medicationSchema>
export type MedicationResult = z.infer<typeof resultSchema>
export type Message = z.infer<typeof messageSchema>
export type Conversation = z.infer<typeof conversationSchema>
