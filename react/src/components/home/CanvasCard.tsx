import { deleteCanvas, ListCanvasesResponse } from '@/api/canvas'
import { DEFAULT_CANVAS_COVER_URL } from '@/constants'
import { Trash2 } from 'lucide-react'
import { motion } from 'motion/react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { Button } from '../ui/button'
import { formatDate } from '@/utils/formatDate'
import CanvasDeleteDialog from './CanvasDeleteDialog'

type CanvasCardProps = {
    index: number
    canvas: ListCanvasesResponse
    handleCanvasClick: (id: string) => void
    handleDeleteCanvas: () => void
}

function DefaultCanvasCover({ name }: { name: string }) {
    return (
        <div className="w-full h-40 rounded-lg overflow-hidden bg-gradient-to-br from-violet-100 via-purple-50 to-orange-50 dark:from-violet-950/50 dark:via-purple-950/30 dark:to-orange-950/20 flex items-center justify-center">
            <img
                src={DEFAULT_CANVAS_COVER_URL}
                alt={name}
                className="w-14 h-14 object-contain opacity-90"
                draggable={false}
            />
        </div>
    )
}

const CanvasCard: React.FC<CanvasCardProps> = ({
    index,
    canvas,
    handleCanvasClick,
    handleDeleteCanvas,
}) => {
    const { t } = useTranslation()
    const [showDeleteDialog, setShowDeleteDialog] = useState(false)
    const [thumbnailError, setThumbnailError] = useState(false)

    const showDefaultCover = !canvas.thumbnail || thumbnailError

    const handleDelete = async () => {
        try {
            await deleteCanvas(canvas.id)
            handleDeleteCanvas()
            toast.success(t('canvas:messages.canvasDeleted'))
        } catch (error) {
            toast.error(t('canvas:messages.failedToDelete'))
        }
        setShowDeleteDialog(false)
    }

    return (
        <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5, delay: index * 0.1 }}
            className="border border-primary/20 rounded-xl cursor-pointer hover:border-primary/40 transition-all duration-300 hover:shadow-md hover:bg-primary/5 active:scale-99 relative group"
        >
            <CanvasDeleteDialog
                show={showDeleteDialog}
                setShow={setShowDeleteDialog}
                handleDeleteCanvas={handleDelete}
            >
                <Button
                    variant="secondary"
                    size="icon"
                    className="absolute top-3 right-3 sm:top-4 sm:right-4 opacity-100 sm:opacity-0 sm:group-hover:opacity-100 transition-opacity duration-300 z-10"
                >
                    <Trash2 className="w-4 h-4" />
                </Button>
            </CanvasDeleteDialog>

            <div
                className="p-3 flex flex-col gap-2"
                onClick={() => handleCanvasClick(canvas.id)}
            >
                {showDefaultCover ? (
                    <DefaultCanvasCover name={canvas.name} />
                ) : (
                    <img
                        src={canvas.thumbnail}
                        alt={canvas.name}
                        className="w-full h-40 object-cover rounded-lg bg-muted"
                        onError={() => setThumbnailError(true)}
                    />
                )}
                <div className="flex flex-col">
                    <h3 className="text-lg font-bold truncate">{canvas.name}</h3>
                    <p className="text-sm text-gray-500">{formatDate(canvas.created_at)}</p>
                </div>
            </div>
        </motion.div>
    )
}

export default CanvasCard
