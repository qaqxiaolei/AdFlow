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
      })
      .catch(() => toast.error(t('common:auth.rechargeLoadFailed')))
      .finally(() => setLoading(false))
  }, [open, t])

  useEffect(() => {
    if (!open || step !== 'pay' || !order?.order_id) return
    if (order.status === 'paid') return

    let cancelled = false
    const timer = window.setInterval(async () => {
      try {
        const status = await getRechargeOrderStatus(order.order_id)
        if (cancelled) return
        if (status.status === 'paid') {
          toast.success(
            t('common:auth.rechargeSuccess', {
              credits: status.credits,
            })
          )
          await queryClient.invalidateQueries({ queryKey: ['balance'] })
          onOpenChange(false)
        }
      } catch {
        // keep polling
      }
    }, 2000)

    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [open, step, order, queryClient, onOpenChange, t])

  const handleCreateOrder = async () => {
    if (!selected) return
    setSubmitting(true)
    try {
      const created = await createWechatRechargeOrder(selected)
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
            {t('common:auth.wechatScanHint')}
          </p>
          {order?.qr_image ? (
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
              }}
            >
              {t('common:auth.cancel')}
            </Button>
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
