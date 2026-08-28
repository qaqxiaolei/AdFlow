import { useEffect } from 'react'
import { consumeWechatRechargeReturn } from '@/lib/wechat-pay'

/** 从微信支付页回跳后自动打开充值弹窗（整次会话只触发一次） */
export function useWechatRechargeReturn(
  isLoggedIn: boolean,
  openRecharge: (open: boolean) => void
) {
  useEffect(() => {
    if (!isLoggedIn) return
    if (consumeWechatRechargeReturn()) {
      openRecharge(true)
    }
  }, [isLoggedIn, openRecharge])
}
