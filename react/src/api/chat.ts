import { Message, Model, PendingType } from '@/types/types'
import { ToolInfo } from './model'
import { authenticatedFetch } from './auth'

function errorDetail(data: unknown, fallback: string): string {
  if (data && typeof data === 'object' && 'detail' in data) {
    const detail = (data as { detail: unknown }).detail
    if (typeof detail === 'string') return detail
  }
  return fallback
}

export const getChatSession = async (sessionId: string) => {
  const response = await authenticatedFetch(`/api/chat_session/${sessionId}`)
  const data = await response.json().catch(() => ([]))
  if (!response.ok) {
    throw new Error(errorDetail(data, 'Failed to load chat history'))
  }
  return data as Message[]
}

export const sendMessages = async (payload: {
  sessionId: string
  canvasId: string
  newMessages: Message[]
  textModel: Model
  toolList: ToolInfo[]
  systemPrompt: string | null
}) => {
  const response = await authenticatedFetch(`/api/chat`, {
    method: 'POST',
    body: JSON.stringify({
      messages: payload.newMessages,
      canvas_id: payload.canvasId,
      session_id: payload.sessionId,
      text_model: payload.textModel,
      tool_list: payload.toolList,
      system_prompt: payload.systemPrompt,
    }),
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(errorDetail(data, 'Failed to send message'))
  }
  return data as Message[]
}

export const cancelChat = async (sessionId: string) => {
  const response = await authenticatedFetch(`/api/cancel/${sessionId}`, {
    method: 'POST',
  })
  return await response.json()
}

export type ChatSessionStatus = {
  running: boolean
  last_progress?: string
  pending_type?: PendingType
}

export const getChatSessionStatus = async (sessionId: string) => {
  const response = await authenticatedFetch(`/api/chat/status/${sessionId}`)
  if (!response.ok) {
    throw new Error('Failed to fetch chat session status')
  }
  return (await response.json()) as ChatSessionStatus
}

export const renameChatSession = async (sessionId: string, title: string) => {
  const response = await authenticatedFetch(
    `/api/chat_session/${sessionId}/rename`,
    {
      method: 'POST',
      body: JSON.stringify({ title }),
    }
  )
  return await response.json()
}
