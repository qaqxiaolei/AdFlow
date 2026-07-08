import { Session } from '@/types/types'
import { PlusIcon, ChevronDown } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '../ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../ui/select'
import { Input } from '../ui/input'
import { useState } from 'react'
import { renameChatSession } from '@/api/chat'
import { getCanvas } from '@/api/canvas'

type SessionSelectorProps = {
  session: Session | null
  sessionList: Session[]
  onSelectSession: (sessionId: string) => void
  onClickNewChat: () => void
  canvasId: string
  onSetSessionList: (sessions: Session[]) => void
}

const SessionSelector: React.FC<SessionSelectorProps> = ({
  session,
  sessionList,
  onSelectSession,
  onClickNewChat,
  canvasId,
  onSetSessionList,
}) => {
  const { t } = useTranslation()
  const [isEditing, setIsEditing] = useState(false)
  const [editValue, setEditValue] = useState('')
  const [isSaving, setIsSaving] = useState(false)

  const refreshSessions = async () => {
    try {
      const canvasData = await getCanvas(canvasId)
      if (canvasData && canvasData.sessions) {
        onSetSessionList(canvasData.sessions)
      }
    } catch (error) {
      console.error('Failed to refresh sessions:', error)
    }
  }

  const getSessionTitle = (s: Session) => {
    return s.title || '未命名'
  }

  const handleStartEdit = (e: React.MouseEvent) => {
    e.stopPropagation()
    if (session) {
      setEditValue(getSessionTitle(session))
      setIsEditing(true)
    }
  }

  const handleSaveEdit = async () => {
    if (session && editValue.trim()) {
      setIsSaving(true)
      try {
        await renameChatSession(session.id, editValue.trim())
        await refreshSessions()
        setEditValue('')
      } catch (error) {
        console.error('Failed to rename session:', error)
      } finally {
        setIsSaving(false)
      }
    }
    setIsEditing(false)
  }

  const handleCancelEdit = () => {
    setIsEditing(false)
    setEditValue('')
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSaveEdit()
    } else if (e.key === 'Escape') {
      handleCancelEdit()
    }
  }

  return (
    <div className="flex items-center gap-2 w-full">
      {sessionList && sessionList.length > 0 ? (
        <div className="flex-1 flex items-center">
          {isEditing && session ? (
            <div className="flex items-center gap-2 w-full">
              <Input
                value={editValue}
                onChange={(e) => setEditValue(e.target.value)}
                onKeyDown={handleKeyDown}
                className="flex-1"
                autoFocus
                disabled={isSaving}
              />
              <Button
                variant="ghost"
                size="icon"
                onClick={handleSaveEdit}
                className="h-8 w-8 text-green-600"
                disabled={isSaving}
              >
                {isSaving ? (
                  <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                ) : (
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
                )}
              </Button>
              <Button
                variant="ghost"
                size="icon"
                onClick={handleCancelEdit}
                className="h-8 w-8 text-red-600"
                disabled={isSaving}
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
              </Button>
            </div>
          ) : (
            <div className="flex-1 relative">
              <Select
                value={session?.id}
                onValueChange={(value) => {
                  onSelectSession(value)
                  setIsEditing(false)
                }}
              >
                <SelectTrigger className="w-full bg-background">
                  <SelectValue placeholder="未命名" />
                </SelectTrigger>
                <SelectContent>
                  {sessionList
                    ?.filter((session) => session.id && session.id.trim() !== '')
                    ?.map((session) => (
                      <SelectItem key={session.id} value={session.id}>
                        {getSessionTitle(session)}
                      </SelectItem>
                    ))}
                </SelectContent>
              </Select>
              <Button
                variant="ghost"
                size="icon"
                onClick={handleStartEdit}
                className="absolute right-2 top-1/2 -translate-y-1/2 h-6 w-6 text-muted-foreground hover:text-foreground"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"></path></svg>
              </Button>
            </div>
          )}
        </div>
      ) : (
        <div className="flex-1 min-w-0 bg-background border border-border rounded-md px-3 py-2 text-muted-foreground text-sm">
          {t('chat:noChatSessions') || 'No Chat Sessions'}
        </div>
      )}

      <Button
        variant={'outline'}
        onClick={onClickNewChat}
        className="shrink-0 gap-1"
      >
        <PlusIcon />
        <span className="text-sm">{t('chat:newChat')}</span>
      </Button>
    </div>
  )
}

export default SessionSelector
