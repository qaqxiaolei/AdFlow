import { Message, MessageContent } from '@/types/types'
import { stripInternalMessageTags } from '@/utils/displayMessageText'
import { Markdown } from '../Markdown'
import MessageImage from './Image'

type MessageRegularProps = {
  message: Message
  content: MessageContent | string
}

const MessageRegular: React.FC<MessageRegularProps> = ({
  message,
  content,
}) => {
  const isStrContent = typeof content === 'string'
  const isText = isStrContent || (!isStrContent && content.type == 'text')

  const rawText = isStrContent
    ? content
    : content.type === 'text'
    ? content.text
    : ''
  const markdownText =
    message.role === 'user'
      ? stripInternalMessageTags(rawText)
      : rawText
  if (!isText) return <MessageImage content={content} />
  if (markdownText.includes('<hide_in_user_ui>')) {
    return null
  }

  return (
    <>
      {message.role === 'user' ? (
        <div className="flex justify-end mb-4 min-w-0 w-full">
          <div className="bg-primary text-primary-foreground rounded-xl rounded-br-md px-4 py-3 text-left max-w-[min(100%,20rem)] min-w-0 w-fit flex flex-col overflow-hidden break-words [overflow-wrap:anywhere]">
            <Markdown>{markdownText}</Markdown>
          </div>
        </div>
      ) : (
        <div className="text-gray-800 dark:text-gray-200 text-left items-start mb-4 flex flex-col">
          <Markdown>{markdownText}</Markdown>
        </div>
      )}
    </>
  )
}

export default MessageRegular
