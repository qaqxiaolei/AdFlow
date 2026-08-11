import { ModelInfo, ToolInfo } from '@/api/model'
import { LLMConfig, Model } from '@/types/types'
import { create } from 'zustand'

export type GenerationMode = 'image' | 'video'

type ConfigsStore = {
  initCanvas: boolean
  setInitCanvas: (initCanvas: boolean) => void

  textModels: Model[]
  setTextModels: (models: Model[]) => void

  selectedTools: ToolInfo[]
  setSelectedTools: (models: ToolInfo[]) => void

  textModel?: Model
  setTextModel: (model?: Model) => void

  generationMode: GenerationMode
  setGenerationMode: (mode: GenerationMode) => void

  showInstallDialog: boolean
  setShowInstallDialog: (show: boolean) => void

  showUpdateDialog: boolean
  setShowUpdateDialog: (show: boolean) => void

  showSettingsDialog: boolean
  setShowSettingsDialog: (show: boolean) => void

  allTools: ToolInfo[]
  setAllTools: (tools: ToolInfo[]) => void

  providers: {
    [key: string]: LLMConfig
  }
  setProviders: (providers: { [key: string]: LLMConfig }) => void
}

function readStoredGenerationMode(): GenerationMode {
  if (typeof localStorage === 'undefined') return 'video'
  const stored = localStorage.getItem('generation_mode')
  return stored === 'image' || stored === 'video' ? stored : 'video'
}

const useConfigsStore = create<ConfigsStore>((set) => ({
  initCanvas: false,
  setInitCanvas: (initCanvas) => set({ initCanvas }),

  textModels: [],
  setTextModels: (models) => set({ textModels: models }),

  textModel: undefined,
  setTextModel: (model) => set({ textModel: model }),

  generationMode: readStoredGenerationMode(),
  setGenerationMode: (mode) => {
    localStorage.setItem('generation_mode', mode)
    set({ generationMode: mode })
  },

  showInstallDialog: false,
  setShowInstallDialog: (show) => set({ showInstallDialog: show }),

  showUpdateDialog: false,
  setShowUpdateDialog: (show) => set({ showUpdateDialog: show }),

  showSettingsDialog: false,
  setShowSettingsDialog: (show) => set({ showSettingsDialog: show }),

  providers: {},
  setProviders: (providers) => set({ providers }),

  allTools: [],
  setAllTools: (tools) => set({ allTools: tools }),

  selectedTools: [],
  setSelectedTools: (tools) => set({ selectedTools: tools }),
}))

export default useConfigsStore
