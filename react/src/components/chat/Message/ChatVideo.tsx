import { Button } from '@/components/ui/button'
import { downloadVideoFile, openVideoDirectly } from '@/lib/downloadVideo'
import {
  isWeChatBrowser,
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
  video.setAttribute('preload', 'metadata')
}

export default function ChatVideo({ src, title, className }: ChatVideoProps) {
  const { t } = useTranslation()
  const videoRef = useRef<HTMLVideoElement>(null)
  const playWatchRef = useRef<number | null>(null)
  const inWeChat = isWeChatBrowser()
  const avoidInline = shouldAvoidInlineVideo()
  const [downloading, setDownloading] = useState(false)
  const [started, setStarted] = useState(false)
  const [frameVisible, setFrameVisible] = useState(false)
  const [hasError, setHasError] = useState(false)
  const [posterOk, setPosterOk] = useState(true)
  const [checking, setChecking] = useState(() => !shouldAvoidInlineVideo())

  const playbackSrc = useMemo(() => toPlaybackUrl(src), [src])
  const videoUrl = useMemo(() => resolveMediaUrl(playbackSrc), [playbackSrc])
  const poster = useMemo(() => resolveMediaUrl(toPosterUrl(src)), [src])
  const showPoster = posterOk && poster !== videoUrl && !frameVisible
  const showPlayOverlay = !hasError && !started && !checking

  useEffect(() => {
    if (avoidInline) {
      setChecking(false)
      setHasError(false)
      return
    }

    let cancelled = false
    setChecking(true)
    setHasError(false)

    fetch(videoUrl, {
      method: 'GET',
      headers: { Range: 'bytes=0-0' },
      credentials: 'same-origin',
    })
      .then((res) => {
        if (cancelled) return
        if (res.status === 404) setHasError(true)
      })
      .catch(() => {
        // 探测失败不代表文件不可播
      })
      .finally(() => {
        if (!cancelled) setChecking(false)
      })

    return () => {
      cancelled = true
    }
  }, [videoUrl, avoidInline])

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
    try {
      await downloadVideoFile(playbackSrc, title)
      if (inWeChat) {
        toast.message(t('chat:messages.wechatOpenHint', '已在微信中打开视频，可长按保存'))
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
      setDownloading(false)
    }
  }

  const handleOpenExternal = (event: React.MouseEvent) => {
    event.preventDefault()
    event.stopPropagation()
    openVideoDirectly(playbackSrc)
  }

  const handlePlay = async () => {
    if (hasError) return

    if (avoidInline) {
      openVideoDirectly(playbackSrc)
      return
    }

    const video = videoRef.current
    if (!video) return

    try {
      prepareVideoForMobile(video)
      if (video.readyState < HTMLMediaElement.HAVE_METADATA) {
        video.load()
      }
      await video.play()
      setStarted(true)

      clearPlayWatch()
      playWatchRef.current = window.setTimeout(() => {
        if (!frameVisible) {
          setHasError(true)
          toast.error(
            t('chat:messages.videoLoadFailed', '视频无法播放，请尝试在新窗口打开')
          )
        }
      }, 4000)
    } catch (error) {
      console.warn('Video play failed:', error)
      setHasError(true)
      toast.error(t('chat:messages.videoLoadFailed', '视频加载失败，请尝试保存后播放'))
    }
  }

  return (
    <span
      className={cn(
        'group relative block h-[220px] w-full overflow-hidden rounded-md my-2 last:mb-4 bg-zinc-800',
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
            frameVisible ? 'opacity-100' : 'opacity-0 pointer-events-none'
          )}
          controls={started}
          playsInline
          preload="metadata"
          poster={poster !== videoUrl ? poster : undefined}
          src={videoUrl}
          onTimeUpdate={() => {
            const video = videoRef.current
            if (video && video.currentTime > 0.05) {
              setFrameVisible(true)
              clearPlayWatch()
            }
          }}
          onPlay={() => setStarted(true)}
          onError={() => {
            clearPlayWatch()
            setHasError(true)
          }}
          {...(title ? { title } : {})}
        />
      )}

      {checking && (
        <div className="absolute inset-0 z-[3] flex items-center justify-center bg-zinc-800/80">
          <Loader2 className="size-8 animate-spin text-muted-foreground" />
        </div>
      )}

      {showPlayOverlay && (
        <button
          type="button"
          className="absolute inset-0 z-[4] flex flex-col items-center justify-center gap-2 touch-manipulation"
          onClick={(event) => {
            event.preventDefault()
            event.stopPropagation()
            void handlePlay()
          }}
          aria-label={t('chat:messages.tapToPlay', '点击播放视频')}
        >
          <span className="flex size-14 items-center justify-center rounded-full bg-black/55 shadow-lg">
            <Play className="size-7 fill-white text-white ml-0.5" />
          </span>
          <span className="text-xs font-medium text-white drop-shadow-sm px-3 text-center">
            {inWeChat
              ? t('chat:messages.wechatTapToPlay', '点击用系统播放器打开')
              : t('chat:messages.tapToPlay', '点击播放视频')}
          </span>
        </button>
      )}

      {hasError && (
        <div className="absolute inset-0 z-[5] flex flex-col items-center justify-center gap-3 bg-zinc-800 px-4 text-center text-sm text-muted-foreground">
          <p>{t('chat:messages.videoLoadFailed', '视频无法播放')}</p>
          <div className="flex flex-wrap items-center justify-center gap-2">
            <Button type="button" size="sm" variant="outline" onClick={handleDownload}>
              {t('chat:messages.videoDownload', '保存视频')}
            </Button>
            <Button type="button" size="sm" variant="secondary" onClick={handleOpenExternal}>
              <ExternalLink className="size-4 mr-1" />
              {t('chat:messages.openVideo', '新窗口打开')}
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
        className={cn(
          'absolute top-2 right-2 z-[6] h-9 gap-1.5 px-3 shadow-md',
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
