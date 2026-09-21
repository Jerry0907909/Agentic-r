import { BookOpenText, ChevronDown, GitFork } from 'lucide-react'
import type { Source } from '@/types/stream'
import { cn } from '@/lib/utils'

export function SourceCards({ sources }: { sources: Source[] }) {
  if (!sources.length) return null

  return (
    <div className="mt-5 space-y-2.5 border-t border-border/70 pt-4">
      <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground">
        <BookOpenText aria-hidden="true" className="h-3.5 w-3.5" />
        回答依据 · {sources.length}
      </div>
      <div className="grid gap-2 lg:grid-cols-2">
        {sources.map((source, index) => (
          <details
            key={`${source.type}-${source.name}-${index}`}
            className={cn(
              'group rounded-xl border bg-surface/55 p-3 transition-[background-color,border-color] open:bg-background',
              source.type === 'graph' ? 'border-graph/25 hover:border-graph/45' : 'border-document/25 hover:border-document/45',
            )}
          >
            <summary className="flex cursor-pointer list-none items-start gap-2">
              <span
                className={cn(
                  'mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-lg',
                  source.type === 'graph'
                    ? 'bg-graph/10 text-graph'
                    : 'bg-document/10 text-document',
                )}
              >
                {source.type === 'graph' ? <GitFork aria-hidden="true" className="h-3.5 w-3.5" /> : <BookOpenText aria-hidden="true" className="h-3.5 w-3.5" />}
              </span>
              <span className="min-w-0 flex-1">
                <span className="line-clamp-2 text-xs font-medium leading-5">{source.name}</span>
                <span className="mt-0.5 flex gap-2 text-[10px] text-muted-foreground">
                  <span>{source.type === 'graph' ? '知识图谱' : '医学资料'}</span>
                  {source.score != null && <span>相关度 {(source.score * 100).toFixed(0)}%</span>}
                </span>
              </span>
              <ChevronDown aria-hidden="true" className="mt-1 h-3.5 w-3.5 text-muted-foreground transition-transform group-open:rotate-180" />
            </summary>
            <p className="mt-2 line-clamp-2 text-xs leading-5 text-muted-foreground group-open:hidden">{source.snippet}</p>
            <div className="mt-2 border-t border-border/60 pt-2 text-xs leading-5 text-muted-foreground">
              <p>{source.snippet}</p>
              {Boolean(source.meta?.cypher) && (
                <pre className="mt-2 overflow-x-auto rounded-lg bg-muted p-2 font-mono text-[10px]">
                  {String(source.meta?.cypher)}
                </pre>
              )}
            </div>
          </details>
        ))}
      </div>
    </div>
  )
}
