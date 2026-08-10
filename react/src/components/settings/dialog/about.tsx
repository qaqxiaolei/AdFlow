import { LOGO_URL } from '@/constants'
import { useTranslation } from 'react-i18next'

const SettingAbout = () => {
  const { t } = useTranslation()

  return (
    <div className="flex flex-col gap-4 p-4 sm:p-6 max-w-2xl mx-auto w-full pb-10">
      <div className="flex flex-col gap-1">
        <h2 className="text-2xl font-bold tracking-tight">
          {t('settings:about.title')}
        </h2>
        <p className="text-sm text-muted-foreground">
          {t('settings:about.subtitle')}
        </p>
      </div>

      <div className="rounded-2xl bg-card border border-border px-6 py-8 flex flex-col items-center gap-3">
        <img
          src={LOGO_URL}
          alt={t('settings:about.appName')}
          className="w-20 h-20 object-contain"
          draggable={false}
        />
        <h3 className="text-xl font-bold">{t('settings:about.appName')}</h3>
        <p className="text-sm text-muted-foreground">
          {t('settings:about.version')}
        </p>
      </div>

      <div className="rounded-2xl bg-card border border-border px-5 py-5 flex flex-col gap-3">
        <h3 className="text-base font-bold">
          {t('settings:about.introTitle')}
        </h3>
        <p className="text-sm text-muted-foreground leading-relaxed">
          {t('settings:about.intro')}
        </p>
      </div>

      <div className="rounded-2xl bg-card border border-border px-5 py-5 flex flex-col gap-1">
        <h3 className="text-base font-bold mb-2">
          {t('settings:about.contactTitle')}
        </h3>
        <div className="flex items-start justify-between gap-3 py-3 border-b border-border">
          <span className="text-sm shrink-0">
            {t('settings:about.addressLabel')}
          </span>
          <span className="text-sm text-muted-foreground text-right">
            {t('settings:about.address')}
          </span>
        </div>
        <div className="flex items-center justify-between gap-3 py-3">
          <span className="text-sm shrink-0">
            {t('settings:about.phoneLabel')}
          </span>
          <span className="text-sm text-muted-foreground whitespace-nowrap">
            {t('settings:about.phone')}
          </span>
        </div>
      </div>
    </div>
  )
}

export default SettingAbout
