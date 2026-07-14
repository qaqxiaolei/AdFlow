import CommonDialogContent from '@/components/common/DialogContent'
import { Button } from '@/components/ui/button'
import { Dialog } from '@/components/ui/dialog'
import { ScrollArea } from '@/components/ui/scroll-area'
import { SidebarInset, SidebarProvider, SidebarTrigger } from '@/components/ui/sidebar'
import { useConfigs } from '@/contexts/configs'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from '@tanstack/react-router'
import SettingProviders from './providers'
import SettingProxy from './proxy'
import SettingSidebar, { SettingSidebarType } from './sidebar'
import { ChevronLeft } from 'lucide-react'

const SettingsDialog = () => {
  const { showSettingsDialog: open, setShowSettingsDialog } = useConfigs()
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [current, setCurrent] = useState<SettingSidebarType>('provider')

  const handleBackHome = () => {
    setShowSettingsDialog(false)
    navigate({ to: '/' })
  }

  const renderContent = () => {
    switch (current) {
      case 'proxy':
        return <SettingProxy />
      case 'provider':
      default:
        return <SettingProviders />
    }
  }

  return (
    <Dialog open={open} onOpenChange={setShowSettingsDialog}>
      <CommonDialogContent
        open={open}
        transformPerspective={6000}
        className="flex flex-col p-0 gap-0 w-screen! h-dvh! max-h-dvh! max-w-[100vw]! rounded-none! border-none! shadow-none!"
      >
        <SidebarProvider className="flex flex-col flex-1 min-h-0 h-full">
          <header className="flex md:hidden items-center justify-between gap-2 px-2 py-2 border-b border-border shrink-0 bg-background pt-[max(0.5rem,env(safe-area-inset-top))]">
            <Button
              variant="ghost"
              size="sm"
              className="shrink-0 gap-1 px-2"
              onClick={handleBackHome}
            >
              <ChevronLeft className="size-5" />
              <span>{t('settings:backToHome')}</span>
            </Button>
            <span className="font-semibold text-sm truncate">{t('settings:title')}</span>
            <SidebarTrigger className="shrink-0" />
          </header>

          <div className="flex flex-1 min-h-0 w-full">
            <SettingSidebar
              current={current}
              setCurrent={setCurrent}
              onClose={() => setShowSettingsDialog(false)}
            />
            <SidebarInset className="min-h-0 overflow-hidden">
              <ScrollArea className="h-full w-full">
                {renderContent()}
              </ScrollArea>
            </SidebarInset>
          </div>
        </SidebarProvider>
      </CommonDialogContent>
    </Dialog>
  )
}

export default SettingsDialog
