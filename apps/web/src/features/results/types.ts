import type { ChatRequest } from '@/shared/api/client'

export type ResultAction = (action: Omit<ChatRequest, 'request_id'>, label: string) => void
