/**
 * Generated contract snapshot. Run `npm run api:types` while the FastAPI
 * service is running whenever the backend contract changes.
 */
export interface components {
  schemas: {
    AgentType: 'rag' | 'graph'
    AskRequest: {
      question: string
      conversation_id?: string | null
      use_memory?: boolean
    }
    Source: {
      type: 'vector' | 'graph'
      name: string
      score?: number | null
      snippet: string
      meta?: Record<string, unknown> | null
    }
    Usage: {
      prompt: number
      completion: number
      total: number
      model: string
      latency_ms: number
    }
    Conversation: {
      id: string
      title: string
      agent_type: 'rag' | 'graph'
      message_count: number
      total_tokens: number
      created_at: string
      updated_at: string
    }
    ConversationCreate: {
      title?: string
      agent_type?: 'rag' | 'graph'
    }
    ConversationUpdate: { title: string }
    Message: {
      id: number
      role: 'user' | 'assistant'
      content: string
      sources?: components['schemas']['Source'][] | null
      prompt_tokens?: number | null
      completion_tokens?: number | null
      total_tokens?: number | null
      model?: string | null
      latency_ms?: number | null
      created_at: string
    }
    Page_Conversation_: {
      total: number
      page: number
      size: number
      items: components['schemas']['Conversation'][]
    }
    Page_Message_: {
      total: number
      page: number
      size: number
      items: components['schemas']['Message'][]
    }
    ErrorBody: { code: number; msg: string; detail?: string | null }
    HealthStatus: {
      mysql: string
      neo4j: string
      ollama: string
      faiss_index: string
      bm25_corpus: string
      rerank: string
    }
  }
}

export interface paths {
  '/api/ask': {
    post: {
      requestBody: { content: { 'application/json': components['schemas']['AskRequest'] } }
      responses: { 200: { content: { 'application/x-ndjson': unknown } } }
    }
  }
  '/api/ask_graph': paths['/api/ask']
  '/api/conversations': {
    get: {
      parameters: { query?: { page?: number; size?: number } }
      responses: { 200: { content: { 'application/json': components['schemas']['Page_Conversation_'] } } }
    }
    post: {
      requestBody: { content: { 'application/json': components['schemas']['ConversationCreate'] } }
      responses: { 201: { content: { 'application/json': components['schemas']['Conversation'] } } }
    }
  }
  '/api/conversations/{conversation_id}': {
    patch: {
      parameters: { path: { conversation_id: string } }
      requestBody: { content: { 'application/json': components['schemas']['ConversationUpdate'] } }
      responses: { 200: { content: { 'application/json': components['schemas']['Conversation'] } } }
    }
    delete: {
      parameters: { path: { conversation_id: string } }
      responses: { 204: { content: never } }
    }
  }
  '/api/conversations/{conversation_id}/messages': {
    get: {
      parameters: {
        path: { conversation_id: string }
        query?: { page?: number; size?: number }
      }
      responses: { 200: { content: { 'application/json': components['schemas']['Page_Message_'] } } }
    }
  }
  '/api/health': {
    get: {
      responses: { 200: { content: { 'application/json': components['schemas']['HealthStatus'] } } }
    }
  }
}
