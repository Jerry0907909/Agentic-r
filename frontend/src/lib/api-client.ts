import createClient from 'openapi-fetch'
import type { paths } from '@/types/api'
import type { ApiMessage, Conversation, HealthStatus } from '@/types/stream'

const api = createClient<paths>({ baseUrl: '/' })

type ErrorEnvelope = { code?: number; msg?: string; detail?: string | null }

export class ApiError extends Error {
  constructor(
    public code: number,
    message: string,
    public detail?: string | null,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

function throwApiError(error: unknown, response: Response): never {
  const body = (error ?? {}) as ErrorEnvelope
  throw new ApiError(body.code ?? response.status, body.msg ?? `请求失败（${response.status}）`, body.detail)
}

export async function listConversations() {
  const { data, error, response } = await api.GET('/api/conversations', {
    params: { query: { page: 1, size: 100 } },
  })
  if (error || !data) throwApiError(error, response)
  return data
}

export async function listMessages(conversationId: string) {
  const { data, error, response } = await api.GET('/api/conversations/{conversation_id}/messages', {
    params: { path: { conversation_id: conversationId }, query: { page: 1, size: 200 } },
  })
  if (error || !data) throwApiError(error, response)
  return data
}

export async function renameConversation(conversationId: string, title: string): Promise<Conversation> {
  const { data, error, response } = await api.PATCH('/api/conversations/{conversation_id}', {
    params: { path: { conversation_id: conversationId } },
    body: { title },
  })
  if (error || !data) throwApiError(error, response)
  return data
}

export async function deleteConversation(conversationId: string) {
  const { error, response } = await api.DELETE('/api/conversations/{conversation_id}', {
    params: { path: { conversation_id: conversationId } },
  })
  if (error || !response.ok) throwApiError(error, response)
}

export async function getHealth(): Promise<HealthStatus> {
  const { data, error, response } = await api.GET('/api/health')
  if (error || !data) throwApiError(error, response)
  return data
}

export function toChatMessage(message: ApiMessage): import('@/types/stream').ChatMessage {
  const usage =
    message.prompt_tokens != null &&
    message.completion_tokens != null &&
    message.total_tokens != null &&
    message.model != null &&
    message.latency_ms != null
      ? {
          prompt: message.prompt_tokens,
          completion: message.completion_tokens,
          total: message.total_tokens,
          model: message.model,
          latency_ms: message.latency_ms,
        }
      : null

  return {
    id: String(message.id),
    role: message.role,
    content: message.content,
    sources: message.sources ?? undefined,
    usage,
    createdAt: message.created_at,
  }
}
