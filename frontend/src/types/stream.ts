import type { components } from './api'

export type AgentType = components['schemas']['AgentType']
export type AskRequest = components['schemas']['AskRequest']
export type Source = components['schemas']['Source']
export type Usage = components['schemas']['Usage']
export type Conversation = components['schemas']['Conversation']
export type ApiMessage = components['schemas']['Message']
export type HealthStatus = components['schemas']['HealthStatus']

export type StreamEvent =
  | { sid: string }
  | { c: string }
  | { s: Source[] }
  | { u: Usage }
  | { err: string }

export type ChatMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: Source[]
  usage?: Usage | null
  error?: string
  createdAt?: string
  streaming?: boolean
}
