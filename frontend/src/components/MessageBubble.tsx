import { Bot, UserRound } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import rehypeHighlight from 'rehype-highlight'
import remarkGfm from 'remark-gfm'
import { SourceCards } from '@/components/SourceCard'
import { UsageBadge } from '@/components/UsageBadge'
import { cn, formatTime } from '@/lib/utils'
import type { ChatMessage } from '@/types/stream'

export function MessageBubble({ message }: { message: ChatMessage }) {
  const assistant = message.role === 'assistant'
  return (
    <article className={cn('flex gap-3', !assistant && 'flex-row-reverse')}>
      <div
        className={cn(
          'grid h-8 w-8 shrink-0 place-items-center rounded-xl border',
          assistant
            ? 'border-primary/20 bg-primary/10 text-primary'
            : 'border-primary bg-primary text-primary-foreground',
        )}
      >
        {assistant ? <Bot className="h-4 w-4" /> : <UserRound className="h-4 w-4" />}
      </div>
      <div className={cn('min-w-0 max-w-[min(760px,85%)]', !assistant && 'text-right')}>
        <div
          className={cn(
            'inline-block max-w-full rounded-2xl px-4 py-3 text-left text-sm leading-7 shadow-sm',
            assistant
              ? 'rounded-tl-md border border-border bg-card text-foreground'
              : 'rounded-tr-md bg-primary text-primary-foreground',
          )}
        >
          {assistant ? (
            <>
              {message.content ? (
                <div className="markdown-body">
                  <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
                    {message.content}
                  </ReactMarkdown>
                  {message.streaming && <span className="ml-0.5 inline-block animate-blink text-primary">▍</span>}
                </div>
              ) : message.streaming ? (
                <div className="flex items-center gap-2 py-1 text-muted-foreground">
                  <span className="flex gap-1">
                    <i className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary [animation-delay:-.3s]" />
                    <i className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary [animation-delay:-.15s]" />
                    <i className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary" />
                  </span>
                  正在检索并组织答案…
                </div>
              ) : null}
              {message.error && (
                <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs leading-5 text-red-600 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300">
                  {message.error}
                </div>
              )}
              {message.sources?.length ? <SourceCards sources={message.sources} /> : null}
              {message.usage ? <UsageBadge usage={message.usage} /> : null}
            </>
          ) : (
            <p className="whitespace-pre-wrap">{message.content}</p>
          )}
        </div>
        {message.createdAt && (
          <div className={cn('mt-1 px-1 text-[10px] text-muted-foreground', !assistant && 'text-right')}>
            {formatTime(message.createdAt)}
          </div>
        )}
      </div>
    </article>
  )
}
