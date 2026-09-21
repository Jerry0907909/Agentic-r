import { BookOpenText, ChevronDown, GitFork } from 'lucide-react'
import type { Source } from '@/types/stream'
import { cn } from '@/lib/utils'

export function SourceCards({ sources }: { sources: Source[] }) {
  if (!sources.length) return null

  return (
    <div className="mt-4 space-y-2 border-t border-border/70 pt-3">
      <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
        <BookOpenText className="h-3.5 w-3.5" />
        回答依据 · {sources.length}
      </div>
      <div className="grid gap-2 lg:grid-cols-2">
        {sources.map((source, index) => (
          <details
            key={`${source.type}-${source.name}-${index}`}
            className={cn(
              'group rounded-xl border bg-background/70 p-3 transition-colors open:bg-background',
              source.type === 'graph' ? 'border-emerald-200 dark:border-emerald-900' : 'border-indigo-200 dark:border-indigo-900',
            )}
          >
            <summary className="flex cursor-pointer list-none items-start gap-2">
              <span
                className={cn(
                  'mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-lg',
                  source.type === 'graph'
                    ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300'
                    : 'bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300',
                )}
              >
                {source.type === 'graph' ? <GitFork className="h-3.5 w-3.5" /> : <BookOpenText className="h-3.5 w-3.5" />}
              </span>
              <span className="min-w-0 flex-1">
                <span className="line-clamp-2 text-xs font-medium leading-5">{source.name}</span>
                <span className="mt-0.5 flex gap-2 text-[10px] text-muted-foreground">
                  <span>{source.type === 'graph' ? 'Neo4j 图谱' : '向量文档'}</span>
                  {source.score != null && <span>相关度 {(source.score * 100).toFixed(0)}%</span>}
                </span>
              </span>
              <ChevronDown className="mt-1 h-3.5 w-3.5 text-muted-foreground transition-transform group-open:rotate-180" />
            </summary>
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
