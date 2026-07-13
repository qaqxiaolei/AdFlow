import { Button } from '@/components/ui/button'
import { downloadVideoFile } from '@/lib/downloadVideo'
import { cn } from '@/lib/utils'
import { Download, Loader2 } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'

type ChatVideoProps = {
  src: string
  title?: string
  className?: string
}

export default function ChatVideo({ src, title, className }: ChatVideoProps) {
  const { t } = useTranslation()
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

  return (
    <span
      className={cn(
        'group block relative overflow-hidden rounded-md my-2 last:mb-4',
        className
      )}
    >
      <video
        className="w-full max-w-full h-auto rounded-md bg-black"
        controls
        preload="metadata"
        playsInline
        src={src}
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
