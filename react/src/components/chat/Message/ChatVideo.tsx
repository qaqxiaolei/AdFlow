import { Button } from '@/components/ui/button'
import { downloadVideoFile, openVideoDirectly } from '@/lib/downloadVideo'
import {
  resolveMediaUrl,
  shouldAvoidInlineVideo,
} from '@/lib/resolveMediaUrl'
import { cn } from '@/lib/utils'
import { Download, ExternalLink, Loader2, Play } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'

type ChatVideoProps = {
  src: string
  title?: string
  className?: string
}

function isImageSrc(src: string): boolean {
  return /\.(jpe?g|png|webp)(\?|$)/i.test(src)
}

function toPosterUrl(src: string): string {
  if (isImageSrc(src)) return src
  const fromMp4 = src.replace(/\.mp4(\?.*)?$/i, '.jpg$1')
  if (fromMp4 !== src) return fromMp4
  const fileMatch = src.match(/(\/api\/file\/vi_[^/?#]+)/i)
  if (fileMatch) {
    const stem = fileMatch[1].replace(/\.[^.]+$/, '')
    return src.replace(fileMatch[1], `${stem}.jpg`)
  }
  return src
}

function toPlaybackUrl(src: string): string {
  if (isImageSrc(src)) {
    return src.replace(/\.(jpe?g|png|webp)(\?.*)?$/i, '.mp4$2')
  }
  return src
}

function prepareVideoForMobile(video: HTMLVideoElement) {
  video.playsInline = true
  video.setAttribute('playsinline', '')
  video.setAttribute('webkit-playsinline', 'true')
  video.setAttribute('x5-playsinline', 'true')
  video.setAttribute('x5-video-player-type', 'h5-page')
  video.setAttribute('x5-video-player-fullscreen', 'false')
  video.preload = 'metadata'
}

export default function ChatVideo({ src, title, className }: ChatVideoProps) {
  const { t } = useTranslation()
  const videoRef = useRef<HTMLVideoElement>(null)
  const playWatchRef = useRef<number | null>(null)
  const avoidInline = shouldAvoidInlineVideo()
  const playAttemptedRef = useRef(false)
  const [downloading, setDownloading] = useState(false)
  const [started, setStarted] = useState(false)
  const [buffering, setBuffering] = useState(false)
  const [frameVisible, setFrameVisible] = useState(false)
  const [hasError, setHasError] = useState(false)
  const [posterOk, setPosterOk] = useState(true)

  const playbackSrc = useMemo(() => toPlaybackUrl(src), [src])
  const videoUrl = useMemo(() => resolveMediaUrl(playbackSrc), [playbackSrc])
  const poster = useMemo(() => resolveMediaUrl(toPosterUrl(src)), [src])
  const showPoster = posterOk && poster !== videoUrl && !frameVisible
  const showPlayOverlay = !hasError && !started && !buffering

  useEffect(() => {
    if (avoidInline) return
    const video = videoRef.current
    if (video) prepareVideoForMobile(video)
  }, [videoUrl, avoidInline])

  useEffect(() => {
    return () => {
      if (playWatchRef.current) {
        window.clearTimeout(playWatchRef.current)
      }
    }
  }, [])

  const clearPlayWatch = () => {
    if (playWatchRef.current) {
      window.clearTimeout(playWatchRef.current)
      playWatchRef.current = null
    }
  }

  const handleDownload = async (event: React.MouseEvent) => {
    event.preventDefault()
    event.stopPropagation()
    if (downloading) return

    setDownloading(true)
    const stopLoading = window.setTimeout(() => setDownloading(false), 8000)
    try {
      const result = await downloadVideoFile(playbackSrc, title)
      if (result === 'downloaded') {
        toast.success(
          t('chat:messages.videoDownloadStarted', '已开始下载')
        )
      }
    } catch (error) {
      console.error('Video download failed:', error)
      toast.error(t('chat:messages.videoDownloadFailed'))
      try {
        openVideoDirectly(playbackSrc)
      } catch {
        // ignore
      }
    } finally {
      window.clearTimeout(stopLoading)
      setDownloading(false)
    }
  }

  const handleOpenExternal = (event: React.MouseEvent) => {
    event.preventDefault()
    event.stopPropagation()
    openVideoDirectly(playbackSrc)
  }

  const handlePlay = async () => {
    playAttemptedRef.current = true

    const video = videoRef.current
    if (!video || avoidInline) {
      // 无法内联时直接打开原始视频文件，不进自定义播放页
      openVideoDirectly(playbackSrc)
      return
    }

    setBuffering(true)
    setHasError(false)
    clearPlayWatch()
    playWatchRef.current = window.setTimeout(() => {
      const current = videoRef.current
      if (!current || current.currentTime < 0.05) {
        setBuffering(false)
        setHasError(true)
      }
    }, 45000)

    try {
      prepareVideoForMobile(video)
      if (video.readyState < HTMLMediaElement.HAVE_METADATA) {
        video.load()
      }
      video.muted = true
      await video.play()
      video.muted = false
      setStarted(true)
      setHasError(false)
    } catch (error) {
      console.warn('Video play failed:', error)
      clearPlayWatch()
      setStarted(false)
      setBuffering(false)
      setHasError(true)
    }
  }

  return (
    <div
      className={cn(
        'group relative my-2 w-full max-w-[240px] overflow-hidden rounded-xl',
        'aspect-[9/16] bg-gradient-to-b from-zinc-600 via-zinc-800 to-zinc-950',
        className
      )}
    >
      {showPoster && (
        <img
          src={poster}
          alt=""
          aria-hidden
          className="absolute inset-0 z-[1] h-full w-full object-cover pointer-events-none"
          onError={() => setPosterOk(false)}
        />
      )}

      {!avoidInline && (
        <video
          ref={videoRef}
          className={cn(
            'absolute inset-0 z-[2] h-full w-full object-cover bg-transparent',
            // 已开始播放就显示控件区域，不再一直 opacity-0 变成「打不开」
            started || frameVisible
              ? 'opacity-100'
              : 'opacity-0 pointer-events-none'
          )}
          controls={started}
          playsInline
          preload="metadata"
          poster={poster !== videoUrl ? poster : undefined}
          src={videoUrl}
          onWaiting={() => setBuffering(true)}
          onPlaying={() => {
            setBuffering(false)
            setStarted(true)
            setFrameVisible(true)
            clearPlayWatch()
          }}
          onTimeUpdate={() => {
            const video = videoRef.current
            if (video && video.currentTime > 0.05) {
              setFrameVisible(true)
              setBuffering(false)
              clearPlayWatch()
            }
          }}
          onPlay={() => {
            setStarted(true)
            setBuffering(false)
          }}
          onError={() => {
            clearPlayWatch()
            if (playAttemptedRef.current) {
              setBuffering(false)
              setHasError(true)
            }
          }}
          {...(title ? { title } : {})}
        />
      )}

      {buffering && (
        <div className="absolute inset-0 z-[3] flex flex-col items-center justify-center gap-2 bg-zinc-900/60">
          <Loader2 className="size-8 animate-spin text-white" />
          <span className="text-xs text-white/90">
            {t('chat:messages.videoBuffering', '视频加载中…')}
          </span>
        </div>
      )}

      {showPlayOverlay && (
        <button
          type="button"
          className="absolute inset-0 z-[4] flex flex-col items-center justify-center gap-3 touch-manipulation"
          onClick={(event) => {
            event.preventDefault()
            event.stopPropagation()
            void handlePlay()
          }}
          aria-label={t('chat:messages.tapToPlay', '点击播放视频')}
        >
          <span className="flex size-16 items-center justify-center rounded-full bg-white shadow-xl">
            <Play className="size-8 fill-zinc-900 text-zinc-900 ml-0.5" />
          </span>
          <span className="rounded-full bg-black/70 px-3 py-1 text-xs font-medium text-white">
            {t('chat:messages.tapToPlay', '点击播放视频')}
          </span>
        </button>
      )}

      {hasError && (
        <div className="absolute inset-0 z-[5] flex flex-col items-center justify-center gap-3 bg-zinc-900 px-4 text-center text-sm text-white">
          <p>{t('chat:messages.videoLoadFailed', '视频无法播放')}</p>
          <div className="flex flex-wrap items-center justify-center gap-2">
            <Button type="button" size="sm" variant="outline" onClick={handleDownload}>
              {t('chat:messages.videoDownload', '保存视频')}
            </Button>
            <Button type="button" size="sm" variant="secondary" onClick={handleOpenExternal}>
              <ExternalLink className="size-4 mr-1" />
              {t('chat:messages.openVideo', '打开视频')}
            </Button>
          </div>
        </div>
      )}

      <Button
        type="button"
        size="sm"
        variant="secondary"
        disabled={downloading}
        onClick={handleDownload}
        className="absolute top-2 right-2 z-[6] h-9 gap-1.5 px-3 shadow-md touch-manipulation"
        aria-label={t('chat:messages.videoDownload')}
      >
        {downloading ? (
          <Loader2 className="size-4 animate-spin" />
        ) : (
          <Download className="size-4" />
        )}
        <span className="text-xs font-medium">
          {t('chat:messages.videoDownload')}
        </span>
      </Button>
    </div>
  )
}
