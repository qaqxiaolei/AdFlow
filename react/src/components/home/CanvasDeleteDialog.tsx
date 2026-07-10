import CommonDialogContent from '@/components/common/DialogContent'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { MobileBottomSheet } from '@/components/ui/mobile-bottom-sheet'
import { useIsMobile } from '@/hooks/use-mobile'
import { Trash2 } from 'lucide-react'
import React from 'react'
import { useTranslation } from 'react-i18next'

type CanvasDeleteDialogProps = {
  show: boolean
  className?: string
  children?: React.ReactNode
  setShow: (show: boolean) => void
  handleDeleteCanvas: () => void
}

const CanvasDeleteDialog: React.FC<CanvasDeleteDialogProps> = ({
  show,
  className,
  children,
  setShow,
  handleDeleteCanvas,
}) => {
  const { t } = useTranslation()
  const isMobile = useIsMobile()

  const trigger = children ?? (
    <Button variant="destructive" size="icon" className={className}>
      <Trash2 className="w-4 h-4" />
    </Button>
  )

  const openDialog = (event: React.MouseEvent) => {
    event.stopPropagation()
    setShow(true)
  }

  const mobileTrigger = React.isValidElement(trigger)
    ? React.cloneElement(
        trigger as React.ReactElement<{ onClick?: (event: React.MouseEvent) => void }>,
        {
          onClick: (event: React.MouseEvent) => {
            openDialog(event)
            ;(
              trigger as React.ReactElement<{ onClick?: (event: React.MouseEvent) => void }>
            ).props.onClick?.(event)
          },
        }
      )
    : trigger

  const actionButtons = (
    <div className={isMobile ? 'grid grid-cols-2 gap-2.5 pt-1' : 'contents'}>
      <Button
        variant="outline"
        className={isMobile ? 'h-11 touch-manipulation' : undefined}
        onClick={() => setShow(false)}
      >
        {t('canvas:deleteDialog.cancel')}
      </Button>
      <Button
        variant="destructive"
        className={isMobile ? 'h-11 touch-manipulation' : undefined}
        onClick={() => handleDeleteCanvas()}
      >
        {t('canvas:deleteDialog.delete')}
      </Button>
    </div>
  )

  if (isMobile) {
    return (
      <>
        {mobileTrigger}
        <MobileBottomSheet
          open={show}
          onOpenChange={setShow}
          title={t('canvas:deleteDialog.title')}
        >
          <p className="text-xs text-muted-foreground leading-relaxed mb-3">
            {t('canvas:deleteDialog.description')}
          </p>
          {actionButtons}
        </MobileBottomSheet>
      </>
    )
  }

  return (
    <Dialog open={show} onOpenChange={setShow}>
      <DialogTrigger asChild onClick={openDialog}>
        {trigger}
      </DialogTrigger>

      <CommonDialogContent open={show}>
        <DialogHeader>
          <DialogTitle>{t('canvas:deleteDialog.title')}</DialogTitle>
        </DialogHeader>

        <DialogDescription>
          {t('canvas:deleteDialog.description')}
        </DialogDescription>

        <DialogFooter>{actionButtons}</DialogFooter>
      </CommonDialogContent>
    </Dialog>
  )
}

export default CanvasDeleteDialog
