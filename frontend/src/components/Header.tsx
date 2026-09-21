import { BrainCircuit, Menu, Moon, Sun } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Tooltip } from '@/components/ui/tooltip'
import type { AgentType } from '@/types/stream'
import { cn } from '@/lib/utils'

type HeaderProps = {
  activeTab: AgentType
  busy: boolean
  dark: boolean
  healthOkay: boolean | null
  onOpenSidebar: () => void
  onTabChange: (tab: AgentType) => void
  onToggleTheme: () => void
}

export function Header({
  activeTab,
  busy,
  dark,
  healthOkay,
  onOpenSidebar,
  onTabChange,
  onToggleTheme,
}: HeaderProps) {
  const tabs: Array<{ value: AgentType; label: string }> = [
    { value: 'rag', label: 'Agentic RAG 对话' },
    { value: 'graph', label: '医疗疾病问答' },
  ]

  return (
    <header className="flex h-16 shrink-0 items-center gap-3 border-b border-border bg-card/90 px-4 backdrop-blur-xl md:px-6">
      <Button className="md:hidden" variant="ghost" size="icon" onClick={onOpenSidebar} aria-label="打开会话列表">
        <Menu className="h-5 w-5" />
      </Button>

      <div className="flex min-w-0 items-center gap-2.5 md:w-64">
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-primary text-white shadow-lg shadow-primary/20">
          <BrainCircuit className="h-5 w-5" />
        </span>
        <div className="hidden min-w-0 sm:block">
          <div className="truncate text-sm font-semibold">Agentic RAG</div>
          <div className="truncate text-[11px] text-muted-foreground">医疗智能问答系统</div>
        </div>
      </div>

      <nav className="mx-auto flex rounded-xl bg-muted p-1" aria-label="问答模式">
        {tabs.map((tab) => (
          <button
            key={tab.value}
            type="button"
            aria-current={activeTab === tab.value ? 'page' : undefined}
            className={cn(
              'rounded-lg px-3 py-2 text-xs font-medium transition-all sm:px-5 sm:text-sm',
              activeTab === tab.value
                ? 'bg-card text-primary shadow-sm'
                : 'text-muted-foreground hover:text-foreground',
            )}
            onClick={() => onTabChange(tab.value)}
            disabled={busy && activeTab !== tab.value}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <div className="flex items-center gap-2 md:w-64 md:justify-end">
        <div className="hidden items-center gap-2 rounded-full border border-border px-3 py-1.5 text-xs text-muted-foreground lg:flex">
          <span
            className={cn(
              'h-1.5 w-1.5 rounded-full',
              healthOkay === true && 'bg-emerald-500',
              healthOkay === false && 'bg-red-500',
              healthOkay === null && 'bg-amber-400',
            )}
          />
          {healthOkay === true ? '服务正常' : healthOkay === false ? '服务待检查' : '正在检查'}
        </div>
        <Tooltip content={dark ? '切换到浅色模式' : '切换到深色模式'}>
          <Button variant="ghost" size="icon" onClick={onToggleTheme} aria-label="切换主题">
            {dark ? <Sun className="h-4.5 w-4.5" /> : <Moon className="h-4.5 w-4.5" />}
          </Button>
        </Tooltip>
      </div>
    </header>
  )
}
