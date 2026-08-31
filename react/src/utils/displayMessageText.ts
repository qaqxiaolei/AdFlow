/** 展示用：去掉前端注入的内部参数标签 */
export function stripInternalMessageTags(text: string): string {
  return text
    .replace(/<aspect_ratio>[\s\S]*?<\/aspect_ratio>\s*/gi, '')
    .replace(/<quantity>[\s\S]*?<\/quantity>\s*/gi, '')
    .replace(/<generation_mode>[\s\S]*?<\/generation_mode>\s*/gi, '')
    .replace(/<input_images>[\s\S]*?<\/input_images>\s*/gi, '')
    .trim()
}

/** 顶部会话名等窄区域展示：单行截断 */
export function truncateDisplayTitle(text: string, maxLen = 16): string {
  const cleaned = stripInternalMessageTags(text).replace(/\s+/g, ' ').trim()
  if (!cleaned) return '未命名'
  if (cleaned.length <= maxLen) return cleaned
  return `${cleaned.slice(0, maxLen)}…`
}
