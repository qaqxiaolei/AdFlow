import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  fetchCaptcha,
  loginWithPhone,
  registerWithPhone,
  resetPasswordWithCaptcha,
  validatePasswordClient,
  validatePhoneClient,
} from '@/api/auth'
import { useAuth } from '@/contexts/AuthContext'
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
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { cn } from '@/lib/utils'

type Mode = 'login' | 'register' | 'forgot'

interface AuthDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function AuthDialog({ open, onOpenChange }: AuthDialogProps) {
  const { t } = useTranslation()
  const { refreshAuth } = useAuth()
  const queryClient = useQueryClient()
  const isMobile = useIsMobile()
  const [mode, setMode] = useState<Mode>('login')
  const [phone, setPhone] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [captchaId, setCaptchaId] = useState('')
  const [captchaImage, setCaptchaImage] = useState('')
  const [captchaCode, setCaptchaCode] = useState('')
  const [captchaLoading, setCaptchaLoading] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const loadCaptcha = async () => {
    setCaptchaLoading(true)
    try {
      const data = await fetchCaptcha()
      setCaptchaId(data.captcha_id)
      setCaptchaImage(data.image_base64)
      setCaptchaCode('')
    } catch (err) {
      setError(
        err instanceof Error ? err.message : t('common:auth.captchaLoadFailed')
      )
    } finally {
      setCaptchaLoading(false)
    }
  }

  useEffect(() => {
    if (!open) {
      setError('')
      setPassword('')
      setConfirmPassword('')
      setCaptchaCode('')
      setCaptchaId('')
      setCaptchaImage('')
      setMode('login')
    }
  }, [open])

