import { createCanvas } from '@/api/canvas'
import ChatTextarea from '@/components/chat/ChatTextarea'
import CanvasList from '@/components/home/CanvasList'
import { ScrollArea } from '@/components/ui/scroll-area'
import { useConfigs } from '@/contexts/configs'
import { DEFAULT_SYSTEM_PROMPT } from '@/constants'
import { useMutation } from '@tanstack/react-query'
import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { motion } from 'motion/react'
import { nanoid } from 'nanoid'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import TopMenu from '@/components/TopMenu'

const BACKGROUND_VIDEOS = [
  '/backgroudVideo1.mp4',
  '/backgroudVideo2.mp4',
  '/backgroudVideo3.mp4',
] as const

/** 全屏纵向渐变：上浅下深（fixed 铺满视口，不随内容切断） */
const HOME_GRADIENT =
  'linear-gradient(180deg, #c5e85a 0%, #8fcf45 35%, #4db348 70%, #2a9340 100%)'

export const Route = createFileRoute('/')({
  component: Home,
})

function Home() {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const { setInitCanvas } = useConfigs()
  const [activeVideo, setActiveVideo] = useState(0)
  /** 仅当视频真正开始播放时才显示，避免微信露出大播放按钮 */
  const [playingVisible, setPlayingVisible] = useState(false)
  const videoRefs = useRef<(HTMLVideoElement | null)[]>([])
  const { mutate: createCanvasMutation, isPending } = useMutation({
    mutationFn: createCanvas,
    onSuccess: (data, variables) => {
      setInitCanvas(true)
      navigate({
        to: '/canvas/$id',
        params: { id: data.id },
        search: {
          sessionId: variables.session_id,
        },
      })
    },
    onError: (error) => {
      toast.error(t('common:messages.error'), {
        description: error.message,
      })
    },
  })

  const prepareVideo = (video: HTMLVideoElement) => {
    video.muted = true
    video.defaultMuted = true
    video.playsInline = true
    video.setAttribute('muted', '')
    video.setAttribute('playsinline', '')
    video.setAttribute('webkit-playsinline', 'true')
    video.setAttribute('x5-playsinline', 'true')
    video.setAttribute('x5-video-player-type', 'h5')
    video.setAttribute('x5-video-player-fullscreen', 'false')
  }

  const tryPlay = (video: HTMLVideoElement) => {
    prepareVideo(video)
    const playPromise = video.play()
    if (playPromise && typeof playPromise.then === 'function') {
      playPromise
        .then(() => setPlayingVisible(true))
        .catch(() => setPlayingVisible(false))
    }
  }

  useEffect(() => {
    videoRefs.current.forEach((video, index) => {
      if (!video) return
      prepareVideo(video)
      if (index === activeVideo) {
        tryPlay(video)
      } else {
        video.pause()
        try {
          video.currentTime = 0
        } catch {
          // ignore
        }
      }
    })
  }, [activeVideo])

  useEffect(() => {
    const resume = () => {
      const video = videoRefs.current[activeVideo]
      if (video && video.paused) tryPlay(video)
    }
    document.addEventListener('touchstart', resume, { once: true, passive: true })
    document.addEventListener('click', resume, { once: true })
    return () => {
      document.removeEventListener('touchstart', resume)
      document.removeEventListener('click', resume)
    }
  }, [activeVideo])

  return (
    <div className="relative flex flex-col h-dvh min-h-0 overflow-hidden bg-background">
      {/* 全屏固定渐变：70% 不透明度，避免过深 */}
      <div
        className="pointer-events-none fixed inset-0 z-0 opacity-70"
        style={{ background: HOME_GRADIENT }}
        aria-hidden
      />

      <ScrollArea className="relative z-10 h-full bg-transparent [&_[data-slot=scroll-area-viewport]]:bg-transparent">
        {/* 上方：仅视频（渐变在更底层，不裁切） */}
        <div className="relative overflow-hidden">
          <div
            className="absolute inset-0 pointer-events-none home-hero-video-mask"
            aria-hidden
          >
            {BACKGROUND_VIDEOS.map((src, index) => (
              <video
                key={src}
                ref={(el) => {
                  videoRefs.current[index] = el
                }}
                className={`home-bg-video absolute inset-0 h-full w-full object-cover transition-opacity duration-700 ${index === activeVideo && playingVisible
                  ? 'opacity-75'
                  : 'opacity-0'
                  }`}
                src={src}
                muted
                autoPlay
                playsInline
                preload="metadata"
                controls={false}
                disablePictureInPicture
                disableRemotePlayback
                onPlaying={() => {
                  if (index === activeVideo) setPlayingVisible(true)
                }}
                onError={() => {
                  if (index === activeVideo) setPlayingVisible(false)
                }}
                onEnded={() => {
                  setPlayingVisible(false)
                  setActiveVideo(
                    (current) => (current + 1) % BACKGROUND_VIDEOS.length
                  )
                }}
              />
            ))}
          </div>

          <TopMenu />

          <div className="relative z-10 flex flex-col items-center justify-center h-fit min-h-[42vh] sm:min-h-[calc(100vh-420px)] pt-8 sm:pt-[60px] px-4 w-full pb-8">
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
            >
              <h1 className="text-3xl sm:text-4xl lg:text-5xl font-bold mb-2 mt-4 sm:mt-8 text-center text-white drop-shadow-sm">
                {t('home:title')}
              </h1>
            </motion.div>
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
            >
              <p className="text-base sm:text-xl text-white/90 mb-6 sm:mb-8 text-center px-2">
                {t('home:subtitle')}
              </p>
            </motion.div>

            <ChatTextarea
              className="w-full max-w-xl"
              messages={[]}
              onSendMessages={(messages, configs) => {
                createCanvasMutation({
                  name: t('home:newCanvas'),
                  canvas_id: nanoid(),
                  messages: messages,
                  session_id: nanoid(),
                  text_model: configs.textModel,
                  tool_list: configs.toolList,
                  system_prompt:
                    localStorage.getItem('system_prompt') ||
                    DEFAULT_SYSTEM_PROMPT,
                })
              }}
              pending={isPending}
            />
          </div>
        </div>

        {/* 下方：最近项目（透明，透出同一层全屏渐变） */}
        <div className="relative z-10 bg-transparent">
          <CanvasList />
        </div>
      </ScrollArea>
    </div>
  )
}