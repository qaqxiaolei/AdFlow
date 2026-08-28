export const PENDING_RECHARGE_ORDER_KEY = 'adflow_pending_recharge_order'
export const WECHAT_OPENID_KEY = 'adflow_wechat_openid'
export const PENDING_RECHARGE_PACKAGE_KEY = 'adflow_pending_recharge_package'

export type WechatTradeType = 'jsapi' | 'native' | 'h5'

export interface WechatJsapiPayParams {
  appId: string
  timeStamp: string
  nonceStr: string
  package: string
  signType: string
  paySign: string
}

declare global {
  interface Window {
    WeixinJSBridge?: {
      invoke: (
        method: string,
        params: Record<string, string>,
        callback: (res: { err_msg?: string }) => void
      ) => void
    }
  }
}

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

/**
 * 微信内 → JSAPI；其它端 → Native 扫码。
 * （H5 未开通时不再默认走 H5）
 */
export function getWechatTradeType(): WechatTradeType {
  if (isWechatBrowser()) return 'jsapi'
  return 'native'
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

export function savePendingRechargePackage(packageId: string) {
  try {
    sessionStorage.setItem(PENDING_RECHARGE_PACKAGE_KEY, packageId)
  } catch {
    // ignore
  }
}

export function loadPendingRechargePackage(): string | null {
  try {
    return sessionStorage.getItem(PENDING_RECHARGE_PACKAGE_KEY)
  } catch {
    return null
  }
}

export function clearPendingRechargePackage() {
  try {
    sessionStorage.removeItem(PENDING_RECHARGE_PACKAGE_KEY)
  } catch {
    // ignore
  }
}

export function saveWechatOpenid(openid: string) {
  try {
    sessionStorage.setItem(WECHAT_OPENID_KEY, openid)
  } catch {
    // ignore
  }
}

export function loadWechatOpenid(): string | null {
  try {
    return sessionStorage.getItem(WECHAT_OPENID_KEY)
  } catch {
    return null
  }
}

const RECHARGE_RETURN_CONSUMED_KEY = 'adflow_recharge_return_consumed'

export function hasWechatRechargeReturn(): boolean {
  if (typeof window === 'undefined') return false
  const params = new URLSearchParams(window.location.search)
  return (
    params.has('recharge_order') ||
    params.has('wechat_mock_pay') ||
    params.has('wechat_openid') ||
    params.has('open_recharge') ||
    Boolean(loadPendingRechargeOrder())
  )
}

/** 标记本次回跳已自动打开过弹窗，避免多处挂载/路由切换重复弹窗 */
export function consumeWechatRechargeReturn(): boolean {
  if (!hasWechatRechargeReturn()) return false
  try {
    if (sessionStorage.getItem(RECHARGE_RETURN_CONSUMED_KEY) === '1') {
      return false
    }
    sessionStorage.setItem(RECHARGE_RETURN_CONSUMED_KEY, '1')
  } catch {
    // ignore
  }
  return true
}

/** 用户关闭充值弹窗：清掉待支付标记，避免之后点别处又弹出来 */
export function dismissWechatRechargeReturn() {
  clearPendingRechargeOrder()
  clearPendingRechargePackage()
  clearRechargeQueryParams()
  try {
    sessionStorage.removeItem(RECHARGE_RETURN_CONSUMED_KEY)
  } catch {
    // ignore
  }
}

export function clearRechargeQueryParams() {
  const params = new URLSearchParams(window.location.search)
  ;[
    'recharge_order',
    'wechat_mock_pay',
    'order_id',
    'wechat_openid',
    'open_recharge',
    'wechat_oauth_error',
  ].forEach((key) => params.delete(key))
  const next = `${window.location.pathname}${
    params.toString() ? `?${params}` : ''
  }${window.location.hash}`
  window.history.replaceState({}, '', next)
}

export function buildRechargeRedirectUrl(): string {
  return `${window.location.origin}${window.location.pathname}${window.location.search}`
}

/** 跳转后端发起微信网页授权（静默拿 openid） */
export function startWechatOAuth(returnUrl?: string) {
  const target = returnUrl || buildRechargeRedirectUrl()
  const url = `/api/billing/wechat/oauth/start?return_url=${encodeURIComponent(target)}`
  window.location.href = url
}

export function invokeWechatJsapiPay(
  params: WechatJsapiPayParams
): Promise<'ok' | 'cancel' | 'fail'> {
  return new Promise((resolve) => {
    const doPay = () => {
      const bridge = window.WeixinJSBridge
      if (!bridge) {
        resolve('fail')
        return
      }
      bridge.invoke(
        'getBrandWCPayRequest',
        {
          appId: params.appId,
          timeStamp: params.timeStamp,
          nonceStr: params.nonceStr,
          package: params.package,
          signType: params.signType,
          paySign: params.paySign,
        },
        (res) => {
          const msg = res?.err_msg || ''
          if (msg === 'get_brand_wcpay_request:ok') resolve('ok')
          else if (msg === 'get_brand_wcpay_request:cancel') resolve('cancel')
          else resolve('fail')
        }
      )
    }

    if (typeof window.WeixinJSBridge === 'undefined') {
      document.addEventListener('WeixinJSBridgeReady', doPay, false)
      // 兜底：部分机型事件丢失
      window.setTimeout(() => {
        if (window.WeixinJSBridge) doPay()
        else resolve('fail')
      }, 2500)
    } else {
      doPay()
    }
  })
}
