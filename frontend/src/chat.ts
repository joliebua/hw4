import { request } from './api'
import type { ChatHistory, ChatResponse, PageContext } from './types'

/**
 * Chat client for the floating chat panel. Talks to Handsome Dan, the PydanticAI
 * agent behind FastAPI (backend/main.py → agent.py).
 */

/**
 * Send one message with the page the shopper is on, so Dan knows what
 * "this" means on a product page. The reply includes product cards built
 * from the database.
 */
export function askDan(message: string, conversationId: string | null, page: PageContext): Promise<ChatResponse> {
  return request<ChatResponse>('/api/chat', {
    method: 'POST',
    body: JSON.stringify({ message, conversation_id: conversationId, page }),
  })
}

/** A signed-in shopper's saved chat (empty for guests), ready to continue. */
export function loadChatHistory(): Promise<ChatHistory> {
  return request<ChatHistory>('/api/chat/history')
}

/** "Start a new chat": the agent forgets this conversation. */
export async function resetConversation(conversationId: string): Promise<void> {
  await request<void>(`/api/chat/${encodeURIComponent(conversationId)}`, { method: 'DELETE' })
}
