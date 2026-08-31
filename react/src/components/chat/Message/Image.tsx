import { PhotoView } from 'react-photo-view'
import ChatVideo from './ChatVideo'
import { isProbablyVideoUrl } from '@/lib/resolveMediaUrl'

type MessageImageProps = {
    content: {
        image_url: {
            url: string
        }
        type: 'image_url'
    }
}

const MessageImage = ({ content }: MessageImageProps) => {
    const url = content.image_url.url
    if (isProbablyVideoUrl(url)) {
        return <ChatVideo src={url} />
    }

    return (
        <div className="w-full max-w-[140px]">
            <PhotoView src={url}>
                <div className="relative group cursor-pointer">
                    <img
                        className="w-full h-auto max-h-[140px] object-cover rounded-md border border-border hover:scale-105 transition-transform duration-300"
                        src={url}
                        alt="Image"
                    />
                </div>
            </PhotoView>
        </div>
    )
}

export default MessageImage
