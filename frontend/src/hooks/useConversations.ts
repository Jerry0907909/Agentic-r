import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  deleteConversation,
  listConversations,
  listMessages,
  renameConversation,
} from '@/lib/api-client'

export const conversationKeys = {
  all: ['conversations'] as const,
  list: () => [...conversationKeys.all, 'list'] as const,
  messages: (id: string) => [...conversationKeys.all, id, 'messages'] as const,
}

export function useConversations() {
  return useQuery({
    queryKey: conversationKeys.list(),
    queryFn: listConversations,
    staleTime: 15_000,
  })
}

export function useMessages(id: string | null) {
  return useQuery({
    queryKey: conversationKeys.messages(id ?? 'new'),
    queryFn: () => listMessages(id as string),
    enabled: Boolean(id),
  })
}

export function useRenameConversation() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) => renameConversation(id, title),
    onSuccess: () => client.invalidateQueries({ queryKey: conversationKeys.all }),
  })
}

export function useDeleteConversation() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: deleteConversation,
    onSuccess: () => client.invalidateQueries({ queryKey: conversationKeys.all }),
  })
}
