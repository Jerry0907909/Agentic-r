import { ApiError } from '@/lib/api-client'
import type { AskRequest, StreamEvent } from '@/types/stream'

type ErrorEnvelope = { code?: number; msg?: string; detail?: string | null }

async function httpError(response: Response) {
  let body: ErrorEnvelope = {}
  try {
    body = (await response.json()) as ErrorEnvelope
  } catch {
    // Keep the HTTP fallback below when an upstream proxy returned non-JSON.
  }
  return new ApiError(body.code ?? response.status, body.msg ?? `请求失败（${response.status}）`, body.detail)
}

function parseLine(line: string): StreamEvent {
  try {
    return JSON.parse(line) as StreamEvent
  } catch {
    throw new ApiError(0, '服务返回了无法解析的数据', line.slice(0, 160))
  }
}

export async function streamAsk(
  endpoint: '/api/ask' | '/api/ask_graph',
  payload: AskRequest,
  onEvent: (event: StreamEvent) => void,
  signal: AbortSignal,
) {
  const response = await fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/x-ndjson' },
    body: JSON.stringify(payload),
    signal,
  })
  if (!response.ok) throw await httpError(response)
  if (!response.body) throw new ApiError(0, '响应体为空，无法读取流')

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  const emit = (raw: string) => {
    const line = raw.trim()
    if (!line) return
    onEvent(parseLine(line))
  }

  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''
    lines.forEach(emit)
  }

  buffer += decoder.decode()
  emit(buffer)
}
