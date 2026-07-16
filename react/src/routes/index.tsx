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

export const Route = createFileRoute('/')({
  component: Home,
})

function Home() {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const { setInitCanvas } = useConfigs()
  const [activeVideo, setActiveVideo] = useState(0)
  const videoRefs = useRef<(HTMLVideoElement | null)[]>([])
  // useMutation 是 @tanstack/react-query 提供的异步提交接口专用钩子，专门处理「新增 / 修改 / 删除」这类会改变后端数据的请求（区别于 useQuery 查数据）
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

  useEffect(() => {
    videoRefs.current.forEach((video, index) => {
      if (!video) return
      if (index === activeVideo) {
        void video.play().catch(() => {})
      } else {
        video.pause()
        video.currentTime = 0
      }
    })
  }, [activeVideo])

  return (
    <div className='flex flex-col h-dvh min-h-0 overflow-hidden'>
      <ScrollArea className='h-full'>
        <div className='relative'>
          <div className='absolute inset-0 overflow-hidden pointer-events-none' aria-hidden>
            {BACKGROUND_VIDEOS.map((src, index) => (
              <video
                key={src}
                ref={(el) => {
                  videoRefs.current[index] = el
                }}
                className={`absolute inset-0 h-full w-full object-cover transition-opacity duration-1000 ${
                  index === activeVideo ? 'opacity-100' : 'opacity-0'
                }`}
                src={src}
                autoPlay={index === 0}
                muted
                playsInline
                onEnded={() => {
                  setActiveVideo((current) => (current + 1) % BACKGROUND_VIDEOS.length)
                }}
              />
            ))}
            <div className='absolute inset-0 bg-background/40' />
            <div className='absolute inset-x-0 bottom-0 h-24 bg-gradient-to-t from-background to-transparent' />
          </div>

          <TopMenu />

          <div className='relative z-10 flex flex-col items-center justify-center h-fit min-h-[50vh] sm:min-h-[calc(100vh-460px)] pt-8 sm:pt-[60px] px-4 w-full'>
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
            >
              <h1 className='text-3xl sm:text-4xl lg:text-5xl font-bold mb-2 mt-4 sm:mt-8 text-center'>{t('home:title')}</h1>
            </motion.div>
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
            >
              <p className='text-base sm:text-xl text-muted-foreground mb-6 sm:mb-8 text-center px-2'>{t('home:subtitle')}</p>
            </motion.div>

            <ChatTextarea
              className='w-full max-w-xl'
              messages={[]}
              onSendMessages={(messages, configs) => {
                createCanvasMutation({
                  name: t('home:newCanvas'),
                  canvas_id: nanoid(),
                  messages: messages,
                  session_id: nanoid(),
                  text_model: configs.textModel,
                  tool_list: configs.toolList,
                  system_prompt: localStorage.getItem('system_prompt') || DEFAULT_SYSTEM_PROMPT,
                })
              }}
              pending={isPending}
            />
          </div>
        </div>

        <CanvasList />
      </ScrollArea>
    </div>
  )
}
