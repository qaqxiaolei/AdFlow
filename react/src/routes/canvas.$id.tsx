import ChatInterface from '@/components/chat/Chat'
import TopMenu from '@/components/TopMenu'
import { getCanvas } from '@/api/canvas'
import { useAuth } from '@/contexts/AuthContext'
import { Session } from '@/types/types'
import {
  createFileRoute,
  useNavigate,
  useParams,
  useSearch,
} from '@tanstack/react-router'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'

export const Route = createFileRoute('/canvas/$id')({
  component: Canvas,
})

function Canvas() {
  const { id } = useParams({ from: '/canvas/$id' })
  const [sessionList, setSessionList] = useState<Session[]>([])
  const search = useSearch({ from: '/canvas/$id' }) as {
    sessionId: string
  }
  const searchSessionId = search?.sessionId || ''
  const { authStatus, isLoading, openAuthDialog } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    if (isLoading) return
    if (!authStatus.is_logged_in) {
      openAuthDialog()
      navigate({ to: '/' })
      return
    }

    const fetchSessions = async () => {
      try {
        const data = await getCanvas(id)
        if (data.sessions) {
          setSessionList(data.sessions)
        }
      } catch (error) {
        console.error('Failed to fetch sessions:', error)
        toast.error(
          error instanceof Error ? error.message : '无法加载项目'
        )
        navigate({ to: '/' })
      }
    }
    fetchSessions()
  }, [id, authStatus.is_logged_in, isLoading, openAuthDialog, navigate])

  return (
    <div className="flex flex-col h-svh md:h-dvh min-h-0 overflow-hidden">
      <TopMenu />
      <ChatInterface
        canvasId={id}
        sessionList={sessionList}
        setSessionList={setSessionList}
        sessionId={searchSessionId}
      />
    </div>
  )
}
