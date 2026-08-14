import { cancelChat } from '@/api/chat'
import { cancelMagicGenerate } from '@/api/magic'
import { uploadImage } from '@/api/upload'
import { Button } from '@/components/ui/button'
import { useConfigs } from '@/contexts/configs'
import {
  eventBus,
  TCanvasAddImagesToChatEvent,
  TMaterialAddImagesToChatEvent,
} from '@/lib/event'
import { cn, dataURLToFile } from '@/lib/utils'
import { Message, MessageContent, Model } from '@/types/types'
import { ModelInfo, ToolInfo } from '@/api/model'
import { useMutation } from '@tanstack/react-query'
import { useDrop } from 'ahooks'
import { produce } from 'immer'
import {
  ArrowUp,
  Loader2,
  PlusIcon,
  Square,
  XIcon,
  RectangleVertical,
  ChevronDown,
  ImageIcon,
  Clapperboard,
} from 'lucide-react'
import type { GenerationMode } from '@/stores/configs'
import { AnimatePresence, motion } from 'motion/react'
import Textarea, { TextAreaRef } from 'rc-textarea'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import ModelSelectorV3 from './ModelSelectorV3'
import { useAuth } from '@/contexts/AuthContext'
import { useBalance } from '@/hooks/use-balance'
import { useWechatRechargeReturn } from '@/hooks/use-wechat-recharge-return'
import { RechargeDialog } from '@/components/auth/RechargeDialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { MobileBottomSheet } from '@/components/ui/mobile-bottom-sheet'
import { useIsMobile } from '@/hooks/use-mobile'

type ChatTextareaProps = {
  pending: boolean
  className?: string
  messages: Message[]
  sessionId?: string
  /** 首页可加大默认高度；画布内保持原自动增高 */
  autoSize?: boolean | { minRows?: number; maxRows?: number }
  onSendMessages: (
    data: Message[],
    configs: {
      textModel: Model
      toolList: ToolInfo[]
    }
  ) => void
  onCancelChat?: () => void
}

const toolbarIconButtonClass =
  'touch-manipulation h-8 w-8 shrink-0 p-0'

const toolbarChipButtonClass =
  'touch-manipulation h-8 shrink-0 px-2 gap-0.5 whitespace-nowrap'

const ASPECT_RATIOS = ['auto', '1:1', '4:3', '3:4', '16:9', '9:16'] as const

function isInteractiveTarget(target: EventTarget | null) {
  if (!(target instanceof HTMLElement)) return false
  return Boolean(
    target.closest(
      'button, a, input, textarea, label, [role="menuitem"], [role="combobox"], [data-radix-popper-content-wrapper]'
    )
  )
}

