import { authenticatedFetch } from './auth'

export interface BalanceResponse {
  balance: string
}

export interface RechargePackage {
  id: string
  credits: number
  price_cny: number
  label: string
}

export interface WechatOrderResponse {
  status: string
  order_id: string
  credits: number
  price_cny: number
  amount_cents: number
  qr_image: string
  code_url: string
  mock: boolean
  message?: string
}

export interface OrderStatusResponse {
  order_id: string
  status: 'pending' | 'paid' | string
  credits: number
  price_cny: number
  paid_at?: string
  balance: string
}

export async function getBalance(): Promise<BalanceResponse> {
  const response = await authenticatedFetch('/api/billing/getBalance')
  if (!response.ok) {
    throw new Error(`Failed to fetch balance: ${response.status}`)
  }
  return await response.json()
}

export async function getRechargePackages(): Promise<{
  packages: RechargePackage[]
  wechat_mock: boolean
}> {
  const response = await authenticatedFetch('/api/billing/packages')
  if (!response.ok) {
    throw new Error(`Failed to fetch packages: ${response.status}`)
  }
  const data = await response.json()
  return {
    packages: data.packages || [],
    wechat_mock: Boolean(data.wechat_mock),
  }
}

export async function createWechatRechargeOrder(
  packageId: string
): Promise<WechatOrderResponse> {
  const response = await authenticatedFetch('/api/billing/wechat/create-order', {
    method: 'POST',
    body: JSON.stringify({ package_id: packageId }),
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail =
      typeof data.detail === 'string' ? data.detail : '创建支付订单失败'
    throw new Error(detail)
  }
  return data
}

export async function getRechargeOrderStatus(
  orderId: string
): Promise<OrderStatusResponse> {
  const response = await authenticatedFetch(`/api/billing/orders/${orderId}`)
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail =
      typeof data.detail === 'string' ? data.detail : '查询订单失败'
    throw new Error(detail)
  }
  return data
}

export async function mockConfirmWechatPay(
  orderId: string
): Promise<{ status: string; message: string; balance: string }> {
  const response = await authenticatedFetch(
    `/api/billing/orders/${orderId}/mock-pay`,
    { method: 'POST' }
  )
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail =
      typeof data.detail === 'string' ? data.detail : '确认支付失败'
    throw new Error(detail)
  }
  return data
}

/** @deprecated 使用 createWechatRechargeOrder */
export async function rechargePackage(
  packageId: string
): Promise<WechatOrderResponse> {
  return createWechatRechargeOrder(packageId)
}
