import ChatInterface from '@/components/chat/Chat'
import TopMenu from '@/components/TopMenu'
import { Session } from '@/types/types'
import { createFileRoute, useParams, useSearch } from '@tanstack/react-router'
import { useState } from 'react'

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

    return (
        <div className='flex flex-col h-full'>
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
