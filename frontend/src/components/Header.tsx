import { HeartPulse, Menu, Moon, Network, PanelLeftClose, PanelLeftOpen, Stethoscope, Sun } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Tooltip } from '@/components/ui/tooltip'
import type { AgentType } from '@/types/stream'
import { cn } from '@/lib/utils'

type HeaderProps = {
  activeTab: AgentType
  busy: boolean
  dark: boolean
  sidebarCollapsed: boolean
  onOpenSidebar: () => void
  onTabChange: (tab: AgentType) => void
  onToggleSidebar: () => void
  onToggleTheme: () => void
}

export function Header({
  activeTab,
  busy,
  dark,
  sidebarCollapsed,
  onOpenSidebar,
  onTabChange,
  onToggleSidebar,
  onToggleTheme,
}: HeaderProps) {
  const tabs: Array<{ value: AgentType; label: string; shortLabel: string; icon: typeof Stethoscope }> = [
    { value: 'rag', label: '医疗健康问答', shortLabel: '健康问答', icon: Stethoscope },
    { value: 'graph', label: '知识图谱查询', shortLabel: '图谱查询', icon: Network },
  ]

  return (
    <header className="shrink-0 bg-card/95 px-3 py-3 backdrop-blur-xl md:px-0 md:py-0">
      <div
        className={cn(
          'flex flex-wrap items-center gap-2.5 sm:flex-nowrap md:grid md:gap-0 md:transition-[grid-template-columns] md:duration-200 motion-reduce:transition-none',
          sidebarCollapsed
            ? 'md:grid-cols-[72px_minmax(0,1fr)]'
            : 'md:grid-cols-[264px_minmax(0,1fr)]',
        )}
      >
        <div
          className={cn(
            'relative flex min-h-12 min-w-0 items-center gap-2.5 md:h-full md:px-4 md:py-2',
            sidebarCollapsed && 'md:justify-center md:px-0',
          )}
        >
          <Button className="md:hidden" variant="ghost" size="icon" onClick={onOpenSidebar} aria-label="打开会话列表">
            <Menu aria-hidden="true" className="h-5 w-5" />
          </Button>
          <span className={cn('grid h-10 w-10 shrink-0 place-items-center rounded-2xl bg-accent/14 text-accent ring-1 ring-primary/50', sidebarCollapsed && 'md:hidden')}>
            <HeartPulse aria-hidden="true" className="h-5 w-5" />
          </span>
          <div className={cn('hidden min-w-0 sm:block', sidebarCollapsed && 'md:hidden')}>
            <div className="truncate text-[15px] font-bold tracking-tight">医知助手</div>
          </div>
          <Tooltip content={sidebarCollapsed ? '展开会话列表' : '折叠会话列表'}>
            <Button
              className={cn(
                'z-20 hidden h-11 w-11 rounded-full border border-primary/25 bg-card text-primary shadow-soft hover:border-primary/45 hover:bg-primary/5 md:inline-flex',
                !sidebarCollapsed && 'absolute -right-[22px]',
              )}
              variant="ghost"
              size="icon"
              onClick={onToggleSidebar}
              aria-label={sidebarCollapsed ? '展开会话列表' : '折叠会话列表'}
              aria-expanded={!sidebarCollapsed}
            >
              {sidebarCollapsed
                ? <PanelLeftOpen aria-hidden="true" className="h-4.5 w-4.5" />
                : <PanelLeftClose aria-hidden="true" className="h-4.5 w-4.5" />}
            </Button>
          </Tooltip>
        </div>

        <div className="contents md:grid md:min-w-0 md:grid-cols-[minmax(0,1fr)_auto] md:items-center md:gap-4 md:py-2 md:pl-8 md:pr-4 xl:grid-cols-[minmax(0,1fr)_minmax(520px,620px)_minmax(0,1fr)] xl:pl-8 xl:pr-6">
          <nav className="order-3 mt-3 grid min-h-12 w-full grid-cols-2 gap-2 sm:order-none sm:mt-0 sm:max-w-xl sm:flex-1 md:order-none md:col-start-1 md:max-w-none md:justify-self-stretch xl:col-start-2" aria-label="问答模式">
            {tabs.map((tab) => {
              const Icon = tab.icon
              const selected = activeTab === tab.value
              return (
                <button
                  key={tab.value}
                  type="button"
                  aria-pressed={selected}
                  className={cn(
                    'group flex min-h-12 min-w-0 items-center gap-2.5 rounded-2xl border px-3 py-2 text-left transition-[background-color,border-color,box-shadow,color] duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:cursor-not-allowed disabled:opacity-45 sm:px-4',
                    selected
                      ? 'border-primary/35 bg-primary/10 text-primary shadow-sm'
                      : 'border-transparent bg-surface/80 text-muted-foreground hover:border-primary/20 hover:bg-primary/5 hover:text-foreground',
                  )}
                  onClick={() => onTabChange(tab.value)}
                  disabled={busy && !selected}
                >
                  <span className={cn('grid h-8 w-8 shrink-0 place-items-center rounded-xl', selected ? 'bg-primary text-primary-foreground' : 'bg-card text-muted-foreground ring-1 ring-border')}>
                    <Icon aria-hidden="true" className="h-4 w-4" />
                  </span>
                  <span className="min-w-0">
                    <span className="block truncate text-xs font-bold sm:hidden">{tab.shortLabel}</span>
                    <span className="hidden truncate text-sm font-bold sm:block">{tab.label}</span>
                  </span>
                </button>
              )
            })}
          </nav>

          <div className="ml-auto flex min-h-12 shrink-0 items-center md:col-start-2 md:row-start-1 md:ml-0 md:justify-self-end xl:col-start-3">
            <Tooltip content={dark ? '切换到浅色模式' : '切换到深色模式'}>
              <Button variant="ghost" size="icon" onClick={onToggleTheme} aria-label="切换主题">
                {dark ? <Sun aria-hidden="true" className="h-4.5 w-4.5" /> : <Moon aria-hidden="true" className="h-4.5 w-4.5" />}
              </Button>
            </Tooltip>
          </div>
        </div>
      </div>
    </header>
  )
}
