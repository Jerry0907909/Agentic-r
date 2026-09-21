import { useCallback, useRef, useState } from 'react'
import { ApiError } from '@/lib/api-client'
import { streamAsk } from '@/lib/stream'
import type { AskRequest, StreamEvent } from '@/types/stream'

export type StreamStatus = 'idle' | 'sending' | 'streaming' | 'error'

type Handlers = {
  onEvent: (event: StreamEvent) => void
  onFinish: (aborted: boolean) => void
  onError: (error: Error) => void
}

export function useChatStream() {
  const [status, setStatus] = useState<StreamStatus>('idle')
  const abortRef = useRef<AbortController | null>(null)

  const send = useCallback(
    async (
      endpoint: '/api/ask' | '/api/ask_graph',
      payload: AskRequest,
      handlers: Handlers,
    ) => {
      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller
      setStatus('sending')
      let aborted = false

      try {
        await streamAsk(
          endpoint,
          payload,
          (event) => {
            if ('c' in event) setStatus('streaming')
            handlers.onEvent(event)
            if ('err' in event) throw new ApiError(0, event.err)
          },
          controller.signal,
        )
        setStatus('idle')
      } catch (cause) {
        if (cause instanceof DOMException && cause.name === 'AbortError') {
          aborted = true
          setStatus('idle')
        } else {
          const error = cause instanceof Error ? cause : new Error('未知错误')
          setStatus('error')
          handlers.onError(error)
        }
      } finally {
        handlers.onFinish(aborted)
        if (abortRef.current === controller) abortRef.current = null
      }
    },
    [],
  )

  const stop = useCallback(() => abortRef.current?.abort(), [])
  const reset = useCallback(() => setStatus('idle'), [])

  return { status, busy: status === 'sending' || status === 'streaming', send, stop, reset }
}
