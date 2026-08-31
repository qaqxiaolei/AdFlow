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

async function fetchVideoBlob(url: string): Promise<Blob> {
  const response = await fetch(withDownloadParam(url), {
    credentials: 'same-origin',
  })
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`)
  }
  return response.blob()
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

function triggerBlobDownload(blob: Blob, filename: string): void {
  const objectUrl = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = objectUrl
  anchor.download = filename
  anchor.rel = 'noopener'
  anchor.style.display = 'none'
  document.body.appendChild(anchor)
  anchor.click()
  document.body.removeChild(anchor)
  URL.revokeObjectURL(objectUrl)
}

/** 微信内直接打开 mp4，系统播放器里可长按保存 */
export function openVideoDirectly(src: string): void {
  const url = withDownloadParam(resolveMediaUrl(src))
  window.location.href = url
}

/** 下载或保存聊天中的生成视频，兼容 iOS / Android / 微信 */
export async function downloadVideoFile(
  src: string,
  title?: string
): Promise<void> {
  const url = resolveMediaUrl(src)
  const filename = extractFilename(src, title)

  // 微信里 blob 下载常失效，优先走系统播放器
  if (isWeChatBrowser()) {
    openVideoDirectly(src)
    return
  }

  const blob = await fetchVideoBlob(url)

  try {
    const shared = await tryMobileShare(blob, filename)
    if (shared) {
      return
    }
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      return
    }
  }

  triggerBlobDownload(blob, filename)
}
