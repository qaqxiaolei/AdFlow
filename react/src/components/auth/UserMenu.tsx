import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { useAuth } from '@/contexts/AuthContext'
import { useRefreshModels } from '@/contexts/configs'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { logout } from '@/api/auth'
import { PointsDisplay } from './PointsDisplay'
import { RechargeDialog } from './RechargeDialog'

export function UserMenu() {
  const { authStatus, refreshAuth, openAuthDialog } = useAuth()
  const refreshModels = useRefreshModels()
  const { t } = useTranslation()
  const [showRechargeDialog, setShowRechargeDialog] = useState(false)
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  const handleLogout = async () => {
    await logout()
    queryClient.removeQueries({ queryKey: ['canvases'] })
    queryClient.removeQueries({ queryKey: ['balance'] })
    await refreshAuth()
    refreshModels()
    navigate({ to: '/' })
  }

  if (authStatus.is_logged_in && authStatus.user_info) {
    const { username, phone } = authStatus.user_info
    const display = phone || username || 'U'
    const initials = display.substring(0, 2).toUpperCase()

    return (
      <>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" className="relative p-0 h-auto gap-2 px-2">
              <PointsDisplay>
                <Avatar className="h-6 w-6">
                  <AvatarFallback className="text-xs">{initials}</AvatarFallback>
                </Avatar>
              </PointsDisplay>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel>{t('common:auth.myAccount')}</DropdownMenuLabel>
            <DropdownMenuItem disabled>{display}</DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => setShowRechargeDialog(true)}>
              {t('common:auth.recharge')}
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={handleLogout}>
              {t('common:auth.logout')}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
        <RechargeDialog
          open={showRechargeDialog}
          onOpenChange={setShowRechargeDialog}
        />
      </>
    )
  }

  return (
    <Button variant="outline" size="sm" onClick={openAuthDialog}>
      {t('common:auth.login')}
    </Button>
  )
}
