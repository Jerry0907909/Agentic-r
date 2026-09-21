import { MessageSquareText, Pencil, Plus, Trash2, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Tooltip } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'
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
  onClose: () => void
  onNew: () => void
  onSelect: (id: string) => void
  onRename: (conversation: Conversation) => void
  onDelete: (conversation: Conversation) => void
}

export function Sidebar({
  conversations,
  selectedId,
  open,
  loading,
  onClose,
  onNew,
  onSelect,
  onRename,
  onDelete,
}: SidebarProps) {
  const content = (
    <aside className="flex h-full w-[292px] shrink-0 flex-col border-r border-border bg-card">
      <div className="flex items-center gap-2 p-4">
        <Button className="flex-1 justify-start rounded-xl" onClick={onNew}>
          <Plus className="h-4 w-4" />
          新建对话
        </Button>
        <Button className="md:hidden" variant="ghost" size="icon" onClick={onClose} aria-label="关闭会话列表">
          <X className="h-5 w-5" />
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
            <MessageSquareText className="mx-auto mb-3 h-7 w-7 opacity-50" />
            还没有历史会话
            <br />
            发起一次提问后会显示在这里
          </div>
        )}
        {!loading &&
          groupByDate(conversations).map((group) => (
            <section key={group.label} className="mb-5">
              <h2 className="px-3 pb-2 pt-2 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                {group.label}
              </h2>
              <div className="space-y-1">
                {group.items.map((conversation) => (
                  <div
                    key={conversation.id}
                    className={cn(
                      'group relative flex items-center rounded-xl pr-1 transition-colors',
                      selectedId === conversation.id ? 'bg-primary/10 text-primary' : 'hover:bg-muted',
                    )}
                  >
                    <button
                      className="min-w-0 flex-1 px-3 py-2.5 text-left"
                      type="button"
                      onClick={() => onSelect(conversation.id)}
                    >
                      <div className="truncate text-sm font-medium">{conversation.title || '新会话'}</div>
                      <div className="mt-1 flex gap-2 text-[10px] text-muted-foreground">
                        <span>{conversation.message_count} 条消息</span>
                        {conversation.total_tokens > 0 && <span>{conversation.total_tokens.toLocaleString()} tokens</span>}
                      </div>
                    </button>
                    <div className="flex opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100">
                      <Tooltip content="重命名">
                        <button
                          type="button"
                          className="rounded-md p-1.5 text-muted-foreground hover:bg-card hover:text-foreground"
                          onClick={() => onRename(conversation)}
                          aria-label="重命名会话"
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </button>
                      </Tooltip>
                      <Tooltip content="删除">
                        <button
                          type="button"
                          className="rounded-md p-1.5 text-muted-foreground hover:bg-red-50 hover:text-red-500 dark:hover:bg-red-950/30"
                          onClick={() => onDelete(conversation)}
                          aria-label="删除会话"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </Tooltip>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          ))}
      </div>

      <div className="border-t border-border p-4 text-[11px] leading-5 text-muted-foreground">
        医疗内容仅作课程演示，不构成医疗建议
      </div>
    </aside>
  )

  return (
    <>
      <div className="hidden h-full md:block">{content}</div>
      {open && (
        <div className="fixed inset-0 z-40 md:hidden">
          <button className="absolute inset-0 bg-slate-950/35 backdrop-blur-sm" onClick={onClose} aria-label="关闭遮罩" />
          <div className="relative h-full w-[292px] shadow-2xl">{content}</div>
        </div>
      )}
    </>
  )
}
