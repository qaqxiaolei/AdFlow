import { Button } from '@/components/ui/button'
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from '@/components/ui/sidebar'
import { cn } from '@/lib/utils'
import { UserRound, History, ChevronLeft } from 'lucide-react'
import { useTranslation } from 'react-i18next'

export type SettingSidebarType = 'about' | 'history'

type SettingSidebar = {
  current: SettingSidebarType
  setCurrent: (current: SettingSidebarType) => void
  onClose?: () => void
}

const SettingSidebar: React.FC<SettingSidebar> = ({
  current,
  setCurrent,
  onClose,
}) => {
  const { t } = useTranslation()

  const items: {
    type: SettingSidebarType
    title: string
    icon: React.ElementType
  }[] = [
    {
      type: 'history',
      title: 'settings:history.title',
      icon: History,
    },
    {
      type: 'about',
      title: 'settings:about.title',
      icon: UserRound,
    },
  ]

  return (
    <Sidebar className="h-full rounded-l-lg overflow-hidden">
      <SidebarContent>
        <SidebarGroup>
          <div className="flex items-center justify-between mb-2">
            {onClose && (
              <Button onClick={onClose}>
                <ChevronLeft className="h-6 w-6" />
                <span className="sr-only">Close</span>
              </Button>
            )}
            <SidebarGroupLabel className="text-lg font-bold select-none">
              {t('settings:title')}
            </SidebarGroupLabel>
          </div>
          <SidebarGroupContent>
            <SidebarMenu>
              {items.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton asChild>
                    <div
                      className={cn(
                        'flex items-center gap-2 select-none cursor-pointer',
                        current === item.type && 'bg-muted'
                      )}
                      onClick={() => setCurrent(item.type)}
                    >
                      <item.icon />
                      <span>{t(item.title)}</span>
                    </div>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
    </Sidebar>
  )
}

export default SettingSidebar
