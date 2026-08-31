/** 微信 / iOS 从系统播放器返回后，WKWebView 常把 visualViewport.scale 留在 >1 */

const VIEWPORT_LOCKED =
  'width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover'

const VIEWPORT_UNLOCK_TICK =
  'width=device-width, initial-scale=1.0, maximum-scale=1.01, user-scalable=yes, viewport-fit=cover'

let resetting = false

function setViewport(content: string) {
  const meta = document.querySelector('meta[name="viewport"]')
  if (meta) meta.setAttribute('content', content)
}

export function resetViewportScale() {
  if (resetting) return
  resetting = true
  // 先放开再锁回 1，才能把已放大的 visualViewport 拉回来
  setViewport(VIEWPORT_UNLOCK_TICK)
  requestAnimationFrame(() => {
    setViewport(VIEWPORT_LOCKED)
    requestAnimationFrame(() => {
      resetting = false
    })
  })
}

function onPageVisible() {
  resetViewportScale()
}

window.addEventListener('pageshow', onPageVisible)
window.addEventListener('orientationchange', resetViewportScale)
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') onPageVisible()
})

window.visualViewport?.addEventListener('resize', () => {
  if ((window.visualViewport?.scale ?? 1) > 1.01) {
    resetViewportScale()
  }
})
