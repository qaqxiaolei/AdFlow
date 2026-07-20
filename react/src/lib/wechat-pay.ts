export const PENDING_RECHARGE_ORDER_KEY = 'adflow_pending_recharge_order'

export function isWechatBrowser(): boolean {
  if (typeof navigator === 'undefined') return false
  return /MicroMessenger/i.test(navigator.userAgent)
}

export function isMobileDevice(): boolean {
  if (typeof window === 'undefined') return false
  const ua = navigator.userAgent || ''
  const byUa =
    /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini|Mobile/i.test(
      ua
    )
  const byWidth = window.innerWidth < 768
  return byUa || byWidth || isWechatBrowser()
}

/** 手机端或微信内置浏览器走 H5 跳转；桌面浏览器走 Native 扫码 */
export function getWechatTradeType(): 'h5' | 'native' {
  return isMobileDevice() ? 'h5' : 'native'
}

export function savePendingRechargeOrder(orderId: string) {
  try {
    sessionStorage.setItem(PENDING_RECHARGE_ORDER_KEY, orderId)
  } catch {
    // ignore
  }
}

export function loadPendingRechargeOrder(): string | null {
  try {
    return sessionStorage.getItem(PENDING_RECHARGE_ORDER_KEY)
  } catch {
    return null
  }
}

export function clearPendingRechargeOrder() {
  try {
    sessionStorage.removeItem(PENDING_RECHARGE_ORDER_KEY)
  } catch {
    // ignore
  }
}

export function hasWechatRechargeReturn(): boolean {
  if (typeof window === 'undefined') return false
  const params = new URLSearchParams(window.location.search)
  return (
    params.has('recharge_order') ||
    params.has('wechat_mock_pay') ||
    Boolean(loadPendingRechargeOrder())
  )
}

export function clearRechargeQueryParams() {
  const params = new URLSearchParams(window.location.search)
  ;['recharge_order', 'wechat_mock_pay', 'order_id'].forEach((key) =>
    params.delete(key)
  )
  const next = `${window.location.pathname}${
    params.toString() ? `?${params}` : ''
  }${window.location.hash}`
  window.history.replaceState({}, '', next)
}

export function buildRechargeRedirectUrl(): string {
  return `${window.location.origin}${window.location.pathname}${window.location.search}`
}
