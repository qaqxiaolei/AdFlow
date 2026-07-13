import ChatInterface from '@/components/chat/Chat'
import TopMenu from '@/components/TopMenu'
import { Session } from '@/types/types'
import { createFileRoute, useParams, useSearch } from '@tanstack/react-router'
import { useEffect, useState } from 'react'

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

    useEffect(() => {
        const fetchSessions = async () => {
            try {
                const response = await fetch('/api/canvas/' + id)
                const data = await response.json()
                if (data.sessions) {
                    setSessionList(data.sessions)
                }
            } catch (error) {
                console.error('Failed to fetch sessions:', error)
            }
        }
        fetchSessions()
    }, [id])

    return (
        <div className='flex flex-col h-svh md:h-dvh min-h-0 overflow-hidden'>
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
