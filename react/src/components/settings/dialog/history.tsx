import { listCanvases } from '@/api/canvas'
import CanvasCard from '@/components/home/CanvasCard'
import { useAuth } from '@/contexts/AuthContext'
import { useConfigs } from '@/contexts/configs'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { AnimatePresence, motion } from 'motion/react'
import { useTranslation } from 'react-i18next'

const SettingHistory = () => {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { setShowSettingsDialog } = useConfigs()
  const { authStatus } = useAuth()
  const userId = authStatus.user_info?.id

  const { data: canvases, refetch, isLoading } = useQuery({
    queryKey: ['canvases', userId, 'history'],
    // 不传 limit，拉取当前账号全部历史项目
    queryFn: () => listCanvases(),
    enabled: !!userId,
    refetchOnMount: 'always',
    refetchInterval: (query) => {
      const items = query.state.data
      if (items?.some((canvas) => !canvas.thumbnail)) {
        return 3000
      }
      return false
    },
  })

  const handleCanvasClick = (id: string, sessionId: string) => {
    setShowSettingsDialog(false)
    navigate({
      to: '/canvas/$id',
      params: { id },
      search: sessionId ? { sessionId } : {},
    })
  }

  if (!userId) {
    return (
      <div className="flex flex-col gap-4 p-4 sm:p-6">
        <h2 className="text-2xl font-bold">{t('settings:history.title')}</h2>
        <p className="text-sm text-muted-foreground">
          {t('settings:history.loginRequired')}
        </p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4 p-4 sm:p-6 w-full pb-10">
      <motion.span
        className="text-2xl font-bold"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        {t('settings:history.title')}
      </motion.span>

      {isLoading && (
        <p className="text-sm text-muted-foreground">
          {t('settings:history.loading')}
        </p>
      )}

      {!isLoading && (!canvases || canvases.length === 0) && (
        <p className="text-sm text-muted-foreground">
          {t('settings:history.empty')}
        </p>
      )}

      <AnimatePresence>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4 w-full">
          {canvases?.map((canvas, index) => (
            <CanvasCard
              key={canvas.id}
              index={index}
              canvas={canvas}
              handleCanvasClick={() =>
                handleCanvasClick(canvas.id, canvas.session_id || '')
              }
              handleDeleteCanvas={() => refetch()}
            />
          ))}
        </div>
      </AnimatePresence>
    </div>
  )
}

export default SettingHistory