  useEffect(() => {
    if (!open || (mode !== 'register' && mode !== 'forgot')) return
    let cancelled = false
    ;(async () => {
      setCaptchaLoading(true)
      try {
        const data = await fetchCaptcha()
        if (cancelled) return
        setCaptchaId(data.captcha_id)
        setCaptchaImage(data.image_base64)
        setCaptchaCode('')
      } catch (err) {
        if (cancelled) return
        setError(
          err instanceof Error
            ? err.message
            : t('common:auth.captchaLoadFailed')
        )
      } finally {
        if (!cancelled) setCaptchaLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [open, mode, t])

  const switchMode = (next: Mode) => {
    setMode(next)
    setError('')
    setPassword('')
    setConfirmPassword('')
    setCaptchaCode('')
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    const phoneErr = validatePhoneClient(phone)
    if (phoneErr) {
      setError(phoneErr)
      return
    }

    if (mode === 'login') {
      if (!password) {
        setError(t('common:auth.passwordRequired'))
        return
      }
      setLoading(true)
      try {
        const result = await loginWithPhone(phone.trim(), password)
        toast.success(result.message || t('common:auth.loginSuccessMessage'))
        await refreshAuth()
        await queryClient.invalidateQueries({ queryKey: ['canvases'] })
        await queryClient.invalidateQueries({ queryKey: ['balance'] })
        onOpenChange(false)
      } catch (err) {
        setError(
          err instanceof Error ? err.message : t('common:auth.loginFailed')
        )
      } finally {
        setLoading(false)
      }
      return
    }

    if (!captchaCode.trim()) {
      setError(t('common:auth.captchaRequired'))
      return
    }

    const pwdErr = validatePasswordClient(password)
    if (pwdErr) {
      setError(pwdErr)
      return
    }
    if (password !== confirmPassword) {
      setError(t('common:auth.passwordMismatch'))
      return
    }

    setLoading(true)
    try {
      if (mode === 'forgot') {
        const result = await resetPasswordWithCaptcha(
          phone.trim(),
          password,
          captchaId,
          captchaCode.trim()
        )
        toast.success(result.message || t('common:auth.resetPasswordSuccess'))
        switchMode('login')
        return
      }

      const result = await registerWithPhone(
        phone.trim(),
        password,
        captchaId,
        captchaCode.trim()
      )
      toast.success(result.message || t('common:auth.registerSuccess'))
      await refreshAuth()
      await queryClient.invalidateQueries({ queryKey: ['canvases'] })
      await queryClient.invalidateQueries({ queryKey: ['balance'] })
      onOpenChange(false)
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : mode === 'forgot'
            ? t('common:auth.resetPasswordFailed')
            : t('common:auth.registerFailed')
      )
      void loadCaptcha()
    } finally {
      setLoading(false)
    }
  }

  const title =
    mode === 'login'
      ? t('common:auth.login')
      : mode === 'register'
        ? t('common:auth.register')
        : t('common:auth.forgotPassword')
  const description =
    mode === 'login'
      ? t('common:auth.loginPhoneDescription')
      : mode === 'register'
        ? t('common:auth.registerDescription')
        : t('common:auth.forgotPasswordDescription')

  const body = (
    <>
      <p
        className={cn(
          'text-muted-foreground',
          isMobile ? 'text-xs leading-relaxed mb-3' : 'text-sm mb-0'
        )}
      >
        {description}
      </p>

      {mode !== 'forgot' ? (
        <div className={cn('flex gap-2', isMobile ? 'mb-3' : 'mb-2')}>
          <Button
            type="button"
            variant={mode === 'login' ? 'default' : 'outline'}
            className={cn('flex-1 touch-manipulation', isMobile && 'h-11')}
            onClick={() => switchMode('login')}
          >
            {t('common:auth.login')}
          </Button>
          <Button
            type="button"
            variant={mode === 'register' ? 'default' : 'outline'}
            className={cn('flex-1 touch-manipulation', isMobile && 'h-11')}
            onClick={() => switchMode('register')}
          >
            {t('common:auth.register')}
          </Button>
        </div>
      ) : (
        <div className={cn(isMobile ? 'mb-3' : 'mb-2')}>
          <Button
            type="button"
            variant="ghost"
            className={cn('px-0 h-auto', isMobile && 'text-sm')}
            onClick={() => switchMode('login')}
          >
            ← {t('common:auth.backToLogin')}
          </Button>
        </div>
      )}

      <form
        onSubmit={handleSubmit}
        className={cn('space-y-4', isMobile && 'pb-1')}
      >
        <div className="space-y-2">
          <Label htmlFor="auth-phone">{t('common:auth.phone')}</Label>
          <Input
            id="auth-phone"
            inputMode="numeric"
            maxLength={11}
            value={phone}
            onChange={(e) =>
              setPhone(e.target.value.replace(/\D/g, '').slice(0, 11))
            }
            autoComplete="tel"
            className={cn(isMobile && 'h-11 text-base')}
          />
        </div>

        {(mode === 'register' || mode === 'forgot') && (
          <div className="space-y-2">
            <Label htmlFor="auth-captcha">{t('common:auth.captcha')}</Label>
            <div className="flex gap-2 items-center">
              <Input
                id="auth-captcha"
                value={captchaCode}
                onChange={(e) =>
                  setCaptchaCode(e.target.value.replace(/\s/g, '').slice(0, 6))
                }
                autoComplete="off"
                placeholder={t('common:auth.captchaPlaceholder')}
                maxLength={6}
                className={cn('flex-1', isMobile && 'h-11 text-base')}
              />
              <button
                type="button"
                onClick={() => void loadCaptcha()}
                disabled={captchaLoading}
                title={t('common:auth.captchaRefresh')}
                className={cn(
                  'shrink-0 rounded-md border border-input bg-muted/40 overflow-hidden',
                  'hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                  'disabled:opacity-60',
                  isMobile ? 'h-11 w-[120px]' : 'h-10 w-[120px]'
                )}
              >
                {captchaImage ? (
                  <img
                    src={captchaImage}
                    alt={t('common:auth.captcha')}
                    className="h-full w-full object-cover"
                    draggable={false}
                  />
                ) : (
                  <span className="text-xs text-muted-foreground px-2">
                    {captchaLoading
                      ? t('common:auth.loading')
                      : t('common:auth.captchaRefresh')}
                  </span>
                )}
              </button>
            </div>
            <p className="text-xs text-muted-foreground">
              {t('common:auth.captchaHint')}
            </p>
          </div>
        )}

        {mode === 'login' && (
          <div className="space-y-2">
            <div className="flex items-center justify-between gap-2">
              <Label htmlFor="auth-password">{t('common:auth.password')}</Label>
              <button
                type="button"
                className="text-xs text-primary hover:underline"
                onClick={() => switchMode('forgot')}
              >
                {t('common:auth.forgotPassword')}
              </button>
            </div>
            <Input
              id="auth-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              placeholder={t('common:auth.password')}
              className={cn(isMobile && 'h-11 text-base')}
            />
          </div>
        )}

        {(mode === 'register' || mode === 'forgot') && (
          <>
            <div className="space-y-2">
              <Label htmlFor="auth-new-password">
                {mode === 'forgot'
                  ? t('common:auth.newPassword')
                  : t('common:auth.password')}
              </Label>
              <Input
                id="auth-new-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="new-password"
                placeholder={t('common:auth.passwordHint')}
                className={cn(isMobile && 'h-11 text-base')}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="auth-confirm">
                {t('common:auth.confirmPassword')}
              </Label>
              <Input
                id="auth-confirm"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                autoComplete="new-password"
                className={cn(isMobile && 'h-11 text-base')}
              />
            </div>
          </>
        )}

        {error && <p className="text-sm text-destructive">{error}</p>}

        <Button
          type="submit"
          className={cn('w-full touch-manipulation', isMobile && 'h-11')}
          disabled={loading}
        >
          {loading
            ? t('common:auth.submitting')
            : mode === 'login'
              ? t('common:auth.login')
              : mode === 'register'
                ? t('common:auth.register')
                : t('common:auth.resetPassword')}
        </Button>
      </form>
    </>
  )

  if (isMobile) {
    return (
      <MobileBottomSheet
        open={open}
        onOpenChange={onOpenChange}
        title={title}
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
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription className="sr-only">
            {description}
          </DialogDescription>
        </DialogHeader>
        {body}
      </DialogContent>
    </Dialog>
  )
}
