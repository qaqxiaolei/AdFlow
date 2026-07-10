export type ModelInfo = {
  provider: string
  model: string
  type: 'text' | 'image' | 'tool' | 'video'
  url: string
}

export type ToolInfo = {
  provider: string
  id: string
  display_name?: string | null
  type?: 'image' | 'tool' | 'video'
}

async function fetchModelList(path: string): Promise<unknown[]> {
  const res = await fetch(path, { cache: 'no-store' })
  if (!res.ok) {
    throw new Error(`Failed to fetch ${path}: HTTP ${res.status}`)
  }
  const data = await res.json()
  if (!Array.isArray(data)) {
    throw new Error(`Invalid response from ${path}`)
  }
  return data
}

export async function listModels(): Promise<{
  llm: ModelInfo[]
  tools: ToolInfo[]
}> {
  const [modelsResp, toolsResp] = await Promise.all([
    fetchModelList('/api/list_models'),
    fetchModelList('/api/list_tools'),
  ])

  return {
    llm: modelsResp as ModelInfo[],
    tools: toolsResp as ToolInfo[],
  }
}
