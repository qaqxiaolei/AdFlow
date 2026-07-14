import { Message } from '@/types/types'
import { authenticatedFetch } from './auth'

export const sendMagicGenerate = async (payload: {
  sessionId: string
  canvasId: string
  newMessages: Message[]
  systemPrompt: string | null
}) => {
  const response = await authenticatedFetch(`/api/magic`, {
    method: 'POST',
    body: JSON.stringify({
      messages: payload.newMessages,
      canvas_id: payload.canvasId,
      session_id: payload.sessionId,
      system_prompt: payload.systemPrompt,
    }),
  })
  const data = await response.json()
  return data as Message[]
}

export const cancelMagicGenerate = async (sessionId: string) => {
  try {
    const response = await authenticatedFetch(
      `/api/magic/cancel/${sessionId}`,
      {
        method: 'POST',
      }
    )
    return await response.json()
  } catch (error) {
    console.error('Error cancelling magic generate:', error)
    throw error
  }
}
