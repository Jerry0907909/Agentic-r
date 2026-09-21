import { MessageSquareText, Network, Pencil, Plus, Stethoscope, Trash2, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Tooltip } from '@/components/ui/tooltip'
import { cn, conversationTurnCount } from '@/lib/utils'
import type { Conversation } from '@/types/stream'

type DateGroup = { label: string; items: Conversation[] }

function startOfDay(date: Date) {
  const copy = new Date(date)
  copy.setHours(0, 0, 0, 0)
  return copy.getTime()
}

function groupByDate(items: Conversation[]): DateGroup[] {
  const today = startOfDay(new Date())
  const yesterday = today - 86_400_000
  const groups: DateGroup[] = [
    { label: '今天', items: [] },
    { label: '昨天', items: [] },
    { label: '更早', items: [] },
  ]
  items.forEach((item) => {
    const timestamp = new Date(item.updated_at).getTime()
    const target = timestamp >= today ? groups[0] : timestamp >= yesterday ? groups[1] : groups[2]
    target.items.push(item)
  })
  return groups.filter((group) => group.items.length)
}

type SidebarProps = {
  conversations: Conversation[]
  selectedId: string | null
  open: boolean
  loading: boolean
  collapsed: boolean
  onClose: () => void
  onNew: () => void
  onSelect: (conversation: Conversation) => void
  onRename: (conversation: Conversation) => void
  onDelete: (conversation: Conversation) => void
}

