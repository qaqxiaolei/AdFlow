import { sendMessages, getChatSessionStatus, getChatSession } from '@/api/chat'
import Blur from '@/components/common/Blur'
import { ScrollArea } from '@/components/ui/scroll-area'
import { eventBus, TEvents } from '@/lib/event'
import ChatMagicGenerator from './ChatMagicGenerator'
import {
    AssistantMessage,
    Message,
    Model,
    PendingType,
    Session,
} from '@/types/types'
import { useSearch } from '@tanstack/react-router'
import { produce } from 'immer'
import { AnimatePresence, motion } from 'motion/react'
import { nanoid } from 'nanoid'
import {
    Dispatch,
    SetStateAction,
    useCallback,
    useEffect,
    useRef,
    useState,
} from 'react'
import { useTranslation } from 'react-i18next'
import { PhotoProvider } from 'react-photo-view'
import { toast } from 'sonner'
import ShinyText from '../ui/shiny-text'
import ChatTextarea from './ChatTextarea'
import MessageRegular from './Message/Regular'
import { ToolCallContent } from './Message/ToolCallContent'
import ToolCallTag from './Message/ToolCallTag'
import SessionSelector from './SessionSelector'
import ChatSpinner from './Spinner'
import ToolcallProgressUpdate from './ToolcallProgressUpdate'
import { useConfigs } from '@/contexts/configs'
import 'react-photo-view/dist/react-photo-view.css'
import { DEFAULT_SYSTEM_PROMPT } from '@/constants'
import { ModelInfo, ToolInfo } from '@/api/model'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/contexts/AuthContext'
import { useQueryClient } from '@tanstack/react-query'
import MixedContent, { MixedContentImages, MixedContentText } from './Message/MixedContent'
import { ChevronDown, ChevronUp } from 'lucide-react'


type ChatInterfaceProps = {
    canvasId: string
    sessionList: Session[]
    setSessionList: Dispatch<SetStateAction<Session[]>>
    sessionId: string
}

const VIDEO_MARKDOWN_RE =
    /!\[[^\]]*(?:video_id:)?[^\]]*\]\(([^)]+\.(?:mp4|webm|mov)(?:\?[^)]*)?|\/api\/file\/vi_[^)]+)\)/gi
const VIDEO_URL_RE = /(?:\.mp4|\.webm|\.mov)(?:\?|$)|\/api\/file\/vi_/i

function countSessionVideos(messages: Message[]): number {
    const urls = new Set<string>()

    const collectFromText = (text: string) => {
        VIDEO_MARKDOWN_RE.lastIndex = 0
        let match: RegExpExecArray | null
        while ((match = VIDEO_MARKDOWN_RE.exec(text)) !== null) {
            urls.add(match[1])
        }
        // Fallback: bare video urls in content
        if (VIDEO_URL_RE.test(text)) {
            const bare = text.match(
                /(?:https?:\/\/[^\s)]+|\/api\/file\/vi_[^\s)]+|\S+\.(?:mp4|webm|mov)(?:\?[^\s)]*)?)/gi
            )
            bare?.forEach((url) => {
                if (VIDEO_URL_RE.test(url)) urls.add(url)
            })
        }
    }

    for (const message of messages) {
        if (message.role === 'tool') continue
        const content = message.content
        if (!content) continue
        if (typeof content === 'string') {
            collectFromText(content)
        } else if (Array.isArray(content)) {
            for (const part of content) {
                if (part.type === 'text' && part.text) {
                    collectFromText(part.text)
                }
            }
        }
    }

    return urls.size
}

