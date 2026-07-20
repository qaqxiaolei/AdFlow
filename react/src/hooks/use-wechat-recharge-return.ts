import { useEffect } from 'react'
import { hasWechatRechargeReturn } from '@/lib/wechat-pay'

/** 从微信支付页回跳后自动打开充值弹窗 */
export function useWechatRechargeReturn(
  isLoggedIn: boolean,
  openRecharge: (open: boolean) => void
) {
  useEffect(() => {
    if (!isLoggedIn) return
    if (hasWechatRechargeReturn()) {
      openRecharge(true)
    }
  }, [isLoggedIn, openRecharge])
}
