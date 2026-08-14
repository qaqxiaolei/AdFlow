import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { useQueryClient } from '@tanstack/react-query'
import {
  createWechatRechargeOrder,
  getRechargeOrderStatus,
  getRechargePackages,
  mockConfirmWechatPay,
  type RechargePackage,
  type WechatOrderResponse,
} from '@/api/billing'
import { useIsMobile } from '@/hooks/use-mobile'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { MobileBottomSheet } from '@/components/ui/mobile-bottom-sheet'
import {
  buildRechargeRedirectUrl,
  clearPendingRechargeOrder,
  clearPendingRechargePackage,
  clearRechargeQueryParams,
  getWechatTradeType,
  invokeWechatJsapiPay,
  isMobileDevice,
  isWechatBrowser,
  loadPendingRechargeOrder,
  loadPendingRechargePackage,
  loadWechatOpenid,
  savePendingRechargeOrder,
  savePendingRechargePackage,
  saveWechatOpenid,
  startWechatOAuth,
} from '@/lib/wechat-pay'
import { cn } from '@/lib/utils'

interface RechargeDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

type Step = 'select' | 'pay'

export function RechargeDialog({ open, onOpenChange }: RechargeDialogProps) {
  const { t } = useTranslation()
  const isMobile = useIsMobile()
  const queryClient = useQueryClient()
  const [packages, setPackages] = useState<RechargePackage[]>([])
  const [loading, setLoading] = useState(false)
  const [selected, setSelected] = useState<string>('')
  const [submitting, setSubmitting] = useState(false)
  const [step, setStep] = useState<Step>('select')
  const [order, setOrder] = useState<WechatOrderResponse | null>(null)
  const [mockMode, setMockMode] = useState(true)

  const inWechat = isWechatBrowser()
  const tradeType = getWechatTradeType()
  const useNativePay = tradeType === 'native'

  const finishPaid = async (credits: number) => {
    clearPendingRechargeOrder()
    clearPendingRechargePackage()
    clearRechargeQueryParams()
    toast.success(
      t('common:auth.rechargeSuccess', {
        credits,
      })
    )
    await queryClient.invalidateQueries({ queryKey: ['balance'] })
    onOpenChange(false)
  }

  useEffect(() => {
    if (!open) {
      setStep('select')
      setOrder(null)
      setSubmitting(false)
      return
    }
    setLoading(true)
    getRechargePackages()
      .then((res) => {
        setPackages(res.packages)
        setMockMode(res.wechat_mock)
        const pendingPkg = loadPendingRechargePackage()
        if (pendingPkg && res.packages.some((p) => p.id === pendingPkg)) {
          setSelected(pendingPkg)
        } else if (res.packages.length > 0) {
          setSelected(res.packages[0].id)
        }
        if (res.wechat_mock) {
          toast.message(t('common:auth.wechatMockHint'))
        } else if (!res.wechat_ready && res.wechat_missing.length > 0) {
          toast.error(
            t('common:auth.wechatConfigIncomplete', {
              missing: res.wechat_missing.join('；'),
            })
          )
        }
      })
      .catch(() => toast.error(t('common:auth.rechargeLoadFailed')))
      .finally(() => setLoading(false))
  }, [open, t])

  // OAuth 回跳：保存 openid；支付回跳：恢复订单
  useEffect(() => {
    if (!open || loading) return

    const params = new URLSearchParams(window.location.search)
    const oauthError = params.get('wechat_oauth_error')
    if (oauthError) {
      toast.error(oauthError)
      clearRechargeQueryParams()
      return
    }

    const openidFromQuery = params.get('wechat_openid')
    if (openidFromQuery) {
      saveWechatOpenid(openidFromQuery)
      clearRechargeQueryParams()
      const pendingPkg = loadPendingRechargePackage()
      if (pendingPkg) {
        void handleCreateOrder(pendingPkg, openidFromQuery)
      }
      return
    }

    const fromQuery =
      params.get('recharge_order') || params.get('order_id') || ''
    const pendingId = fromQuery || loadPendingRechargeOrder()
    if (!pendingId) return

    let cancelled = false
    ;(async () => {
      try {
        if (params.get('wechat_mock_pay') === '1') {
          await mockConfirmWechatPay(pendingId)
        }
        const status = await getRechargeOrderStatus(pendingId)
        if (cancelled) return
        if (status.status === 'paid') {
          await finishPaid(status.credits)
          return
        }
        setOrder({
          status: status.status,
          order_id: status.order_id,
          credits: status.credits,
          price_cny: status.price_cny,
          amount_cents: Math.round(status.price_cny * 100),
          qr_image: '',
          code_url: '',
          h5_url: '',
          trade_type: getWechatTradeType(),
          mock: mockMode,
        })
        setStep('pay')
      } catch {
        // ignore restore errors
      } finally {
        if (fromQuery) clearRechargeQueryParams()
      }
    })()

    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, loading, mockMode, isMobile])

  useEffect(() => {
    if (!open || step !== 'pay' || !order?.order_id) return
    if (order.status === 'paid') return

    let cancelled = false
    const timer = window.setInterval(async () => {
      try {
        const status = await getRechargeOrderStatus(order.order_id)
        if (cancelled) return
        if (status.status === 'paid') {
          await finishPaid(status.credits)
        }
      } catch {
        // keep polling
      }
    }, 2000)

    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, step, order?.order_id])

  const handleCreateOrder = async (
    packageId?: string,
    openidOverride?: string
  ) => {
    const pkgId = packageId || selected
    if (!pkgId) return
    setSubmitting(true)
    try {
      const currentTradeType = getWechatTradeType()

      if (currentTradeType === 'jsapi') {
        if (!isWechatBrowser()) {
          toast.error(t('common:auth.wechatJsapiNeedWechat'))
          return
        }
        const openid = openidOverride || loadWechatOpenid()
        if (!openid) {
          savePendingRechargePackage(pkgId)
          startWechatOAuth(buildRechargeRedirectUrl())
          return
        }

        const created = await createWechatRechargeOrder(pkgId, {
          tradeType: 'jsapi',
          openid,
        })
        savePendingRechargeOrder(created.order_id)
        clearPendingRechargePackage()
        setOrder(created)
        setStep('pay')

        if (created.mock) {
          // 模拟模式：直接确认到账
          const result = await mockConfirmWechatPay(created.order_id)
          toast.success(result.message)
          clearPendingRechargeOrder()
          await queryClient.invalidateQueries({ queryKey: ['balance'] })
          onOpenChange(false)
          return
        }

        if (!created.jsapi_params) {
          throw new Error(t('common:auth.rechargeFailed'))
        }

        const payResult = await invokeWechatJsapiPay(created.jsapi_params)
        if (payResult === 'ok') {
          // 等待回调轮询到账
          toast.message(t('common:auth.wechatWaiting'))
        } else if (payResult === 'cancel') {
          toast.message(t('common:auth.wechatPayCancelled'))
        } else {
          toast.error(t('common:auth.wechatPayFailed'))
        }
        return
      }

      // Native / H5
      const created = await createWechatRechargeOrder(pkgId, {
        tradeType: currentTradeType,
        redirectUrl:
          currentTradeType === 'h5' ? buildRechargeRedirectUrl() : undefined,
      })

      savePendingRechargeOrder(created.order_id)

      const payUrl =
        created.h5_url || (currentTradeType === 'h5' ? created.code_url : '')
      if (currentTradeType === 'h5' && payUrl) {
        window.location.href = payUrl
        return
      }

      setOrder(created)
      setStep('pay')
    } catch (e) {
      toast.error(
        e instanceof Error ? e.message : t('common:auth.rechargeFailed')
      )
    } finally {
      setSubmitting(false)
    }
  }

  const handleMockPay = async () => {
    if (!order?.order_id) return
    setSubmitting(true)
    try {
      const result = await mockConfirmWechatPay(order.order_id)
      toast.success(result.message)
      clearPendingRechargeOrder()
      await queryClient.invalidateQueries({ queryKey: ['balance'] })
      onOpenChange(false)
    } catch (e) {
      toast.error(
        e instanceof Error ? e.message : t('common:auth.rechargeFailed')
      )
    } finally {
      setSubmitting(false)
    }
  }

  const handleRetryJsapi = async () => {
    if (!order?.jsapi_params) return
    setSubmitting(true)
    try {
      const payResult = await invokeWechatJsapiPay(order.jsapi_params)
      if (payResult === 'ok') {
        toast.message(t('common:auth.wechatWaiting'))
      } else if (payResult === 'cancel') {
        toast.message(t('common:auth.wechatPayCancelled'))
      } else {
        toast.error(t('common:auth.wechatPayFailed'))
      }
    } finally {
      setSubmitting(false)
    }
  }

  const payHint = inWechat
    ? t('common:auth.wechatJsapiHint')
    : isMobileDevice()
      ? t('common:auth.wechatOpenInWechatHint')
      : t('common:auth.wechatScanHint')

  const body = (
    <>
      {step === 'select' ? (
        <>
          <p
            className={cn(
              'text-muted-foreground',
              isMobile ? 'text-xs leading-relaxed mb-3' : 'text-sm mb-0'
            )}
          >
            {t('common:auth.rechargeDescription')}
          </p>
          {!inWechat ? (
            <p className="text-xs text-amber-600 dark:text-amber-400 mb-3">
              {t('common:auth.wechatOpenInWechatHint')}
            </p>
          ) : null}

          {loading ? (
            <div className="py-8 text-center text-sm text-muted-foreground">
              {t('common:auth.loading')}
            </div>
          ) : (
            <div className={cn('grid gap-2', isMobile ? 'mb-3' : 'mb-0')}>
              {packages.map((pkg) => (
                <button
                  key={pkg.id}
                  type="button"
                  onClick={() => setSelected(pkg.id)}
                  className={cn(
                    'flex items-center justify-between rounded-md border px-4 text-left transition-colors touch-manipulation',
                    isMobile ? 'min-h-14 py-3.5' : 'py-3',
                    selected === pkg.id
                      ? 'border-primary bg-primary/5'
                      : 'border-border hover:bg-muted/50'
                  )}
                >
                  <div>
                    <div className="font-medium">{pkg.label}</div>
                    <div className="text-sm text-muted-foreground">
                      {pkg.credits} {t('common:auth.credits')}
                    </div>
                  </div>
                  <div className="text-sm font-semibold">¥{pkg.price_cny}</div>
                </button>
              ))}
            </div>
          )}

          <Button
            className={cn('w-full touch-manipulation', isMobile && 'h-11')}
            disabled={!selected || submitting || loading}
            onClick={() => handleCreateOrder()}
          >
            {submitting
              ? t('common:auth.submitting')
              : t('common:auth.wechatPay')}
          </Button>
        </>
      ) : (
        <div className="flex flex-col items-center gap-3">
          <p className="text-sm text-muted-foreground text-center">{payHint}</p>
          {useNativePay && order?.qr_image ? (
            <img
              src={order.qr_image}
              alt="WeChat Pay QR"
              className="h-48 w-48 rounded-md border bg-white p-2"
            />
          ) : null}
          {order ? (
            <div className="text-center text-sm">
              <div className="font-semibold text-lg">¥{order.price_cny}</div>
              <div className="text-muted-foreground">
                {order.credits} {t('common:auth.credits')}
              </div>
            </div>
          ) : null}
          <p className="text-xs text-muted-foreground">
            {t('common:auth.wechatWaiting')}
          </p>

          <div className="flex w-full gap-2 pt-1">
            <Button
              type="button"
              variant="outline"
              className={cn('flex-1', isMobile && 'h-11')}
              onClick={() => {
                setStep('select')
                setOrder(null)
                clearPendingRechargeOrder()
              }}
            >
              {t('common:auth.cancel')}
            </Button>
            {order?.trade_type === 'jsapi' && order.jsapi_params ? (
              <Button
                type="button"
                className={cn('flex-1', isMobile && 'h-11')}
                disabled={submitting}
                onClick={handleRetryJsapi}
              >
                {t('common:auth.wechatOpenAgain')}
              </Button>
            ) : null}
            {mockMode ? (
              <Button
                type="button"
                className={cn('flex-1', isMobile && 'h-11')}
                disabled={submitting}
                onClick={handleMockPay}
              >
                {submitting
                  ? t('common:auth.submitting')
                  : t('common:auth.wechatMockPaid')}
              </Button>
            ) : null}
          </div>
        </div>
      )}
    </>
  )

  if (isMobile) {
    return (
      <MobileBottomSheet
        open={open}
        onOpenChange={onOpenChange}
        title={t('common:auth.recharge')}
        className="max-h-[90dvh]"
        contentClassName="overflow-y-auto overscroll-contain max-h-[calc(90dvh-3.5rem)]"
      >
        {body}
      </MobileBottomSheet>
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{t('common:auth.recharge')}</DialogTitle>
          <DialogDescription className="sr-only">
            {t('common:auth.rechargeDescription')}
          </DialogDescription>
        </DialogHeader>
        {body}
      </DialogContent>
    </Dialog>
  )
}
