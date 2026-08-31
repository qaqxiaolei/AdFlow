/** 将 /api/file/... 转为当前站点绝对 URL，避免微信 WebView 相对路径异常 */
export function resolveMediaUrl(src: string): string {
  if (!src) return src
  if (src.startsWith('http://') || src.startsWith('https://')) {
    return src
  }
  const path = src.startsWith('/') ? src : `/${src}`
  return `${window.location.origin}${path}`
}

export function isWeChatBrowser(): boolean {
  return /MicroMessenger/i.test(navigator.userAgent)
}

export function isProbablyVideoUrl(src: string, alt?: string): boolean {
  if (!src) return false
  if (alt && /video/i.test(alt)) return true
  if (/\.(mp4|webm|mov)(\?|$)/i.test(src)) return true
  if (/\/api\/file\/vi_/i.test(src)) return true
  if (/agnes-ai\.space|agnes-aigc/i.test(src)) return true
  if (/\/api\/file\//i.test(src) && !/\.(png|jpe?g|gif|webp|svg|ico)(\?|$)/i.test(src)) {
    return true
  }
  return false
}

export function shouldAvoidInlineVideo(): boolean {
  return isWeChatBrowser() || /Android|iPhone|iPad|iPod/i.test(navigator.userAgent)
}

export function normalizeVideoKey(url: string): string {
  return url.replace(/^https?:\/\/[^/]+/i, '').replace(/[?#].*$/, '')
}

/** 同一段对话里同一个视频只保留第一次出现，避免下方再渲染一块黑屏 */
export function stripDuplicateVideoMarkdown(
  text: string,
  seen: Set<string>
): string {
  return text.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (full, alt, url) => {
    if (!isProbablyVideoUrl(url, alt)) return full
    const key = normalizeVideoKey(url)
    if (seen.has(key)) return ''
    seen.add(key)
    return full
  })
}
