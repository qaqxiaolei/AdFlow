import { Button } from '@/components/ui/button'
import { downloadVideoFile } from '@/lib/downloadVideo'
import { cn } from '@/lib/utils'
import { Download, Loader2 } from 'lucide-react'
import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'

type ChatVideoProps = {
  src: string
  title?: string
  className?: string
}

async function enterFullscreenAndPlay(video: HTMLVideoElement) {
  const anyVideo = video as HTMLVideoElement & {
    webkitEnterFullscreen?: () => void
    webkitRequestFullscreen?: () => Promise<void> | void
  }

  try {
    if (document.fullscreenElement !== video) {
      if (typeof video.requestFullscreen === 'function') {
        await video.requestFullscreen()
      } else if (typeof anyVideo.webkitRequestFullscreen === 'function') {
        await anyVideo.webkitRequestFullscreen()
      } else if (typeof anyVideo.webkitEnterFullscreen === 'function') {
        anyVideo.webkitEnterFullscreen()
      }
    }
  } catch (error) {
    console.warn('Fullscreen request failed:', error)
  }

  try {
    await video.play()
  } catch (error) {
    console.warn('Video play failed:', error)
  }
}

export default function ChatVideo({ src, title, className }: ChatVideoProps) {
  const { t } = useTranslation()
  const videoRef = useRef<HTMLVideoElement>(null)
  const [downloading, setDownloading] = useState(false)

  const handleDownload = async (event: React.MouseEvent) => {
    event.preventDefault()
    event.stopPropagation()
    if (downloading) {
      return
    }

    setDownloading(true)
    try {
      await downloadVideoFile(src, title)
    } catch (error) {
      console.error('Video download failed:', error)
      toast.error(t('chat:messages.videoDownloadFailed'))
    } finally {
      setDownloading(false)
    }
  }

  const handleVideoClick = async (event: React.MouseEvent<HTMLVideoElement>) => {
    // Keep native control clicks (timeline, volume, etc.) working as usual.
    const video = videoRef.current
    if (!video) return

    const rect = video.getBoundingClientRect()
    const controlsReserve = 44
    const clickedInControls =
      event.clientY > rect.bottom - controlsReserve

    if (clickedInControls) return

    event.preventDefault()
    await enterFullscreenAndPlay(video)
  }

  return (
    <span
      className={cn(
        'group block relative overflow-hidden rounded-md my-2 last:mb-4',
        className
      )}
    >
      <video
        ref={videoRef}
        className="w-full max-w-full h-auto rounded-md bg-black cursor-pointer"
        controls
        preload="metadata"
        playsInline
        src={src}
        onClick={handleVideoClick}
        {...(title ? { title } : {})}
      >
        Your browser does not support the video tag.
      </video>

      <Button
        type="button"
        size="sm"
        variant="secondary"
        disabled={downloading}
        onClick={handleDownload}
        className={cn(
          'absolute top-2 right-2 z-10 h-9 gap-1.5 px-3 shadow-md',
          'opacity-100 sm:opacity-0 sm:group-hover:opacity-100 sm:group-focus-within:opacity-100',
          'transition-opacity touch-manipulation'
        )}
        aria-label={t('chat:messages.videoDownload')}
      >
        {downloading ? (
          <Loader2 className="size-4 animate-spin" />
        ) : (
          <Download className="size-4" />
        )}
        <span className="text-xs font-medium sm:hidden">
          {t('chat:messages.videoDownload')}
        </span>
      </Button>
    </span>
  )
}
