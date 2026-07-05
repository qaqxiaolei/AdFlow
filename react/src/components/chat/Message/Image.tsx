import { PhotoView } from 'react-photo-view'

type MessageImageProps = {
    content: {
        image_url: {
            url: string
        }
        type: 'image_url'
    }
}

const MessageImage = ({ content }: MessageImageProps) => {
    return (
        <div className="w-full max-w-[140px]">
            <PhotoView src={content.image_url.url}>
                <div className="relative group cursor-pointer">
                    <img
                        className="w-full h-auto max-h-[140px] object-cover rounded-md border border-border hover:scale-105 transition-transform duration-300"
                        src={content.image_url.url}
                        alt="Image"
                    />
                </div>
            </PhotoView>
        </div>
    )
}

export default MessageImage
