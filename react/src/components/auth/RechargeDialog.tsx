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
  clearRechargeQueryParams,
  getWechatTradeType,
  isMobileDevice,
  loadPendingRechargeOrder,
  savePendingRechargeOrder,
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

  const useH5Pay = isMobileDevice()

  const finishPaid = async (credits: number) => {
    clearPendingRechargeOrder()
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
        if (res.packages.length > 0) setSelected(res.packages[0].id)
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

  // 从微信支付页回跳后，恢复订单并确认到账
  useEffect(() => {
    if (!open || loading) return

    const params = new URLSearchParams(window.location.search)
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

  const handleCreateOrder = async () => {
    if (!selected) return
    setSubmitting(true)
    try {
      const tradeType = getWechatTradeType()
      const created = await createWechatRechargeOrder(selected, {
        tradeType,
        redirectUrl:
          tradeType === 'h5' ? buildRechargeRedirectUrl() : undefined,
      })

      savePendingRechargeOrder(created.order_id)

      const payUrl = created.h5_url || (tradeType === 'h5' ? created.code_url : '')
      if (tradeType === 'h5' && payUrl) {
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

  const handleOpenWechatAgain = () => {
    const url = order?.h5_url || order?.code_url
    if (url) window.location.href = url
  }

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
            onClick={handleCreateOrder}
          >
            {submitting
              ? t('common:auth.submitting')
              : t('common:auth.wechatPay')}
          </Button>
        </>
      ) : (
        <div className="flex flex-col items-center gap-3">
          <p className="text-sm text-muted-foreground text-center">
            {useH5Pay
              ? t('common:auth.wechatH5Hint')
              : t('common:auth.wechatScanHint')}
          </p>
          {!useH5Pay && order?.qr_image ? (
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
            {useH5Pay && (order?.h5_url || order?.code_url) ? (
              <Button
                type="button"
                className={cn('flex-1', isMobile && 'h-11')}
                onClick={handleOpenWechatAgain}
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
