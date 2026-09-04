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

function isIOS(): boolean {
  return /iPhone|iPad|iPod/i.test(navigator.userAgent)
}

/**
 * 尽量映射到本站 /api/file/xxx.mp4?download=1，
 * 由服务端返回 Content-Disposition: attachment，真正触发「下载」而不是打开播放。
 * OSS 公网地址也会回落到同源文件接口（服务器本地通常仍有副本）。
 */
function resolveAttachmentDownloadUrl(src: string): string | null {
  const resolved = resolveMediaUrl(src)
  const match = resolved.match(/\/([^/?#]+\.mp4)/i)
  if (!match) return null

  const filename = match[1]
  const isOurFile =
    resolved.includes('/api/file/') ||
    /aliyuncs\.com|\.oss-|agnes-ai\.space|agnes-aigc/i.test(resolved)

  if (!isOurFile && !resolved.startsWith(window.location.origin)) {
    return null
  }

  return `${window.location.origin}/api/file/${filename}?download=1`
}

function triggerAnchorDownload(url: string, filename: string): void {
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.rel = 'noopener'
  anchor.target = '_blank'
  anchor.style.display = 'none'
  document.body.appendChild(anchor)
  anchor.click()
  document.body.removeChild(anchor)
}

function triggerBlobDownload(blob: Blob, filename: string): void {
  const objectUrl = URL.createObjectURL(blob)
  try {
    triggerAnchorDownload(objectUrl, filename)
  } finally {
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 30_000)
  }
}

async function fetchVideoBlob(url: string, timeoutMs = 45000): Promise<Blob> {
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), timeoutMs)
  try {
    const response = await fetch(url, {
      credentials: url.startsWith(window.location.origin) ? 'same-origin' : 'omit',
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

/** 直接打开原始视频地址 */
export function openVideoDirectly(src: string): void {
  window.location.href = resolveMediaUrl(src)
}

export type DownloadVideoResult = 'downloaded' | 'opened-file'

/**
 * 保存视频：优先直接下载附件；仅在无法下载时才打开文件。
 */
export async function downloadVideoFile(
  src: string,
  title?: string
): Promise<DownloadVideoResult> {
  const filename = extractFilename(src, title)
  const attachmentUrl = resolveAttachmentDownloadUrl(src)
  const mediaUrl = resolveMediaUrl(src)

  // 微信 / iOS：用同源 attachment 地址跳转，系统会走下载/用其他应用打开
  if (attachmentUrl && (isWeChatBrowser() || isIOS())) {
    window.location.href = attachmentUrl
    return 'downloaded'
  }

  // 桌面 / Android：a[download] 触发保存
  if (attachmentUrl) {
    triggerAnchorDownload(attachmentUrl, filename)
    return 'downloaded'
  }

  // 外链（无本地副本）：拉取 blob 再下载
  try {
    const blob = await fetchVideoBlob(mediaUrl)
    triggerBlobDownload(blob, filename)
    return 'downloaded'
  } catch {
    openVideoDirectly(src)
    return 'opened-file'
  }
}