const ChatTextarea: React.FC<ChatTextareaProps> = ({
  pending,
  className,
  messages,
  sessionId,
  autoSize = true,
  onSendMessages,
  onCancelChat,
}) => {
  const { t } = useTranslation()
  const isMobile = useIsMobile()
  const { authStatus, openAuthDialog } = useAuth()
  const { textModel, selectedTools, generationMode, setGenerationMode } =
    useConfigs()
  const { balance } = useBalance()
  const [prompt, setPrompt] = useState('')
  const [isComposing, setIsComposing] = useState(false)
  const textareaRef = useRef<TextAreaRef>(null)
  const [images, setImages] = useState<
    {
      file_id: string
      width: number
      height: number
    }[]
  >([])
  const [isFocused, setIsFocused] = useState(false)
  const [selectedAspectRatio, setSelectedAspectRatio] = useState<string>(() =>
    generationMode === 'image' ? '1:1' : '9:16'
  )
  const [quantity, setQuantity] = useState<number>(2)
  const [showQuantitySlider, setShowQuantitySlider] = useState(false)
  const [showAspectRatioPicker, setShowAspectRatioPicker] = useState(false)
  const [showRechargeDialog, setShowRechargeDialog] = useState(false)
  useWechatRechargeReturn(authStatus.is_logged_in, setShowRechargeDialog)

  const imageInputRef = useRef<HTMLInputElement>(null)

  // 充值按钮组件
  const RechargeContent = useCallback(() => (
    <div className="flex items-center justify-between gap-3">
      <span className="text-sm text-muted-foreground flex-1">
        {t('chat:insufficientBalanceDescription')}
      </span>
      <Button
        size="sm"
        variant="outline"
        className="shrink-0"
        onClick={() => setShowRechargeDialog(true)}
      >
        {t('common:auth.recharge')}
      </Button>
    </div>
  ), [t])

  const { mutate: uploadImageMutation } = useMutation({
    mutationFn: (file: File) => uploadImage(file),
    onSuccess: (data) => {
      console.log('🦄uploadImageMutation onSuccess', data)
      setImages((prev) => [
        ...prev,
        {
          file_id: data.file_id,
          width: data.width,
          height: data.height,
        },
      ])
    },
    onError: (error) => {
      console.error('🦄uploadImageMutation onError', error)
      toast.error('Failed to upload image', {
        description: <div>{error.toString()}</div>,
      })
    },
  })

  const handleImagesUpload = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files
      if (files) {
        for (const file of files) {
          uploadImageMutation(file)
        }
      }
    },
    [uploadImageMutation]
  )

  const handleCancelChat = useCallback(async () => {
    if (sessionId) {
      // 同时取消普通聊天和魔法生成任务
      await Promise.all([cancelChat(sessionId), cancelMagicGenerate(sessionId)])
    }
    onCancelChat?.()
  }, [sessionId, onCancelChat])

  const canSend = prompt.trim().length > 0 && !pending && !isComposing

  const modeTools = (selectedTools || []).filter(
    (tool) => tool.type === generationMode
  )

  const handleGenerationModeChange = useCallback(
    (mode: GenerationMode) => {
      if (mode === generationMode) return
      setGenerationMode(mode)
      // 切换模式时给出更符合场景的默认比例
      setSelectedAspectRatio(mode === 'image' ? '1:1' : '9:16')
    },
    [generationMode, setGenerationMode]
  )

  // Send Prompt
  const handleSendPrompt = useCallback(async () => {
    if (pending) return
    if (!authStatus.is_logged_in) {
      openAuthDialog()
      return
    }
    // 登录用户积分不足时拦截（视频 / 图片都会扣积分）
    const balanceNum = parseFloat(balance)
    if (generationMode === 'video' && balanceNum <= 0) {
      toast.error(t('chat:insufficientBalance'), {
        description: <RechargeContent />,
        duration: 10000,
      })
      return
    }
    if (generationMode === 'image' && balanceNum < quantity) {
      toast.error(t('chat:insufficientBalance'), {
        description: <RechargeContent />,
        duration: 10000,
      })
      return
    }
    if (!textModel) {
      toast.error(t('chat:textarea.selectModel'))
      return
    }
    if (modeTools.length === 0) {
      toast.warning(
        generationMode === 'image'
          ? t('chat:textarea.selectImageTool')
          : t('chat:textarea.selectVideoTool')
      )
    }
    let text_content: MessageContent[] | string = prompt
    if (prompt.length === 0 || prompt.trim() === '') {
      toast.error(t('chat:textarea.enterPrompt'))
      return
    }
    // 如非默认值，请添加宽高比和数量信息
    let additionalInfo = ''
    if (selectedAspectRatio !== 'auto') {
      additionalInfo += `<aspect_ratio>${selectedAspectRatio}</aspect_ratio>\n`
    }
    if (quantity !== 1) {
      additionalInfo += `<quantity>${quantity}</quantity>\n`
    }
    additionalInfo += `<generation_mode>${generationMode}</generation_mode>\n`
    if (additionalInfo) {
      text_content = text_content + '\n\n' + additionalInfo
    }
    if (images.length > 0) {
      text_content += `\n\n<input_images count="${images.length}">`
      images.forEach((image, index) => {
        text_content += `\n<image index="${index + 1}" file_id="${image.file_id}" width="${image.width}" height="${image.height}" />`
      })
      text_content += `\n</input_images>`
    }
    // 从服务器获取图片并转换为 base64 编码的 URL
    const imagePromises = images.map(async (image) => {
      const response = await fetch(`/api/file/${image.file_id}`)
      const blob = await response.blob()
      return new Promise<string>((resolve) => {
        const reader = new FileReader()
        reader.onloadend = () => resolve(reader.result as string)
        reader.readAsDataURL(blob)
      })
    })
    const base64Images = await Promise.all(imagePromises)
    const final_content = [
      {
        type: 'text',
        text: text_content as string,
      },
      ...images.map((image, index) => ({
        type: 'image_url',
        image_url: {
          url: base64Images[index],
        },
      })),
    ] as MessageContent[]
    const newMessage = messages.concat([
      {
        role: 'user',
        content: final_content,
      },
    ])
    setImages([])
    setPrompt('')
    onSendMessages(newMessage, {
      textModel: textModel,
      toolList: modeTools,
    })
  }, [
    pending,
    textModel,
    modeTools,
    prompt,
    onSendMessages,
    images,
    messages,
    t,
    selectedAspectRatio,
    quantity,
    generationMode,
    authStatus.is_logged_in,
    openAuthDialog,
    balance,
    RechargeContent,
  ])

  // Drop Area
  const dropAreaRef = useRef<HTMLDivElement>(null)
  const [isDragOver, setIsDragOver] = useState(false)

  const handleFilesDrop = useCallback(
    (files: File[]) => {
      for (const file of files) {
        uploadImageMutation(file)
      }
    },
    [uploadImageMutation]
  )

  useDrop(dropAreaRef, {
    onDragOver() {
      setIsDragOver(true)
    },
    onDragLeave() {
      setIsDragOver(false)
    },
    onDrop() {
      setIsDragOver(false)
    },
    onFiles: handleFilesDrop,
  })

  useEffect(() => {
    const handleAddImagesToChat = (data: TCanvasAddImagesToChatEvent) => {
      data.forEach(async (image) => {
        if (image.base64) {
          const file = dataURLToFile(image.base64, image.fileId)
          uploadImageMutation(file)
        } else {
          setImages(
            produce((prev) => {
              prev.push({
                file_id: image.fileId,
                width: image.width,
                height: image.height,
              })
            })
          )
        }
      })

      textareaRef.current?.focus()
    }

    const handleMaterialAddImagesToChat = async (
      data: TMaterialAddImagesToChatEvent
    ) => {
      data.forEach(async (image: TMaterialAddImagesToChatEvent[0]) => {
        // Convert file path to blob and upload
        try {
          const fileUrl = `/api/serve_file?file_path=${encodeURIComponent(image.filePath)}`
          const response = await fetch(fileUrl)
          const blob = await response.blob()
          const file = new File([blob], image.fileName, {
            type: `image/${image.fileType}`,
          })
          uploadImageMutation(file)
        } catch (error) {
          console.error('Failed to load image from material:', error)
          toast.error('Failed to load image from material', {
            description: `${error}`,
          })
        }
      })

      textareaRef.current?.focus()
    }

    eventBus.on('Canvas::AddImagesToChat', handleAddImagesToChat)
    eventBus.on('Material::AddImagesToChat', handleMaterialAddImagesToChat)
    return () => {
      eventBus.off('Canvas::AddImagesToChat', handleAddImagesToChat)
      eventBus.off('Material::AddImagesToChat', handleMaterialAddImagesToChat)
    }
  }, [uploadImageMutation])

  const renderQuantityPanelDesktop = () => (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">
          {t('chat:textarea.quantity', '生成数量')}
        </span>
        <span className="text-sm text-muted-foreground tabular-nums">
          {quantity}
          {t('chat:textarea.quantityUnit', '个')}
        </span>
      </div>
      <div className="flex gap-2">
        {[1, 2].map((value) => (
          <Button
            key={value}
            type="button"
            variant={quantity === value ? 'default' : 'outline'}
            className="h-8 flex-1"
            onClick={() => setQuantity(value)}
          >
            {value}
          </Button>
        ))}
      </div>
    </div>
  )

  const renderQuantityPanelMobile = () => (
    <div className="grid grid-cols-2 gap-2.5 pb-1">
      {[1, 2].map((value) => (
        <Button
          key={value}
          type="button"
          variant={quantity === value ? 'default' : 'outline'}
          className="h-11 text-sm touch-manipulation"
          onClick={() => {
            setQuantity(value)
            setShowQuantitySlider(false)
          }}
        >
          {value} {t('chat:textarea.quantityUnit', '个')}
        </Button>
      ))}
    </div>
  )

  return (
    <motion.div
      ref={dropAreaRef}
      className={cn(
        'w-full flex flex-col items-center border border-primary/20 rounded-2xl p-2.5 sm:p-3 hover:border-primary/40 transition-all duration-300 cursor-text gap-2.5 sm:gap-5 bg-background/80 backdrop-blur-xl relative',
        isFocused && 'border-primary/40',
        className
      )}
      style={{
        boxShadow: isFocused
          ? '0 0 0 4px color-mix(in oklab, var(--primary) 10%, transparent)'
          : 'none',
      }}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3, ease: 'linear' }}
      onClick={(e) => {
        if (isInteractiveTarget(e.target)) return
        textareaRef.current?.focus()
      }}
    >
      <AnimatePresence>
        {isDragOver && (
          <motion.div
            className="absolute top-0 left-0 right-0 bottom-0 bg-background/50 backdrop-blur-xl rounded-2xl z-10"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2, ease: 'easeInOut' }}
          >
            <div className="flex items-center justify-center h-full">
              <p className="text-sm text-muted-foreground">
                Drop images here to upload
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {images.length > 0 && (
          <motion.div
            className="flex items-center gap-2 w-full"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2, ease: 'easeInOut' }}
          >
            {images.map((image) => (
              <motion.div
                key={image.file_id}
                className="relative size-10"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                transition={{ duration: 0.2, ease: 'easeInOut' }}
              >
                <img
                  key={image.file_id}
                  src={`/api/file/${image.file_id}`}
                  alt="Uploaded image"
                  className="w-full h-full object-cover rounded-md"
                  draggable={false}
                />
                <Button
                  variant="secondary"
                  size="icon"
                  className="absolute -top-1 -right-1 size-4"
                  onClick={() =>
                    setImages((prev) =>
                      prev.filter((i) => i.file_id !== image.file_id)
                    )
                  }
                >
                  <XIcon className="size-3" />
                </Button>
              </motion.div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      <Textarea
        ref={textareaRef}
        className="w-full h-full border-none outline-none resize-none"
        placeholder={
          generationMode === 'image'
            ? t('chat:textarea.placeholderImage')
            : t('chat:textarea.placeholderVideo')
        }
        value={prompt}
        autoSize={autoSize}
        onChange={(e) => setPrompt(e.target.value)}
        onCompositionStart={() => setIsComposing(true)}
        onCompositionEnd={(e) => {
          setIsComposing(false)
          setPrompt(e.currentTarget.value)
        }}
        onFocus={() => setIsFocused(true)}
        onBlur={() => setIsFocused(false)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            handleSendPrompt()
          }
        }}
      />

      <div
        className="flex items-center justify-between gap-1.5 w-full min-w-0 touch-manipulation shrink-0"
        onPointerDown={(e) => e.stopPropagation()}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-1.5 min-w-0 flex-1 flex-nowrap overflow-x-auto [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          <div
            className="inline-flex h-8 shrink-0 items-center rounded-lg border border-border bg-muted/60 p-0.5"
            role="tablist"
            aria-label={t('chat:textarea.generationMode', '生成模式')}
          >
            <button
              type="button"
              role="tab"
              aria-selected={generationMode === 'image'}
              className={cn(
                'inline-flex h-7 items-center gap-1 rounded-md px-2 text-xs font-medium transition-colors touch-manipulation',
                generationMode === 'image'
                  ? 'bg-background text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              )}
              onClick={() => handleGenerationModeChange('image')}
            >
              <ImageIcon className="size-3.5 shrink-0" />
              <span>{t('chat:textarea.modeImage', '生图片')}</span>
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={generationMode === 'video'}
              className={cn(
                'inline-flex h-7 items-center gap-1 rounded-md px-2 text-xs font-medium transition-colors touch-manipulation',
                generationMode === 'video'
                  ? 'bg-background text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              )}
              onClick={() => handleGenerationModeChange('video')}
            >
              <Clapperboard className="size-3.5 shrink-0" />
              <span>{t('chat:textarea.modeVideo', '生视频')}</span>
            </button>
          </div>

          <input
            ref={imageInputRef}
            type="file"
            accept="image/*"
            multiple
            onChange={handleImagesUpload}
            hidden
          />
          <Button
            variant="outline"
            size="sm"
            className={toolbarIconButtonClass}
            onClick={() => imageInputRef.current?.click()}
          >
            <PlusIcon className="size-4" />
          </Button>

          {!isMobile && <ModelSelectorV3 />}

          {/* Aspect Ratio Selector */}
          {isMobile ? (
            <Button
              variant="outline"
              className={cn('inline-flex items-center', toolbarChipButtonClass)}
              size="sm"
              onClick={() => setShowAspectRatioPicker(true)}
            >
              <RectangleVertical className="size-3.5 shrink-0" />
              <span className="text-xs leading-none">{selectedAspectRatio}</span>
              <ChevronDown className="size-3 shrink-0 opacity-50" />
            </Button>
          ) : (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="outline"
                  className={cn('inline-flex items-center gap-1', toolbarChipButtonClass)}
                  size="sm"
                >
                  <RectangleVertical className="size-4 shrink-0" />
                  <span className="text-sm">{selectedAspectRatio}</span>
                  <ChevronDown className="size-3 opacity-50" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" className="w-32">
                {ASPECT_RATIOS.map((ratio) => (
                  <DropdownMenuItem
                    key={ratio}
                    onSelect={() => setSelectedAspectRatio(ratio)}
                    className="flex items-center justify-between"
                  >
                    <span>{ratio}</span>
                    {selectedAspectRatio === ratio && (
                      <div className="size-2 rounded-full bg-primary" />
                    )}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          )}

          {/* Quantity Selector：桌面用 Portal 下拉，避免被输入框 / overflow 父级遮挡 */}
          {isMobile ? (
            <Button
              variant="outline"
              className={cn('inline-flex items-center', toolbarChipButtonClass)}
              onClick={() => setShowQuantitySlider(true)}
              size="sm"
              title={t('chat:textarea.quantity', '生成数量')}
            >
              <span className="text-xs leading-none tabular-nums">
                {quantity}
                {t('chat:textarea.quantityUnit', '个')}
              </span>
              <ChevronDown className="size-3 shrink-0 opacity-50" />
            </Button>
          ) : (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="outline"
                  className={cn('inline-flex items-center', toolbarChipButtonClass)}
                  size="sm"
                  title={t('chat:textarea.quantity', '生成数量')}
                >
                  <span className="text-xs leading-none tabular-nums">
                    {quantity}
                    {t('chat:textarea.quantityUnit', '个')}
                  </span>
                  <ChevronDown className="size-3 shrink-0 opacity-50" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                align="start"
                side="top"
                sideOffset={8}
                className="z-[200] min-w-52 p-4"
                onCloseAutoFocus={(e) => e.preventDefault()}
              >
                {renderQuantityPanelDesktop()}
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </div>

        {
          pending ? (
            <Button
              className="shrink-0 relative touch-manipulation h-8 w-8 sm:h-9 sm:w-9"
              variant="default"
              size="icon"
              onClick={handleCancelChat}
            >
              <Loader2 className="size-5.5 animate-spin absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2" />
              <Square className="size-2 absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2" />
            </Button>
          ) : (
            <Button
              className="shrink-0 touch-manipulation h-8 w-8 sm:h-9 sm:w-9"
              variant="default"
              size="icon"
              onClick={handleSendPrompt}
              disabled={!canSend}
            >
              <ArrowUp className="size-4" />
            </Button>
          )
        }
      </div>

      {isMobile && (
        <>
          <MobileBottomSheet
            open={showAspectRatioPicker}
            onOpenChange={setShowAspectRatioPicker}
            title={t('chat:textarea.aspectRatio', '生成比例')}
          >
            <div className="grid grid-cols-3 gap-2.5 pb-1">
              {ASPECT_RATIOS.map((ratio) => (
                <Button
                  key={ratio}
                  type="button"
                  variant={selectedAspectRatio === ratio ? 'default' : 'outline'}
                  className="h-11 text-sm touch-manipulation"
                  onClick={() => {
                    setSelectedAspectRatio(ratio)
                    setShowAspectRatioPicker(false)
                  }}
                >
                  {ratio}
                </Button>
              ))}
            </div>
          </MobileBottomSheet>
          <MobileBottomSheet
            open={showQuantitySlider}
            onOpenChange={setShowQuantitySlider}
            title={t('chat:textarea.quantity', '生成数量')}
          >
            {renderQuantityPanelMobile()}
          </MobileBottomSheet>
        </>
      )}
      <RechargeDialog
        open={showRechargeDialog}
        onOpenChange={setShowRechargeDialog}
      />
    </motion.div >
  )
}

export default ChatTextarea
