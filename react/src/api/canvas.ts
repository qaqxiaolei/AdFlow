import { CanvasData, Message, Session } from '@/types/types'
import { ToolInfo } from '@/api/model'
import { authenticatedFetch } from './auth'

export type ListCanvasesResponse = {
  id: string
  name: string
  description?: string
  thumbnail?: string
  created_at: string
  updated_at?: string
  session_id?: string
}

function errorDetail(data: unknown, fallback: string): string {
  if (data && typeof data === 'object' && 'detail' in data) {
    const detail = (data as { detail: unknown }).detail
    if (typeof detail === 'string') return detail
  }
  return fallback
}

export async function listCanvases(): Promise<ListCanvasesResponse[]> {
  const response = await authenticatedFetch('/api/canvas/list')
  const data = await response.json().catch(() => ([]))
  if (!response.ok) {
    throw new Error(errorDetail(data, 'Failed to load projects'))
  }
  return data
}

export async function createCanvas(data: {
  name: string
  canvas_id: string
  messages: Message[]
  session_id: string
  text_model: {
    provider: string
    model: string
    url: string
  }
  tool_list: ToolInfo[]

  system_prompt: string
}): Promise<{ id: string }> {
  const response = await authenticatedFetch('/api/canvas/create', {
    method: 'POST',
    body: JSON.stringify(data),
  })
  const result = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(errorDetail(result, 'Failed to create project'))
  }
  return result
}

export async function getCanvas(
  id: string
): Promise<{ data: CanvasData; name: string; sessions: Session[] }> {
  const response = await authenticatedFetch(`/api/canvas/${id}`)
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(errorDetail(data, 'Failed to load project'))
  }
  return data
}

export async function saveCanvas(
  id: string,
  payload: {
    data: CanvasData
    thumbnail: string
  }
): Promise<void> {
  const response = await authenticatedFetch(`/api/canvas/${id}/save`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new Error(errorDetail(data, 'Failed to save project'))
  }
}

export async function renameCanvas(id: string, name: string): Promise<void> {
  const response = await authenticatedFetch(`/api/canvas/${id}/rename`, {
    method: 'POST',
    body: JSON.stringify({ name }),
  })
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new Error(errorDetail(data, 'Failed to rename project'))
  }
}

export async function deleteCanvas(id: string): Promise<void> {
  const response = await authenticatedFetch(`/api/canvas/${id}/delete`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new Error(errorDetail(data, 'Failed to delete project'))
  }
}