const ChatInterface: React.FC<ChatInterfaceProps> = ({
    canvasId,
    sessionList,
    setSessionList,
    sessionId: searchSessionId,
}) => {
    const { t } = useTranslation()
    const [session, setSession] = useState<Session | null>(null)
    const { initCanvas, setInitCanvas } = useConfigs()
    const { authStatus } = useAuth()
    const queryClient = useQueryClient()

    useEffect(() => {
        if (sessionList.length > 0) {
            let _session = null
            if (searchSessionId) {
                _session = sessionList.find((s) => s.id === searchSessionId) || null
            } else {
                _session = sessionList[0]
            }
            setSession(_session)
        } else {
            setSession(null)
        }
    }, [sessionList, searchSessionId])
    const [messages, setMessages] = useState<Message[]>([])
    const [pending, setPending] = useState<PendingType>(
        initCanvas ? 'text' : false
    )
    const [initialProgress, setInitialProgress] = useState('')
    const [inputExpanded, setInputExpanded] = useState(true)
    const mergedToolCallIds = useRef<string[]>([])
    const sessionId = session?.id ?? searchSessionId

    const sessionVideoCount = countSessionVideos(messages)
    const bothVideosReady = sessionVideoCount >= 2
    const showChatInput = !bothVideosReady || inputExpanded

    // After both videos finish, collapse the input by default.
    useEffect(() => {
        if (bothVideosReady) {
            setInputExpanded(false)
        } else {
            setInputExpanded(true)
        }
    }, [bothVideosReady, sessionId])

    const sessionIdRef = useRef<string>(session?.id || nanoid())
    const [expandingToolCalls, setExpandingToolCalls] = useState<string[]>([])
    const [pendingToolConfirmations, setPendingToolConfirmations] = useState<
        string[]
    >([])
    const scrollRef = useRef<HTMLDivElement>(null)
    const isAtBottomRef = useRef(false)
    const visibilityRestoreTimerRef = useRef<number | null>(null)
    const scrollToBottom = useCallback(() => {
        if (!isAtBottomRef.current) {
            return
        }
        setTimeout(() => {
            scrollRef.current?.scrollTo({
                top: scrollRef.current!.scrollHeight,
                behavior: 'smooth',
            })
        }, 200)
    }, [])

    const mergeToolCallResult = (messages: Message[]) => {
        const messagesWithToolCallResult = messages.map((message, index) => {
            if (message.role === 'assistant' && message.tool_calls) {
                for (const toolCall of message.tool_calls) {
                    // From the next message, find the tool call result
                    for (let i = index + 1; i < messages.length; i++) {
                        const nextMessage = messages[i]
                        if (
                            nextMessage.role === 'tool' &&
                            nextMessage.tool_call_id === toolCall.id
                        ) {
                            toolCall.result = nextMessage.content
                            mergedToolCallIds.current.push(toolCall.id)
                        }
                    }
                }
            }
            return message
        })
        return messagesWithToolCallResult
    }

    const hasIncompleteToolCalls = (messages: Message[]) => {
        for (const message of messages) {
            if (message.role !== 'assistant' || !message.tool_calls) {
                continue
            }
            for (const toolCall of message.tool_calls) {
                if (!toolCall.result) {
                    return true
                }
            }
        }
        return false
    }

    const restoreSessionStatus = useCallback(
        async (sid: string, msgs: Message[]) => {
            try {
                const status = await getChatSessionStatus(sid)
                if (status.running) {
                    const pendingType: PendingType =
                        status.pending_type === 'text' ||
                        status.pending_type === 'image' ||
                        status.pending_type === 'tool'
                            ? status.pending_type
                            : 'tool'
                    setPending(pendingType)
                    if (status.last_progress) {
                        setInitialProgress(status.last_progress)
                    }
                    return
                }
                if (hasIncompleteToolCalls(msgs)) {
                    setPending('tool')
                }
            } catch (error) {
                console.error('Failed to restore session status:', error)
                if (hasIncompleteToolCalls(msgs)) {
                    setPending('tool')
                }
            }
        },
        []
    )

    const handleDelta = useCallback(
        (data: TEvents['Socket::Session::Delta']) => {
            if (data.session_id && data.session_id !== sessionId) {
                return
            }
            setPending('text')
            setMessages(
                produce((prev) => {
                    const last = prev.at(-1)
                    if (
                        last?.role === 'assistant' &&
                        last.content != null &&
                        last.tool_calls == null
                    ) {
                        if (typeof last.content === 'string') {
                            last.content += data.text
                        } else if (
                            last.content &&
                            last.content.at(-1) &&
                            last.content.at(-1)!.type === 'text'
                        ) {
                            ; (last.content.at(-1) as { text: string }).text += data.text
                        }
                    } else {
                        prev.push({
                            role: 'assistant',
                            content: data.text,
                        })
                    }
                })
            )
            scrollToBottom()
        },
        [sessionId, scrollToBottom]
    )

    const handleToolCall = useCallback(
        (data: TEvents['Socket::Session::ToolCall']) => {
            if (data.session_id && data.session_id !== sessionId) {
                return
            }
            const existToolCall = messages.find(
                (m) =>
                    m.role === 'assistant' &&
                    m.tool_calls &&
                    m.tool_calls.find((t) => t.id == data.id)
            )
            if (existToolCall) {
                return
            }
            setMessages(
                produce((prev) => {
                    console.log('👇tool_call event get', data)
                    setPending('tool')
                    prev.push({
                        role: 'assistant',
                        content: '',
                        tool_calls: [
                            {
                                type: 'function',
                                function: {
                                    name: data.name,
                                    arguments: '',
                                },
                                id: data.id,
                            },
                        ],
                    })
                })
            )
            setExpandingToolCalls(
                produce((prev) => {
                    prev.push(data.id)
                })
            )
        },
        [sessionId]
    )

    const handleToolCallPendingConfirmation = useCallback(
        (data: TEvents['Socket::Session::ToolCallPendingConfirmation']) => {
            if (data.session_id && data.session_id !== sessionId) {
                return
            }
            const existToolCall = messages.find(
                (m) =>
                    m.role === 'assistant' &&
                    m.tool_calls &&
                    m.tool_calls.find((t) => t.id == data.id)
            )
            if (existToolCall) {
                return
            }
            setMessages(
                produce((prev) => {
                    console.log('👇tool_call_pending_confirmation event get', data)
                    setPending('tool')
                    prev.push({
                        role: 'assistant',
                        content: '',
                        tool_calls: [
                            {
                                type: 'function',
                                function: {
                                    name: data.name,
                                    arguments: data.arguments,
                                },
                                id: data.id,
                            },
                        ],
                    })
                })
            )
            setPendingToolConfirmations(
                produce((prev) => {
                    prev.push(data.id)
                })
            )
            // 自动展开需要确认的工具调用
            setExpandingToolCalls(
                produce((prev) => {
                    if (!prev.includes(data.id)) {
                        prev.push(data.id)
                    }
                })
            )
        },
        [sessionId]
    )

    const handleToolCallConfirmed = useCallback(
        (data: TEvents['Socket::Session::ToolCallConfirmed']) => {
            if (data.session_id && data.session_id !== sessionId) {
                return
            }
            setPendingToolConfirmations(
                produce((prev) => {
                    return prev.filter((id) => id !== data.id)
                })
            )
            setExpandingToolCalls(
                produce((prev) => {
                    if (!prev.includes(data.id)) {
                        prev.push(data.id)
                    }
                })
            )
        },
        [sessionId]
    )

    const handleToolCallCancelled = useCallback(
        (data: TEvents['Socket::Session::ToolCallCancelled']) => {
            if (data.session_id && data.session_id !== sessionId) {
                return
            }
            setPendingToolConfirmations(
                produce((prev) => {
                    return prev.filter((id) => id !== data.id)
                })
            )
            // 更新工具调用的状态
            setMessages(
                produce((prev) => {
                    prev.forEach((msg) => {
                        if (msg.role === 'assistant' && msg.tool_calls) {
                            msg.tool_calls.forEach((tc) => {
                                if (tc.id === data.id) {
                                    // 添加取消状态标记
                                    tc.result = '工具调用已取消'
                                }
                            })
                        }
                    })
                })
            )
        },
        [sessionId]
    )

    const handleToolCallArguments = useCallback(
        (data: TEvents['Socket::Session::ToolCallArguments']) => {
            if (data.session_id && data.session_id !== sessionId) {
                return
            }
            setMessages(
                produce((prev) => {
                    setPending('tool')
                    const lastMessage = prev.find(
                        (m) =>
                            m.role === 'assistant' &&
                            m.tool_calls &&
                            m.tool_calls.find((t) => t.id == data.id)
                    ) as AssistantMessage

                    if (lastMessage) {
                        const toolCall = lastMessage.tool_calls!.find(
                            (t) => t.id == data.id
                        )
                        if (toolCall) {
                            // 检查是否是待确认的工具调用，如果是则跳过参数追加
                            if (pendingToolConfirmations.includes(data.id)) {
                                return
                            }
                            toolCall.function.arguments += data.text
                        }
                    }
                })
            )
            scrollToBottom()
        },
        [sessionId, scrollToBottom, pendingToolConfirmations]
    )

    const handleToolCallResult = useCallback(
        (data: TEvents['Socket::Session::ToolCallResult']) => {
            console.log('😘🖼️tool_call_result event get', data)
            if (data.session_id && data.session_id !== sessionId) {
                return
            }
            // TODO: support other non string types of returning content like image_url
            if (data.message.content) {
                setMessages(
                    produce((prev) => {
                        prev.forEach((m) => {
                            if (m.role === 'assistant' && m.tool_calls) {
                                m.tool_calls.forEach((t) => {
                                    if (t.id === data.id) {
                                        t.result = data.message.content
                                    }
                                })
                            }
                        })
                    })
                )
            }
        },
        [canvasId, sessionId]
    )

    const handleToolCallProgress = useCallback(
        (data: TEvents['Socket::Session::ToolCallProgress']) => {
            if (data.session_id && data.session_id !== sessionId) {
                return
            }
            setPending('tool')
        },
        [sessionId]
    )

    const handleVideoGenerationStarted = useCallback(
        (data: TEvents['Socket::Session::VideoGenerationStarted']) => {
            if (data.session_id && data.session_id !== sessionId) {
                return
            }
            setPending('tool')
            if (data.message) {
                setInitialProgress(data.message)
            }
        },
        [sessionId]
    )

    const handleImageGenerated = useCallback(
        (data: TEvents['Socket::Session::ImageGenerated']) => {
            if (
                data.canvas_id &&
                data.canvas_id !== canvasId &&
                data.session_id !== sessionId
            ) {
                return
            }
            console.log('⭐️dispatching image_generated', data)
            setPending('image')
        },
        [canvasId, sessionId]
    )

    const handleVideoGenerated = useCallback(
        (data: TEvents['Socket::Session::VideoGenerated']) => {
            if (data.session_id && data.session_id !== sessionId) {
                return
            }
            const videoUrl = data.video_url || data.file?.dataURL
            if (!videoUrl) {
                return
            }

            setMessages(
                produce((prev) => {
                    const duplicate = prev.some(
                        (m) =>
                            m.role === 'assistant' &&
                            typeof m.content === 'string' &&
                            m.content.includes(videoUrl)
                    )
                    if (duplicate) {
                        return
                    }

                    prev.push({
                        role: 'assistant',
                        content: `![video_id: generated](${videoUrl})`,
                    })
                })
            )
            setPending('tool')
            scrollToBottom()
        },
        [sessionId, scrollToBottom]
    )

    const handleAllMessages = useCallback(
        (data: TEvents['Socket::Session::AllMessages']) => {
            if (data.session_id && data.session_id !== sessionId) {
                return
            }
            setMessages(() => {
                console.log('👇all_messages', data.messages)
                return data.messages
            })
            setMessages(mergeToolCallResult(data.messages))
            scrollToBottom()
        },
        [sessionId, scrollToBottom]
    )

    const handleDone = useCallback(
        (data: TEvents['Socket::Session::Done']) => {
            if (data.session_id && data.session_id !== sessionId) {
                return
            }
            setPending(false)
            setInitialProgress('')
            scrollToBottom()

            // 聊天输出完毕后更新余额
            if (authStatus.is_logged_in) {
                queryClient.invalidateQueries({ queryKey: ['balance'] })
            }
        },
        [sessionId, scrollToBottom, authStatus.is_logged_in, queryClient]
    )

    const handleError = useCallback((data: TEvents['Socket::Session::Error']) => {
        setPending(false)
        setInitialProgress('')
        // 视频生成类错误已在对话中由 AI 说明，不再弹红色阻断提示
        if (
            /视频生成|video generation/i.test(data.error) &&
            /超时|较长|稍后重试|过于频繁|failed/i.test(data.error)
        ) {
            return
        }
        toast.error('Error: ' + data.error, {
            closeButton: true,
            duration: 3600 * 1000,
            style: { color: 'red' },
        })
    }, [])

    const handleInfo = useCallback((data: TEvents['Socket::Session::Info']) => {
        toast.info(data.info, {
            closeButton: true,
            duration: 10 * 1000,
        })
    }, [])

    useEffect(() => {
        const handleScroll = () => {
            if (scrollRef.current) {
                isAtBottomRef.current =
                    scrollRef.current.scrollHeight - scrollRef.current.scrollTop <=
                    scrollRef.current.clientHeight + 1
            }
        }
        const scrollEl = scrollRef.current
        scrollEl?.addEventListener('scroll', handleScroll)

        eventBus.on('Socket::Session::Delta', handleDelta)
        eventBus.on('Socket::Session::ToolCall', handleToolCall)
        eventBus.on(
            'Socket::Session::ToolCallPendingConfirmation',
            handleToolCallPendingConfirmation
        )
        eventBus.on('Socket::Session::ToolCallConfirmed', handleToolCallConfirmed)
        eventBus.on('Socket::Session::ToolCallCancelled', handleToolCallCancelled)
        eventBus.on('Socket::Session::ToolCallArguments', handleToolCallArguments)
        eventBus.on('Socket::Session::ToolCallResult', handleToolCallResult)
        eventBus.on('Socket::Session::ToolCallProgress', handleToolCallProgress)
        eventBus.on(
            'Socket::Session::VideoGenerationStarted',
            handleVideoGenerationStarted
        )
        eventBus.on('Socket::Session::ImageGenerated', handleImageGenerated)
        eventBus.on('Socket::Session::VideoGenerated', handleVideoGenerated)
        eventBus.on('Socket::Session::AllMessages', handleAllMessages)
        eventBus.on('Socket::Session::Done', handleDone)
        eventBus.on('Socket::Session::Error', handleError)
        eventBus.on('Socket::Session::Info', handleInfo)
        return () => {
            scrollEl?.removeEventListener('scroll', handleScroll)

            eventBus.off('Socket::Session::Delta', handleDelta)
            eventBus.off('Socket::Session::ToolCall', handleToolCall)
            eventBus.off(
                'Socket::Session::ToolCallPendingConfirmation',
                handleToolCallPendingConfirmation
            )
            eventBus.off(
                'Socket::Session::ToolCallConfirmed',
                handleToolCallConfirmed
            )
            eventBus.off(
                'Socket::Session::ToolCallCancelled',
                handleToolCallCancelled
            )
            eventBus.off(
                'Socket::Session::ToolCallArguments',
                handleToolCallArguments
            )
            eventBus.off('Socket::Session::ToolCallResult', handleToolCallResult)
            eventBus.off(
                'Socket::Session::ToolCallProgress',
                handleToolCallProgress
            )
            eventBus.off(
                'Socket::Session::VideoGenerationStarted',
                handleVideoGenerationStarted
            )
            eventBus.off('Socket::Session::ImageGenerated', handleImageGenerated)
            eventBus.off('Socket::Session::VideoGenerated', handleVideoGenerated)
            eventBus.off('Socket::Session::AllMessages', handleAllMessages)
            eventBus.off('Socket::Session::Done', handleDone)
            eventBus.off('Socket::Session::Error', handleError)
            eventBus.off('Socket::Session::Info', handleInfo)
        }
    })

    // useCallback 用于缓存函数实例，避免组件每次重渲染时重复创建全新函数
    const initChat = useCallback(async () => {
        if (!sessionId) {
            return
        }
        sessionIdRef.current = sessionId
        setPending(false)
        setInitialProgress('')
        const data = await getChatSession(sessionId)
        const msgs = data?.length ? data : []
        const mergedMsgs = mergeToolCallResult(msgs)
        setMessages(mergedMsgs)
        if (msgs.length > 0) {
            setInitCanvas(false)
        }
        await restoreSessionStatus(sessionId, mergedMsgs)
        scrollToBottom()
    }, [sessionId, scrollToBottom, setInitCanvas, restoreSessionStatus])

    useEffect(() => {
        initChat()
    }, [sessionId, initChat])

    useEffect(() => {
        const handleVisibilityChange = () => {
            if (document.visibilityState !== 'visible' || !sessionId) {
                return
            }
            if (visibilityRestoreTimerRef.current) {
                window.clearTimeout(visibilityRestoreTimerRef.current)
            }
            visibilityRestoreTimerRef.current = window.setTimeout(() => {
                restoreSessionStatus(sessionId, messages)
            }, 1500)
        }
        document.addEventListener('visibilitychange', handleVisibilityChange)
        return () => {
            document.removeEventListener('visibilitychange', handleVisibilityChange)
            if (visibilityRestoreTimerRef.current) {
                window.clearTimeout(visibilityRestoreTimerRef.current)
            }
        }
    }, [sessionId, messages, restoreSessionStatus])

    const onSelectSession = (sessionId: string) => {
        setSession(sessionList.find((s) => s.id === sessionId) || null)
        window.history.pushState(
            {},
            '',
            `/canvas/${canvasId}?sessionId=${sessionId}`
        )
    }

    const onClickNewChat = () => {
        const newSession: Session = {
            id: nanoid(),
            title: t('chat:newChat'),
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            model: session?.model || 'gpt-4o',
            provider: session?.provider || 'openai',
        }

        setSessionList((prev) => [...prev, newSession])
        onSelectSession(newSession.id)
    }

    const onSendMessages = useCallback(
        (data: Message[], configs: { textModel: Model; toolList: ToolInfo[] }) => {
            setPending('text')
            setMessages(data)
            sendMessages({
                sessionId: sessionId!,
                canvasId: canvasId,
                newMessages: data,
                textModel: configs.textModel,
                toolList: configs.toolList,
                systemPrompt:
                    localStorage.getItem('system_prompt') || DEFAULT_SYSTEM_PROMPT,
            })
            if (searchSessionId !== sessionId) {
                window.history.pushState(
                    {},
                    '',
                    `/canvas/${canvasId}?sessionId=${sessionId}`
                )
            }
            scrollToBottom()
        },
        [canvasId, sessionId, searchSessionId, scrollToBottom]
    )

    const handleCancelChat = useCallback(() => {
        setPending(false)
    }, [])

    return (
        <PhotoProvider>
            <div className='flex flex-col flex-1 relative w-full min-h-0'>
                <div className='flex flex-col w-full flex-1 min-h-0 lg:mx-auto lg:w-[80%] lg:h-[calc(100vh-2rem-32px)] lg:rounded-2xl lg:shadow-xl lg:border lg:border-border overflow-hidden'>
                    <header className='flex items-center px-3 py-2 sm:px-4 sm:py-3 relative z-10 bg-background/80 backdrop-blur-sm border-b border-border/50'>
                        <div className='flex-1 min-w-0'>
                            <SessionSelector
                                session={session}
                                sessionList={sessionList}
                                onClickNewChat={onClickNewChat}
                                onSelectSession={onSelectSession}
                                canvasId={canvasId}
                                onSetSessionList={setSessionList}
                            />
                        </div>

                        <Blur className='absolute top-0 left-0 right-0 h-full -z-1' />
                    </header>

                    <ScrollArea className='flex-1 min-h-0' viewportRef={scrollRef}>
                        {messages.length > 0 ? (
                            <div className='flex flex-col flex-1 px-3 py-3 sm:px-4 sm:py-4'>
                                {messages.map((message, idx) => (
                                    <div key={`${idx}`} className='flex flex-col gap-3 sm:gap-4 mb-2'>
                                        {typeof message.content == 'string' &&
                                            (message.role !== 'tool' ? (
                                                <MessageRegular
                                                    message={message}
                                                    content={message.content}
                                                />
                                            ) : message.tool_call_id &&
                                                mergedToolCallIds.current.includes(
                                                    message.tool_call_id
                                                ) ? (
                                                <></>
                                            ) : (
                                                <ToolCallContent
                                                    expandingToolCalls={expandingToolCalls}
                                                    message={message}
                                                />
                                            ))}

                                        {Array.isArray(message.content) && (
                                            <>
                                                <MixedContentImages
                                                    contents={message.content}
                                                />
                                                <MixedContentText
                                                    message={message}
                                                    contents={message.content}
                                                />
                                            </>
                                        )}

                                        {message.role === 'assistant' &&
                                            message.tool_calls &&
                                            message.tool_calls.at(-1)?.function.name != 'finish' &&
                                            message.tool_calls.map((toolCall, i) => {
                                                return (
                                                    <ToolCallTag
                                                        key={toolCall.id}
                                                        toolCall={toolCall}
                                                        isExpanded={expandingToolCalls.includes(toolCall.id)}
                                                        onToggleExpand={() => {
                                                            if (expandingToolCalls.includes(toolCall.id)) {
                                                                setExpandingToolCalls((prev) =>
                                                                    prev.filter((id) => id !== toolCall.id)
                                                                )
                                                            } else {
                                                                setExpandingToolCalls((prev) => [
                                                                    ...prev,
                                                                    toolCall.id,
                                                                ])
                                                            }
                                                        }}
                                                        requiresConfirmation={pendingToolConfirmations.includes(
                                                            toolCall.id
                                                        )}
                                                        onConfirm={() => {
                                                            // 发送确认事件到后端
                                                            fetch('/api/tool_confirmation', {
                                                                method: 'POST',
                                                                headers: {
                                                                    'Content-Type': 'application/json',
                                                                },
                                                                body: JSON.stringify({
                                                                    session_id: sessionId,
                                                                    tool_call_id: toolCall.id,
                                                                    confirmed: true,
                                                                }),
                                                            })
                                                        }}
                                                        onCancel={() => {
                                                            // 发送取消事件到后端
                                                            fetch('/api/tool_confirmation', {
                                                                method: 'POST',
                                                                headers: {
                                                                    'Content-Type': 'application/json',
                                                                },
                                                                body: JSON.stringify({
                                                                    session_id: sessionId,
                                                                    tool_call_id: toolCall.id,
                                                                    confirmed: false,
                                                                }),
                                                            })
                                                        }}
                                                    />
                                                )
                                            })}
                                    </div>
                                ))}
                                {pending && <ChatSpinner pending={pending} />}
                                {(pending || initialProgress) && sessionId && (
                                    <ToolcallProgressUpdate
                                        sessionId={sessionId}
                                        initialProgress={initialProgress}
                                    />
                                )}
                            </div>
                        ) : (
                            <motion.div className='flex flex-col h-full p-6 items-center justify-center select-none'>
                                <motion.span
                                    initial={{ opacity: 0, y: 10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ duration: 0.5 }}
                                    className='text-muted-foreground text-2xl lg:text-3xl'
                                >
                                    <ShinyText text='Hello, Restaurant Owner!' />
                                </motion.span>
                                <motion.span
                                    initial={{ opacity: 0, y: 10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ duration: 0.6 }}
                                    className='text-muted-foreground text-lg lg:text-xl mt-2'
                                >
                                    <ShinyText text='How can I help you today?' />
                                </motion.span>
                            </motion.div>
                        )}
                    </ScrollArea>

                    <div className='relative shrink-0 px-3 py-2 sm:p-3 z-50 pb-[max(0.5rem,env(safe-area-inset-bottom))]'>
                        <div className='relative'>
                            {bothVideosReady && (
                                <Button
                                    type='button'
                                    variant='ghost'
                                    size='icon'
                                    className='absolute left-1/2 top-0 z-20 h-7 w-7 -translate-x-1/2 -translate-y-1/2 rounded-full border border-border bg-background shadow-sm touch-manipulation'
                                    aria-label={showChatInput ? '隐藏输入框' : '显示输入框'}
                                    onClick={() => setInputExpanded((prev) => !prev)}
                                >
                                    {showChatInput ? (
                                        <ChevronDown className='size-4' />
                                    ) : (
                                        <ChevronUp className='size-4' />
                                    )}
                                </Button>
                            )}

                            <AnimatePresence initial={false}>
                                {showChatInput ? (
                                    <motion.div
                                        key='chat-textarea'
                                        initial={{ opacity: 0, height: 0 }}
                                        animate={{ opacity: 1, height: 'auto' }}
                                        exit={{ opacity: 0, height: 0 }}
                                        transition={{ duration: 0.2, ease: 'easeInOut' }}
                                        className='overflow-hidden'
                                    >
                                        <ChatTextarea
                                            sessionId={sessionId!}
                                            pending={!!pending}
                                            messages={messages}
                                            onSendMessages={onSendMessages}
                                            onCancelChat={handleCancelChat}
                                        />
                                    </motion.div>
                                ) : (
                                    bothVideosReady && (
                                        <div
                                            key='chat-textarea-collapsed'
                                            className='h-0 border-t border-border'
                                            aria-hidden
                                        />
                                    )
                                )}
                            </AnimatePresence>
                        </div>

                        {/* 魔法生成组件 */}
                        <ChatMagicGenerator
                            sessionId={sessionId || ''}
                            canvasId={canvasId}
                            messages={messages}
                            setMessages={setMessages}
                            setPending={setPending}
                            scrollToBottom={scrollToBottom}
                        />
                    </div>
                </div>
            </div>
        </PhotoProvider>
    )
}

export default ChatInterface