export function Sidebar({
  conversations,
  selectedId,
  open,
  loading,
  collapsed,
  onClose,
  onNew,
  onSelect,
  onRename,
  onDelete,
}: SidebarProps) {
  const compactConversations = [...conversations].sort((left, right) => {
    if (left.agent_type !== right.agent_type) return left.agent_type === 'rag' ? -1 : 1
    return new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime()
  })

  const content = (
    <aside className="flex h-full w-[264px] shrink-0 flex-col bg-surface/80 transition-[width] duration-200 motion-reduce:transition-none">
      <div className="flex items-center gap-2 p-3 pb-2">
        <Button className="w-full justify-start shadow-soft" onClick={onNew}>
          <Plus aria-hidden="true" className="h-4 w-4" />
          新建对话
        </Button>
        <Button className="md:hidden" variant="ghost" size="icon" onClick={onClose} aria-label="关闭会话列表">
          <X aria-hidden="true" className="h-5 w-5" />
        </Button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-4">
        {loading && (
          <div className="space-y-2 px-1 pt-3" aria-label="正在加载会话">
            {[1, 2, 3].map((item) => <div key={item} className="h-14 animate-pulse rounded-xl bg-muted" />)}
          </div>
        )}
        {!loading && conversations.length === 0 && (
          <div className="px-4 py-12 text-center text-xs leading-6 text-muted-foreground">
            <span className="mx-auto mb-3 grid h-12 w-12 place-items-center rounded-2xl bg-card text-primary ring-1 ring-border">
              <MessageSquareText aria-hidden="true" className="h-5 w-5" />
            </span>
            还没有历史会话
            <br />
            发起一次提问后会显示在这里
          </div>
        )}
        {!loading &&
          groupByDate(conversations).map((group) => (
            <section key={group.label} className="mb-5">
              <h2 className="px-3 pb-2 pt-2 text-[11px] font-semibold tracking-wider text-muted-foreground">
                {group.label}
              </h2>
              <div className="space-y-1">
                {group.items.map((conversation) => (
                  <div
                    key={conversation.id}
                    className={cn(
                      'group relative flex items-center rounded-2xl border pr-1 transition-[background-color,border-color,box-shadow]',
                      selectedId === conversation.id
                        ? 'border-primary/20 bg-card text-primary shadow-sm'
                        : 'border-transparent hover:border-border hover:bg-card/70',
                    )}
                  >
                    <button
                      className="min-w-0 flex-1 px-3 py-2.5 text-left"
                      type="button"
                      onClick={() => onSelect(conversation)}
                    >
                      <div className="truncate pr-20 text-sm font-medium">{conversation.title || '新会话'}</div>
                      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                        <span className="shrink-0 whitespace-nowrap rounded-full bg-primary/10 px-2 py-0.5 font-semibold text-primary">
                          {conversation.agent_type === 'graph' ? '图谱查询' : '健康问答'}
                        </span>
                        <span className="whitespace-nowrap">{conversationTurnCount(conversation.message_count)} 轮对话</span>
                      </div>
                    </button>
                    <div className="absolute right-1 top-0 flex opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100">
                      <Tooltip content="重命名">
                        <button
                          type="button"
                          className="grid h-11 w-11 place-items-center rounded-md text-muted-foreground hover:bg-card hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                          onClick={() => onRename(conversation)}
                          aria-label="重命名会话"
                        >
                          <Pencil aria-hidden="true" className="h-3.5 w-3.5" />
                        </button>
                      </Tooltip>
                      <Tooltip content="删除">
                        <button
                          type="button"
                          className="grid h-11 w-11 place-items-center rounded-md text-muted-foreground hover:bg-danger/10 hover:text-danger focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                          onClick={() => onDelete(conversation)}
                          aria-label="删除会话"
                        >
                          <Trash2 aria-hidden="true" className="h-3.5 w-3.5" />
                        </button>
                      </Tooltip>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          ))}
      </div>

      <div className="px-5 py-4 text-[11px] leading-5 text-muted-foreground">
        <div className="font-semibold text-foreground/75">Agentic RAG · 课程演示</div>
        医疗内容仅供参考，不构成诊疗建议
      </div>
    </aside>
  )

  const compactContent = (
    <aside className="flex h-full w-[72px] shrink-0 flex-col bg-surface/80 transition-[width] duration-200 motion-reduce:transition-none">
      <div className="flex flex-col items-center gap-2 p-3 pb-2">
        <Tooltip content="新建对话">
          <Button className="h-12 w-12 rounded-2xl" size="icon" onClick={onNew} aria-label="新建对话">
            <Plus aria-hidden="true" className="h-4 w-4" />
          </Button>
        </Tooltip>
      </div>

      <div className="flex min-h-0 flex-1 flex-col items-center gap-2 overflow-y-auto px-3 pb-3 pt-1">
        {loading && (
          <div className="space-y-2" aria-label="正在加载会话">
            {[1, 2, 3].map((item) => <div key={item} className="h-11 w-11 animate-pulse rounded-xl bg-muted" />)}
          </div>
        )}
        {!loading && conversations.length === 0 && (
          <Tooltip content="还没有历史会话">
            <span className="grid h-11 w-11 place-items-center rounded-xl text-muted-foreground ring-1 ring-border">
              <MessageSquareText aria-hidden="true" className="h-4 w-4" />
            </span>
          </Tooltip>
        )}
        {!loading && compactConversations.map((conversation) => {
          const ConversationIcon = conversation.agent_type === 'graph' ? Network : Stethoscope
          const title = conversation.title || '新会话'
          const selected = selectedId === conversation.id
          return (
            <Tooltip key={conversation.id} content={title}>
              <button
                type="button"
                aria-label={`打开会话：${title}`}
                aria-current={selected ? 'page' : undefined}
                className={cn(
                  'grid h-11 w-11 shrink-0 place-items-center rounded-xl border transition-[background-color,border-color,color] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary',
                  selected
                    ? 'border-primary/25 bg-primary/10 text-primary'
                    : 'border-transparent text-muted-foreground hover:border-border hover:bg-card hover:text-foreground',
                )}
                onClick={() => onSelect(conversation)}
              >
                <ConversationIcon aria-hidden="true" className="h-4 w-4" />
              </button>
            </Tooltip>
          )
        })}
      </div>
    </aside>
  )

  return (
    <>
      <div className="hidden h-full md:block">
        {collapsed ? compactContent : content}
      </div>
      {open && (
        <div className="fixed inset-0 z-40 md:hidden">
          <button className="absolute inset-0 bg-slate-950/35 backdrop-blur-sm" onClick={onClose} aria-label="关闭遮罩" />
          <div className="relative h-full w-[264px] max-w-[88vw] shadow-2xl">{content}</div>
        </div>
      )}
    </>
  )
}
