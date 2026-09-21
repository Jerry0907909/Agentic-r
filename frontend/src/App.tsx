import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Header } from '@/components/Header'
import { Sidebar } from '@/components/Sidebar'
import { MessageBubble } from '@/components/MessageBubble'
import { EmptyState } from '@/components/EmptyState'
import { Composer } from '@/components/Composer'
import { Toast, type ToastState } from '@/components/Toast'
import { getHealth, toChatMessage } from '@/lib/api-client'
import { conversationKeys, useConversations, useDeleteConversation, useMessages, useRenameConversation } from '@/hooks/useConversations'
import { useChatStream } from '@/hooks/useChatStream'
import type { AgentType, ChatMessage, Conversation, StreamEvent } from '@/types/stream'

type TabMap<T> = Record<AgentType, T>

const initialSelection: TabMap<string | null> = { rag: null, graph: null }
const initialMessages: TabMap<ChatMessage[]> = { rag: [], graph: [] }
const initialDrafts: TabMap<string> = { rag: '', graph: '' }

export default function App() {
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState<AgentType>('rag')
  const [selectedByTab, setSelectedByTab] = useState<TabMap<string | null>>(initialSelection)
  const [messagesByTab, setMessagesByTab] = useState<TabMap<ChatMessage[]>>(initialMessages)
  const [draftByTab, setDraftByTab] = useState<TabMap<string>>(initialDrafts)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [toast, setToast] = useState<ToastState | null>(null)
  const [dark, setDark] = useState(() => localStorage.getItem('agentic-rag-theme') === 'dark')
  const scrollRef = useRef<HTMLDivElement>(null)
  const keepAtBottomRef = useRef(true)

  const currentId = selectedByTab[activeTab]
  const currentMessages = messagesByTab[activeTab]
  const conversationsQuery = useConversations()
  const messagesQuery = useMessages(currentId)
  const renameMutation = useRenameConversation()
  const deleteMutation = useDeleteConversation()
  const healthQuery = useQuery({ queryKey: ['health'], queryFn: getHealth, refetchInterval: 30_000 })
  const chat = useChatStream()

  const notify = useCallback((message: string, tone: ToastState['tone'] = 'info') => {
    setToast({ id: Date.now(), message, tone })
  }, [])

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
    localStorage.setItem('agentic-rag-theme', dark ? 'dark' : 'light')
  }, [dark])

  useEffect(() => {
    if (!currentId || !messagesQuery.data || chat.busy) return
    const loaded = messagesQuery.data.items.map(toChatMessage)
    setMessagesByTab((previous) => ({ ...previous, [activeTab]: loaded }))
  }, [activeTab, chat.busy, currentId, messagesQuery.data])

  useEffect(() => {
    if (!messagesQuery.error) return
    notify(messagesQuery.error instanceof Error ? messagesQuery.error.message : '历史消息加载失败', 'error')
  }, [messagesQuery.error, notify])

  useEffect(() => {
    if (!keepAtBottomRef.current) return
    const frame = requestAnimationFrame(() => {
      const element = scrollRef.current
      if (element) element.scrollTop = element.scrollHeight
    })
    return () => cancelAnimationFrame(frame)
  }, [currentMessages])

  const allConversations = conversationsQuery.data?.items ?? []
  const conversations = useMemo(
    () => allConversations.filter((conversation) => conversation.agent_type === activeTab),
    [activeTab, allConversations],
  )
  const selectedConversation = allConversations.find((conversation) => conversation.id === currentId)

  const healthOkay = healthQuery.data
    ? healthQuery.data.mysql === 'ok' &&
      healthQuery.data.neo4j === 'ok' &&
      healthQuery.data.ollama === 'ok' &&
      healthQuery.data.bm25_corpus !== 'missing'
    : healthQuery.isError
      ? false
      : null

  const updateAssistant = useCallback(
    (tab: AgentType, assistantId: string, update: (message: ChatMessage) => ChatMessage) => {
      setMessagesByTab((previous) => ({
        ...previous,
        [tab]: previous[tab].map((message) => (message.id === assistantId ? update(message) : message)),
      }))
    },
    [],
  )

  const handleStreamEvent = (
    tab: AgentType,
    assistantId: string,
    event: StreamEvent,
    resolveConversation: (id: string) => void,
  ) => {
    if ('sid' in event) {
      resolveConversation(event.sid)
      setSelectedByTab((previous) => ({ ...previous, [tab]: event.sid }))
    } else if ('c' in event) {
      updateAssistant(tab, assistantId, (message) => ({ ...message, content: message.content + event.c }))
    } else if ('s' in event) {
      updateAssistant(tab, assistantId, (message) => ({ ...message, sources: event.s }))
    } else if ('u' in event) {
      updateAssistant(tab, assistantId, (message) => ({ ...message, usage: event.u }))
    } else if ('err' in event) {
      updateAssistant(tab, assistantId, (message) => ({ ...message, error: event.err, streaming: false }))
    }
  }

  const sendQuestion = (questionOverride?: string) => {
    const question = (questionOverride ?? draftByTab[activeTab]).trim()
    if (!question || chat.busy) return

    const tab = activeTab
    const endpoint = tab === 'rag' ? '/api/ask' : '/api/ask_graph'
    const conversationAtStart = selectedByTab[tab]
    const userId = `user-${Date.now()}`
    const assistantId = `assistant-${Date.now()}`
    let resolvedConversationId = conversationAtStart

    keepAtBottomRef.current = true
    setDraftByTab((previous) => ({ ...previous, [tab]: '' }))
    setMessagesByTab((previous) => ({
      ...previous,
      [tab]: [
        ...previous[tab],
        { id: userId, role: 'user', content: question },
        { id: assistantId, role: 'assistant', content: '', streaming: true },
      ],
    }))

    void chat.send(
      endpoint,
      { question, conversation_id: conversationAtStart, use_memory: true },
      {
        onEvent: (event) =>
          handleStreamEvent(tab, assistantId, event, (id) => {
            resolvedConversationId = id
          }),
        onError: (error) => {
          updateAssistant(tab, assistantId, (message) => ({
            ...message,
            error: message.error ?? error.message,
            streaming: false,
          }))
          notify(error.message, 'error')
        },
        onFinish: (aborted) => {
          updateAssistant(tab, assistantId, (message) => ({
            ...message,
            streaming: false,
            error: aborted && !message.content ? '已停止生成' : message.error,
          }))
          void queryClient.invalidateQueries({ queryKey: conversationKeys.all })
          if (resolvedConversationId) {
            void queryClient.invalidateQueries({ queryKey: conversationKeys.messages(resolvedConversationId) })
          }
        },
      },
    )
  }

  const selectConversation = (id: string) => {
    if (chat.busy) chat.stop()
    chat.reset()
    keepAtBottomRef.current = true
    setSelectedByTab((previous) => ({ ...previous, [activeTab]: id }))
    setMessagesByTab((previous) => ({ ...previous, [activeTab]: [] }))
    setSidebarOpen(false)
  }

  const newConversation = () => {
    if (chat.busy) chat.stop()
    chat.reset()
    setSelectedByTab((previous) => ({ ...previous, [activeTab]: null }))
    setMessagesByTab((previous) => ({ ...previous, [activeTab]: [] }))
    setDraftByTab((previous) => ({ ...previous, [activeTab]: '' }))
    setSidebarOpen(false)
  }

  const switchTab = (tab: AgentType) => {
    if (tab === activeTab) return
    if (chat.busy) {
      notify('请等待当前回答完成或先点击停止，再切换问答模式')
      return
    }
    setActiveTab(tab)
    keepAtBottomRef.current = true
    setSidebarOpen(false)
  }

  const renameConversation = async (conversation: Conversation) => {
    const title = window.prompt('请输入新的会话标题', conversation.title)?.trim()
    if (!title || title === conversation.title) return
    try {
      await renameMutation.mutateAsync({ id: conversation.id, title })
      notify('会话已重命名', 'success')
    } catch (cause) {
      notify(cause instanceof Error ? cause.message : '重命名失败', 'error')
    }
  }

  const removeConversation = async (conversation: Conversation) => {
    if (!window.confirm(`确定删除“${conversation.title}”及其全部消息吗？此操作不可撤销。`)) return
    try {
      await deleteMutation.mutateAsync(conversation.id)
      if (selectedByTab[activeTab] === conversation.id) newConversation()
      notify('会话已删除', 'success')
    } catch (cause) {
      notify(cause instanceof Error ? cause.message : '删除失败', 'error')
    }
  }

  return (
    <div className="flex h-dvh flex-col overflow-hidden bg-background text-foreground">
      <Header
        activeTab={activeTab}
        busy={chat.busy}
        dark={dark}
        healthOkay={healthOkay}
        onOpenSidebar={() => setSidebarOpen(true)}
        onTabChange={switchTab}
        onToggleTheme={() => setDark((value) => !value)}
      />

      <div className="flex min-h-0 flex-1">
        <Sidebar
          conversations={conversations}
          selectedId={currentId}
          open={sidebarOpen}
          loading={conversationsQuery.isLoading}
          onClose={() => setSidebarOpen(false)}
          onNew={newConversation}
          onSelect={selectConversation}
          onRename={renameConversation}
          onDelete={removeConversation}
        />

        <main className="flex min-w-0 flex-1 flex-col">
          {selectedConversation && (
            <div className="flex h-11 shrink-0 items-center border-b border-border/70 px-5 text-xs text-muted-foreground md:px-8">
              <span className="truncate font-medium text-foreground">{selectedConversation.title}</span>
              <span className="mx-2">·</span>
              <span>{selectedConversation.message_count} 条消息</span>
              {selectedConversation.total_tokens > 0 && (
                <>
                  <span className="mx-2">·</span>
                  <span>{selectedConversation.total_tokens.toLocaleString()} tokens</span>
                </>
              )}
            </div>
          )}

          <div
            ref={scrollRef}
            className="min-h-0 flex-1 overflow-y-auto"
            onScroll={(event) => {
              const element = event.currentTarget
              keepAtBottomRef.current = element.scrollHeight - element.scrollTop - element.clientHeight < 120
            }}
          >
            {messagesQuery.isLoading && currentId && currentMessages.length === 0 ? (
              <div className="mx-auto max-w-4xl space-y-5 px-4 py-8 md:px-8">
                {[1, 2, 3].map((item) => <div key={item} className="h-20 animate-pulse rounded-2xl bg-muted" />)}
              </div>
            ) : currentMessages.length === 0 ? (
              <EmptyState
                mode={activeTab}
                onSelect={(prompt) => {
                  setDraftByTab((previous) => ({ ...previous, [activeTab]: prompt }))
                  sendQuestion(prompt)
                }}
              />
            ) : (
              <div className="mx-auto max-w-4xl space-y-6 px-4 py-7 md:px-8">
                {currentMessages.map((message) => <MessageBubble key={message.id} message={message} />)}
              </div>
            )}
          </div>

          <Composer
            value={draftByTab[activeTab]}
            busy={chat.busy}
            mode={activeTab}
            onChange={(value) => setDraftByTab((previous) => ({ ...previous, [activeTab]: value }))}
            onSend={() => sendQuestion()}
            onStop={chat.stop}
            onNotice={notify}
          />
        </main>
      </div>

      <Toast toast={toast} onClose={() => setToast(null)} />
    </div>
  )
}
