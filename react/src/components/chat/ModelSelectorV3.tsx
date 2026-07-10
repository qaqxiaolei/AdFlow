import React, { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuCheckboxItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
  DropdownMenuLabel,
  DropdownMenuGroup,
} from '@/components/ui/dropdown-menu'
import { MobileBottomSheet } from '@/components/ui/mobile-bottom-sheet'
import { Switch } from '@/components/ui/switch'
import { Checkbox } from '@/components/ui/checkbox'
import { useTranslation } from 'react-i18next'
import { useConfigs, useRefreshModels, useModelsStatus } from '@/contexts/configs'
import { ModelInfo, ToolInfo } from '@/api/model'
import { PROVIDER_NAME_MAPPING } from '@/constants'
import { ScrollArea } from '@/components/ui/scroll-area'
import { useIsMobile } from '@/hooks/use-mobile'

interface ModelSelectorV3Props {
  onModelToggle?: (modelId: string, checked: boolean) => void
  onAutoToggle?: (enabled: boolean) => void
}

const ModelSelectorV3: React.FC<ModelSelectorV3Props> = ({
  onModelToggle,
  onAutoToggle
}) => {
  const refreshModels = useRefreshModels()
  const { modelsLoading, modelsError } = useModelsStatus()
  const {
    textModel,
    setTextModel,
    textModels,
    selectedTools,
    setSelectedTools,
    allTools,
  } = useConfigs()

  const [activeTab, setActiveTab] = useState<'image' | 'video' | 'text'>('image')
  const [open, setOpen] = useState(false)
  const { t } = useTranslation()
  const isMobile = useIsMobile()

  const initialAutoMode = allTools.length > 0 && selectedTools.length === allTools.length
  const [autoMode, setAutoMode] = useState(initialAutoMode)

  useEffect(() => {
    if (open && allTools.length === 0 && textModels.length === 0) {
      refreshModels()
    }
  }, [open, allTools.length, textModels.length, refreshModels])

  const groupModelsByProvider = (models: typeof allTools) => {
    const grouped: { [provider: string]: typeof allTools } = {}
    models?.forEach((model) => {
      if (!grouped[model.provider]) {
        grouped[model.provider] = []
      }
      grouped[model.provider].push(model)
    })
    return grouped
  }

  const groupLLMsByProvider = (models: typeof textModels) => {
    const grouped: { [provider: string]: typeof textModels } = {}
    models?.forEach((model) => {
      if (!grouped[model.provider]) {
        grouped[model.provider] = []
      }
      grouped[model.provider].push(model)
    })
    return grouped
  }

  const groupedLLMs = groupLLMsByProvider(textModels)
  const groupedTools = groupModelsByProvider(allTools)

  const getToolsByType = (type: 'image' | 'video') => {
    const filteredTools = allTools.filter(tool => tool.type === type)
    return groupModelsByProvider(filteredTools)
  }

  const handleModelToggle = (modelKey: string, checked: boolean) => {
    if (activeTab === 'text') {
      const model = textModels?.find((m) => m.provider + ':' + m.model === modelKey)
      if (model) {
        setTextModel(model)
        localStorage.setItem('text_model', modelKey)
      }
    } else {
      let newSelected: ToolInfo[] = []
      const tool = allTools.find((m) => m.provider + ':' + m.id === modelKey)

      if (checked) {
        if (tool) {
          newSelected = [...selectedTools, tool]
        }
      } else {
        newSelected = selectedTools.filter(
          (t) => t.provider + ':' + t.id !== modelKey
        )
      }

      setSelectedTools(newSelected)
      localStorage.setItem(
        'disabled_tool_ids',
        JSON.stringify(
          allTools.filter((t) => !newSelected.includes(t)).map((t) => t.id)
        )
      )

      const isAuto = newSelected.length === allTools.length
      setAutoMode(isAuto)
    }
    onModelToggle?.(modelKey, checked)
  }

  const handleModelClick = (modelKey: string) => {
    if (activeTab === 'text') {
      const model = textModels?.find((m) => m.provider + ':' + m.model === modelKey)
      if (model) {
        setTextModel(model)
        localStorage.setItem('text_model', modelKey)
        onModelToggle?.(modelKey, true)
      }
    } else {
      if (autoMode) {
        setAutoMode(false)
        const tool = allTools.find((m) => m.provider + ':' + m.id === modelKey)
        if (tool) {
          setSelectedTools([tool])
          localStorage.setItem(
            'disabled_tool_ids',
            JSON.stringify(
              allTools.filter((t) => t.id !== tool.id).map((t) => t.id)
            )
          )
          onModelToggle?.(modelKey, true)
        }
      } else {
        const isSelected = selectedTools.some(t => t.provider + ':' + t.id === modelKey)
        handleModelToggle(modelKey, !isSelected)
      }
    }
  }

  const handleAutoToggle = (enabled: boolean) => {
    if (activeTab === 'text') {
      return
    }

    if (enabled) {
      setSelectedTools(allTools)
      localStorage.setItem('disabled_tool_ids', JSON.stringify([]))
    } else {
      const imageTools = allTools.filter(tool => tool.type === 'image')
      const videoTools = allTools.filter(tool => tool.type === 'video')

      const firstImageTool = imageTools.length > 0 ? imageTools[0] : null
      const firstVideoTool = videoTools.length > 0 ? videoTools[0] : null

      const selectedToolsList: ToolInfo[] = []
      if (firstImageTool) selectedToolsList.push(firstImageTool)
      if (firstVideoTool) selectedToolsList.push(firstVideoTool)

      if (selectedToolsList.length > 0) {
        setSelectedTools(selectedToolsList)
        localStorage.setItem(
          'disabled_tool_ids',
          JSON.stringify(
            allTools.filter((t) => !selectedToolsList.includes(t)).map((t) => t.id)
          )
        )
      }
    }
    setAutoMode(enabled)
    onAutoToggle?.(enabled)
  }

  const getCurrentModels = () => {
    if (activeTab === 'text') {
      return groupedLLMs
    }
    return getToolsByType(activeTab)
  }

  const isModelSelected = (modelKey: string) => {
    if (activeTab === 'text') {
      return textModel?.provider + ':' + textModel?.model === modelKey
    }
    return selectedTools.some(t => t.provider + ':' + t.id === modelKey)
  }

  const getProviderDisplayInfo = (provider: string) => {
    const providerInfo = PROVIDER_NAME_MAPPING[provider]
    return {
      name: providerInfo?.name || provider,
      icon: providerInfo?.icon,
    }
  }

  const tabs = [
    { id: 'image', label: t('chat:modelSelector.tabs.image') },
    { id: 'video', label: t('chat:modelSelector.tabs.video') },
    { id: 'text', label: t('chat:modelSelector.tabs.text') }
  ] as const

  const triggerButton = (
    <Button
      size={'sm'}
      variant="outline"
      className={`shrink-0 touch-manipulation h-8 w-8 p-0 sm:h-8 sm:w-auto sm:px-3 ${autoMode
        ? 'bg-background border-border text-muted-foreground'
        : 'text-primary border-green-200 bg-green-50'
        }`}
      onClick={isMobile ? () => setOpen(true) : undefined}
    >
      {autoMode ? (
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path stroke="none" d="M0 0h24v24H0z" fill="none" /><path d="M4 4m0 1a1 1 0 0 1 1 -1h4a1 1 0 0 1 1 1v4a1 1 0 0 1 -1 1h-4a1 1 0 0 1 -1 -1z" /><path d="M4 14m0 1a1 1 0 0 1 1 -1h4a1 1 0 0 1 1 1v4a1 1 0 0 1 -1 1h-4a1 1 0 0 1 -1 -1z" /><path d="M14 14m0 1a1 1 0 0 1 1 -1h4a1 1 0 0 1 1 1v4a1 1 0 0 1 -1 1h-4a1 1 0 0 1 -1 -1z" /><path d="M14 7l6 0" /><path d="M17 4l0 6" /></svg>
      ) : (
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="currentColor" className="icon icon-tabler icons-tabler-filled icon-tabler-apps"><path stroke="none" d="M0 0h24v24H0z" fill="none" /><path d="M9 3h-4a2 2 0 0 0 -2 2v4a2 2 0 0 0 2 2h4a2 2 0 0 0 2 -2v-4a2 2 0 0 0 -2 -2z" /><path d="M9 13h-4a2 2 0 0 0 -2 2v4a2 2 0 0 0 2 2h4a2 2 0 0 0 2 -2v-4a2 2 0 0 0 -2 -2z" /><path d="M19 13h-4a2 2 0 0 0 -2 2v4a2 2 0 0 0 2 2h4a2 2 0 0 0 2 -2v-4a2 2 0 0 0 -2 -2z" /><path d="M17 3a1 1 0 0 1 .993 .883l.007 .117v2h2a1 1 0 0 1 .117 1.993l-.117 .007h-2v2a1 1 0 0 1 -1.993 .117l-.007 -.117v-2h-2a1 1 0 0 1 -.117 -1.993l.117 -.007h2v-2a1 1 0 0 1 1 -1z" /></svg>
      )}
    </Button>
  )

  const panelBody = (
    <>
      <div className="flex items-center justify-between px-4 py-2.5 border-b">
        {!isMobile && <div className="text-sm font-medium">{t('chat:modelSelector.title')}</div>}
        <div className={`flex items-center gap-2 ${isMobile ? 'w-full justify-between' : ''}`}>
          {isMobile && (
            <span className="text-xs text-muted-foreground">{t('chat:modelSelector.auto')}</span>
          )}
          {!isMobile && (
            <span className="text-sm text-muted-foreground">{t('chat:modelSelector.auto')}</span>
          )}
          <Switch
            checked={autoMode}
            onCheckedChange={handleAutoToggle}
          />
        </div>
      </div>

      <div className="flex p-1 bg-muted rounded-lg mx-4 my-2.5">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id)}
            className={`flex-1 px-2 py-2 sm:px-3 sm:py-1 rounded-md text-xs sm:text-sm font-medium transition-colors cursor-pointer touch-manipulation min-h-9 ${activeTab === tab.id
              ? 'bg-background text-foreground shadow-sm'
              : 'text-muted-foreground hover:text-foreground'
              }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <ScrollArea className={isMobile ? 'flex-1 min-h-0' : undefined}>
        <div className={`px-4 pb-4 select-none ${isMobile ? 'max-h-[45vh]' : 'max-h-80 h-80'}`}>
          {Object.keys(getCurrentModels()).length > 0 ? (
            Object.entries(getCurrentModels()).map(([provider, providerModels], index, array) => {
              const providerInfo = getProviderDisplayInfo(provider)
              const isLastGroup = index === array.length - 1
              return (
                <DropdownMenuGroup key={provider}>
                  <DropdownMenuLabel className="text-xs font-medium text-muted-foreground px-0 py-2">
                    <div className="flex items-center gap-2">
                      <img
                        src={providerInfo.icon}
                        alt={providerInfo.name}
                        className="w-4 h-4 rounded-full"
                      />
                      {providerInfo.name}
                    </div>
                  </DropdownMenuLabel>
                  {providerModels.map((model: ModelInfo | ToolInfo) => {
                    const modelKey = activeTab === 'text'
                      ? model.provider + ':' + (model as ModelInfo).model
                      : model.provider + ':' + (model as ToolInfo).id
                    const modelName = activeTab === 'text'
                      ? (model as ModelInfo).model
                      : (model as ToolInfo).display_name || (model as ToolInfo).id

                    return (
                      <div
                        key={modelKey}
                        className="flex items-center justify-between p-3 min-h-11 hover:bg-muted/50 active:bg-muted transition-colors mb-0.5 cursor-pointer touch-manipulation rounded-lg"
                        onClick={() => handleModelClick(modelKey)}
                      >
                        <div className="flex-1">
                          <div className="font-medium text-sm">{modelName}</div>
                        </div>
                        <Checkbox
                          checked={isModelSelected(modelKey)}
                          className={`ml-4 ${autoMode && activeTab !== 'text' ? 'opacity-50' : ''}`}
                          disabled={autoMode && activeTab !== 'text'}
                        />
                      </div>
                    )
                  })}
                  {!isLastGroup && <DropdownMenuSeparator className="my-2" />}
                </DropdownMenuGroup>
              )
            })
          ) : (
            <div className="flex flex-col items-center justify-center gap-3 h-32 text-muted-foreground px-4 text-center">
              <div className="text-sm">
                {modelsLoading
                  ? (t('chat:modelSelector.loading') || 'Loading models…')
                  : (t('chat:noModelsAvailable') || 'No models available')}
              </div>
              {!modelsLoading && (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="touch-manipulation"
                  onClick={() => refreshModels()}
                >
                  {t('common:retry') || 'Retry'}
                </Button>
              )}
              {modelsError && !modelsLoading && (
                <div className="text-xs text-destructive/80">
                  {t('chat:modelSelector.loadFailed') || 'Could not reach the server. Check network and try again.'}
                </div>
              )}
            </div>
          )}
        </div>
      </ScrollArea>
    </>
  )

  if (isMobile) {
    return (
      <>
        {triggerButton}
        <MobileBottomSheet
          open={open}
          onOpenChange={setOpen}
          title={t('chat:modelSelector.title')}
          className="max-h-[60dvh]"
          contentClassName="px-0 pb-0 flex flex-col min-h-0"
          showHandle
        >
          {panelBody}
        </MobileBottomSheet>
      </>
    )
  }

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        {triggerButton}
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-96 max-w-[calc(100vw-2rem)] select-none">
        {panelBody}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export default ModelSelectorV3
