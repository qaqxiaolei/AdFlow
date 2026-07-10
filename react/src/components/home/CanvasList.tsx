import { listCanvases } from '@/api/canvas'
import CanvasCard from '@/components/home/CanvasCard'
import { useQuery } from '@tanstack/react-query'
import { useNavigate, useLocation } from '@tanstack/react-router'
import { AnimatePresence, motion } from 'motion/react'
import { memo } from 'react'
import { useTranslation } from 'react-i18next'
import { useConfigs } from '@/contexts/configs'

const CanvasList: React.FC = () => {
    const { t } = useTranslation()
    const location = useLocation()
    const isHomePage = location.pathname === '/'
    const { initCanvas, setInitCanvas } = useConfigs()

    const { data: canvases, refetch } = useQuery({
        queryKey: ['canvases'],
        queryFn: listCanvases,
        enabled: isHomePage, // 每次进入首页时都重新查询
        refetchOnMount: 'always',
    })

    const navigate = useNavigate()
    const handleCanvasClick = (id: string, sessionId: string) => {
        navigate({
            to: '/canvas/$id',
            params: { id },
            search: sessionId ? { sessionId } : {}
        })
    }

    return (
        <div className="flex flex-col px-4 sm:px-6 lg:px-10 mt-6 sm:mt-10 gap-4 select-none max-w-[1200px] mx-auto w-full">
            {canvases && canvases.length > 0 && (
                <motion.span
                    className="text-2xl font-bold"
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.5 }}
                >
                    {t('home:allProjects')}
                </motion.span>
            )}
            <AnimatePresence>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3 sm:gap-4 w-full pb-6 sm:pb-10">
                    {canvases?.map((canvas, index) => (
                        <CanvasCard
                            key={canvas.id}
                            index={index}
                            canvas={canvas}
                            handleCanvasClick={() => handleCanvasClick(canvas.id, canvas.session_id)}
                            handleDeleteCanvas={() => refetch()}
                        />
                    ))}
                </div>
            </AnimatePresence>
        </div>
    )
}

export default memo(CanvasList)
