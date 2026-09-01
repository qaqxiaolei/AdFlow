import { eventBus, TEvents } from '@/lib/event'
import { Loader2 } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

/** 匹配「已等待 N 秒」，兼容全角/半角括号与省略号 */
const WAITING_ELAPSED_PATTERN = /已等待\s*(\d+)\s*秒/
/** 去掉面向用户的内部状态字段，如（状态: running） */
const INTERNAL_STATUS_PATTERN = /[（(]\s*状态\s*:?\s*[^）)]+[）)]/g
const VIDEO_GENERATING_HINT =
  /视频生成|正在提交|正在下载|等待提交|generation|generate_video/i

function parseWaitingElapsed(text: string): number | null {
  const match = text.match(WAITING_ELAPSED_PATTERN)
  return match ? parseInt(match[1], 10) : null
}

function stripInternalDetails(text: string): string {
  return text.replace(INTERNAL_STATUS_PATTERN, '').replace(/\s+/g, ' ').trim()
}

function isVideoGeneratingProgress(text: string): boolean {
  return VIDEO_GENERATING_HINT.test(text) || WAITING_ELAPSED_PATTERN.test(text)
}

function VideoProgressCard({ elapsedSeconds }: { elapsedSeconds: number }) {
  return (
    <div className="w-full overflow-hidden rounded-xl border border-violet-200/70 bg-gradient-to-r from-violet-50 via-purple-50 to-violet-50 shadow-sm dark:border-violet-800/50 dark:from-violet-950/50 dark:via-purple-950/40 dark:to-violet-950/50">
      <div className="flex items-center gap-2.5 px-3.5 py-2.5">
        <Loader2 className="size-4 shrink-0 animate-spin text-violet-600 dark:text-violet-400" />
        <p className="min-w-0 flex-1 text-sm leading-snug text-violet-900/90 dark:text-violet-100/90">
          视频生成中
          <span className="ml-1.5 tabular-nums font-medium text-violet-600 dark:text-violet-300">
            （已等待 {elapsedSeconds} 秒）
          </span>
        </p>
      </div>
      <div className="relative h-1 overflow-hidden bg-violet-100/80 dark:bg-violet-900/40">
        <div className="toolcall-progress-indeterminate absolute inset-y-0 w-2/5 rounded-full bg-gradient-to-r from-transparent via-violet-400 to-transparent dark:via-violet-500" />
      </div>
    </div>
  )
}

export default function ToolcallProgressUpdate({
  sessionId,
  initialProgress = '',
}: {
  sessionId: string
  initialProgress?: string
}) {
  const [rawProgress, setRawProgress] = useState(initialProgress)
  const [elapsedSeconds, setElapsedSeconds] = useState<number | null>(null)
  const waitStartedAtRef = useRef<number | null>(null)

  useEffect(() => {
    if (!initialProgress.trim()) return
    setRawProgress((prev) => {
      // 恢复/开始通知不要覆盖已经在走的「已等待」
      if (
        parseWaitingElapsed(prev) !== null &&
        parseWaitingElapsed(initialProgress) === null
      ) {
        return prev
      }
      return initialProgress
    })
  }, [initialProgress])

  useEffect(() => {
    const handleToolCallProgress = (
      data: TEvents['Socket::Session::ToolCallProgress']
    ) => {
      if (data.session_id !== sessionId) return
      const update = typeof data.update === 'string' ? data.update : ''
      // 空进度只是某一步结束，整次生成可能还在跑，不能拆掉计时条
      if (!update.trim()) return
      setRawProgress(update)
    }

    eventBus.on('Socket::Session::ToolCallProgress', handleToolCallProgress)
    return () => {
      eventBus.off('Socket::Session::ToolCallProgress', handleToolCallProgress)
    }
  }, [sessionId])

  useEffect(() => {
    const cleaned = stripInternalDetails(rawProgress)
    if (!cleaned || !isVideoGeneratingProgress(cleaned)) {
      return
    }

    const serverElapsed = parseWaitingElapsed(cleaned)
    if (waitStartedAtRef.current === null) {
      waitStartedAtRef.current =
        Date.now() - (serverElapsed ?? 0) * 1000
    } else if (serverElapsed !== null) {
      const localElapsed = Math.floor(
        (Date.now() - waitStartedAtRef.current) / 1000
      )
      // 只允许服务端把时间往前校准，禁止往回跳或清零
      if (serverElapsed > localElapsed) {
        waitStartedAtRef.current = Date.now() - serverElapsed * 1000
      }
    }

    const tick = () => {
      if (waitStartedAtRef.current === null) return
      const elapsed = Math.max(
        0,
        Math.floor((Date.now() - waitStartedAtRef.current) / 1000)
      )
      setElapsedSeconds(elapsed)
    }

    tick()
    const timer = window.setInterval(tick, 1000)
    return () => window.clearInterval(timer)
  }, [rawProgress])

  const plain = stripInternalDetails(rawProgress)
  const displayElapsed =
    elapsedSeconds ?? parseWaitingElapsed(plain) ?? 0

  if (displayElapsed > 0 || isVideoGeneratingProgress(plain)) {
    return <VideoProgressCard elapsedSeconds={displayElapsed} />
  }

  if (!plain) return null

  return (
    <div className="w-full overflow-hidden rounded-xl border border-violet-200/70 bg-gradient-to-r from-violet-50 via-purple-50 to-violet-50 shadow-sm dark:border-violet-800/50 dark:from-violet-950/50 dark:via-purple-950/40 dark:to-violet-950/50">
      <div className="flex items-center gap-2.5 px-3.5 py-2.5">
        <Loader2 className="size-4 shrink-0 animate-spin text-violet-600 dark:text-violet-400" />
        <p className="min-w-0 flex-1 text-sm leading-snug text-violet-900/90 dark:text-violet-100/90">
          {plain}
        </p>
      </div>
    </div>
  )
}
