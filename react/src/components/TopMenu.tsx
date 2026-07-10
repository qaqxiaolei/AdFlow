import { useConfigs } from '@/contexts/configs'
import { Button } from '@/components/ui/button'
import { ChevronLeft, MoreVertical, MoonIcon, SettingsIcon, SunIcon } from 'lucide-react'
import { motion } from 'motion/react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useLocation } from '@tanstack/react-router'
import { LOGO_URL } from '@/constants'
import { UserMenu } from './auth/UserMenu'
import { useIsMobile } from '@/hooks/use-mobile'
import { useTheme } from '@/hooks/use-theme'
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import ThemeButton from '@/components/theme/ThemeButton'

export default function TopMenu({
    middle,
    right,
}: {
    middle?: React.ReactNode
    right?: React.ReactNode
}) {
    const { t } = useTranslation()
    const navigate = useNavigate()
    const location = useLocation()
    const isMobile = useIsMobile()
    const { setTheme, theme } = useTheme()
    const { setShowSettingsDialog } = useConfigs()
    const isHome = location.pathname === '/'

    return (
        <motion.div
            className="sticky top-0 z-20 flex w-full min-h-12 sm:min-h-8 py-2 sm:py-0 bg-background px-3 sm:px-4 justify-between items-center select-none border-b border-border pt-[max(0.5rem,env(safe-area-inset-top))]"
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
        >
            <div className="flex items-center gap-2 sm:gap-8 min-w-0 flex-1">
                <motion.div
                    className="flex items-center gap-1.5 sm:gap-2 cursor-pointer group min-w-0"
                    onClick={() => navigate({ to: '/' })}
                >
                    {!isHome && (
                        <ChevronLeft className="size-5 shrink-0 group-hover:-translate-x-0.5 transition-transform duration-300" />
                    )}
                    <img src={LOGO_URL} alt="logo" className="size-5 shrink-0" draggable={false} />
                    <motion.div className="flex relative overflow-hidden items-start min-h-7 text-base sm:text-xl font-bold min-w-0">
                        <motion.span className="truncate" layout>
                            {isHome ? '餐饮商家' : t('canvas:back')}
                        </motion.span>
                    </motion.div>
                </motion.div>
            </div>

            {middle && (
                <div className="hidden md:flex items-center gap-2 mx-2">{middle}</div>
            )}

            <div className="flex items-center gap-1 sm:gap-2 shrink-0">
                {right}
                {isMobile ? (
                    <>
                        <UserMenu />
                        <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                                <Button size="sm" variant="ghost" aria-label="更多操作">
                                    <MoreVertical className="size-5" />
                                </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end" className="w-44">
                                <DropdownMenuItem onClick={() => setShowSettingsDialog(true)}>
                                    <SettingsIcon className="size-4 mr-2" />
                                    设置
                                </DropdownMenuItem>
                                <DropdownMenuItem
                                    onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
                                >
                                    {theme === 'dark' ? (
                                        <SunIcon className="size-4 mr-2" />
                                    ) : (
                                        <MoonIcon className="size-4 mr-2" />
                                    )}
                                    {theme === 'dark' ? '浅色模式' : '深色模式'}
                                </DropdownMenuItem>
                            </DropdownMenuContent>
                        </DropdownMenu>
                    </>
                ) : (
                    <>
                        <Button
                            size={'sm'}
                            variant="ghost"
                            onClick={() => setShowSettingsDialog(true)}
                        >
                            <SettingsIcon size={30} />
                        </Button>
                        <ThemeButton />
                        <UserMenu />
                    </>
                )}
            </div>
        </motion.div>
    )
}
