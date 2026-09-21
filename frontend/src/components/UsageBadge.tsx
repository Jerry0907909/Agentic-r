import { Clock3, Cpu } from 'lucide-react'
import { formatLatency } from '@/lib/utils'
import type { Usage } from '@/types/stream'

export function UsageBadge({ usage }: { usage: Usage }) {
  return (
    <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted-foreground/90">
      <span className="inline-flex items-center gap-1">
        <Cpu aria-hidden="true" className="h-3 w-3" />
        {usage.total.toLocaleString()} tokens
      </span>
      <span>输入 {usage.prompt.toLocaleString()} · 输出 {usage.completion.toLocaleString()}</span>
      <span className="inline-flex items-center gap-1">
        <Clock3 aria-hidden="true" className="h-3 w-3" />
        {formatLatency(usage.latency_ms)}
      </span>
      <span className="max-w-48 truncate" title={usage.model}>{usage.model}</span>
    </div>
  )
}
