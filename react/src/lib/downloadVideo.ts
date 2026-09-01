import { isWeChatBrowser, resolveMediaUrl } from '@/lib/resolveMediaUrl'

function extractFilename(src: string, title?: string): string {
  if (title?.trim()) {
    const cleaned = title.replace(/^video_id:\s*/i, '').trim()
    if (cleaned && cleaned.includes('.')) {
      return cleaned
    }
  }
  const match = src.match(/\/([^/?#]+\.mp4)/i)
  return match?.[1] ?? 'video.mp4'
}

function withDownloadParam(url: string): string {
  const separator = url.includes('?') ? '&' : '?'
  return `${url}${separator}download=1`
}

function withPlayerParam(url: string): string {
  const separator = url.includes('?') ? '&' : '?'
  return `${url}${separator}player=1`
}

function isIOS(): boolean {
  return /iPhone|iPad|iPod/i.test(navigator.userAgent)
}

function isMobileBrowser(): boolean {
  return (
    isIOS() ||
    /Android|webOS|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent)
  )
}

async function fetchVideoBlob(url: string, timeoutMs = 45000): Promise<Blob> {
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), timeoutMs)
  try {
    const response = await fetch(url, {
      credentials: 'same-origin',
      signal: controller.signal,
    })
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }
    return await response.blob()
  } finally {
    window.clearTimeout(timer)
  }
}

async function tryMobileShare(blob: Blob, filename: string): Promise<boolean> {
  if (!navigator.share) {
    return false
  }

  const file = new File([blob], filename, {
    type: blob.type || 'video/mp4',
  })

  if (navigator.canShare && !navigator.canShare({ files: [file] })) {
    return false
  }

  await navigator.share({ files: [file], title: filename })
  return true
}

function triggerUrlDownload(url: string, filename: string): void {
  const anchor = document.createElement('a')
  anchor.href = withDownloadParam(url)
  anchor.download = filename
  anchor.rel = 'noopener'
  // 不要 target=_blank：手机上容易开空白页，看起来像「打不开」
  anchor.style.display = 'none'
  document.body.appendChild(anchor)
  anchor.click()
  document.body.removeChild(anchor)
}

/** 免登录播放页，可播可下，不依赖聊天登录态 */
export function getVideoPlayerUrl(src: string): string {
  return withPlayerParam(resolveMediaUrl(src))
}

/** 打开播放页（手机 / 微信优先走这里，保证能看到画面） */
export function openVideoDirectly(src: string): void {
  window.location.href = getVideoPlayerUrl(src)
}

export type DownloadVideoResult = 'opened-player' | 'shared' | 'downloaded'

/**
 * 保存视频：
 * - 微信 / 手机浏览器 → 打开可播放页（页内可下载）
 * - 桌面 → 直接附件下载
 * - iOS 桌面外再尝试系统分享
 */
export async function downloadVideoFile(
  src: string,
  title?: string
): Promise<DownloadVideoResult> {
  const url = resolveMediaUrl(src)
  const filename = extractFilename(src, title)

  // 微信、手机：先打开能播的页面，避免「下载了但看不到」
  if (isWeChatBrowser() || isMobileBrowser()) {
    openVideoDirectly(src)
    return 'opened-player'
  }

  triggerUrlDownload(url, filename)

  // 桌面 Safari 等再尝试分享（通常不可用，忽略即可）
  if (isIOS()) {
    try {
      const blob = await fetchVideoBlob(url)
      const shared = await tryMobileShare(blob, filename)
      if (shared) return 'shared'
    } catch {
      // ignore
    }
  }

  return 'downloaded'
}
