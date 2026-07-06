from typing import List, Dict, Any
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field


class SearchVideoByPlatformInput(BaseModel):
    query: str = Field(..., description="搜索关键词，描述用户想要搜索的视频内容")
    platform: str = Field(default="all", description="搜索平台，可选值: xiaohongshu, douyin, bilibili, all")
    max_results: int = Field(default=5, description="返回结果数量，最多10条")


class SearchVideoByPlatformTool(BaseTool):
    name: str = "search_video_by_platform"
    description: str = "搜索小红书、抖音、哔哩哔哩等平台的参考视频，获取视频标题、描述、封面图等信息，用于视频创作参考"
    args_schema: type = SearchVideoByPlatformInput

    def _run(self, query: str, platform: str = "all", max_results: int = 5) -> str:
        results = self._search_videos(query, platform, max_results)
        return self._format_results(results)

    async def _arun(self, query: str, platform: str = "all", max_results: int = 5) -> str:
        return self._run(query, platform, max_results)

    def _search_videos(self, query: str, platform: str, max_results: int) -> List[Dict[str, Any]]:
        max_results = min(max_results, 10)
        
        platforms = []
        if platform == "all":
            platforms = ["xiaohongshu", "douyin", "bilibili"]
        else:
            platforms = [platform]

        all_results = []

        if "xiaohongshu" in platforms:
            all_results.extend(self._mock_xiaohongshu_search(query, max_results))
        
        if "douyin" in platforms:
            all_results.extend(self._mock_douyin_search(query, max_results))
        
        if "bilibili" in platforms:
            all_results.extend(self._mock_bilibili_search(query, max_results))

        return all_results[:max_results]

    def _mock_xiaohongshu_search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        return [
            {
                "platform": "小红书",
                "title": f"{query}教程｜新手也能学会的做法",
                "description": "超详细的制作教程，从选材到成品一步步教你，赶紧收藏起来！",
                "cover_image": "",
                "video_url": "#",
                "likes": 12580,
                "comments": 892,
                "author": "美食达人小王",
                "duration": "03:45",
            },
            {
                "platform": "小红书",
                "title": f"{query}创意做法｜网红同款在家做",
                "description": "最近超火的创意做法，在家也能做出餐厅级别的美味，快来试试！",
                "cover_image": "",
                "video_url": "#",
                "likes": 8920,
                "comments": 567,
                "author": "创意厨房",
                "duration": "02:30",
            },
        ]

    def _mock_douyin_search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        return [
            {
                "platform": "抖音",
                "title": f"{query}制作全过程，看完你也会！",
                "description": "全程无加速，详细展示制作过程，学会记得点赞收藏～",
                "cover_image": "",
                "video_url": "#",
                "likes": 56230,
                "comments": 3240,
                "author": "大厨教做菜",
                "duration": "04:12",
            },
            {
                "platform": "抖音",
                "title": f"{query}挑战｜3分钟快速搞定",
                "description": "挑战3分钟做出美味，时间紧迫但味道不减！",
                "cover_image": "",
                "video_url": "#",
                "likes": 34120,
                "comments": 2156,
                "author": "快手美食",
                "duration": "03:05",
            },
        ]

    def _mock_bilibili_search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        return [
            {
                "platform": "哔哩哔哩",
                "title": f"{query}深度解析｜从理论到实践",
                "description": "深入讲解制作原理和技巧，让你不仅知其然更知其所以然",
                "cover_image": "",
                "video_url": "#",
                "likes": 18920,
                "comments": 1567,
                "author": "美食研究所",
                "duration": "12:35",
            },
            {
                "platform": "哔哩哔哩",
                "title": f"{query}评测｜不同做法对比",
                "description": "对比多种不同做法的优缺点，帮你找到最适合自己的方式",
                "cover_image": "",
                "video_url": "#",
                "likes": 12340,
                "comments": 892,
                "author": "美食测评君",
                "duration": "08:20",
            },
        ]

    def _format_results(self, results: List[Dict[str, Any]]) -> str:
        if not results:
            return "未找到相关视频，请尝试其他关键词"

        formatted = "📺 搜索到以下参考视频:\n\n"
        for i, result in enumerate(results, 1):
            formatted += f"【{i}】[{result['platform']}] {result['title']}\n"
            formatted += f"   📝 描述: {result['description']}\n"
            formatted += f"   👍 点赞: {result['likes']} | 💬 评论: {result['comments']}\n"
            formatted += f"   🎬 时长: {result['duration']} | 👤 作者: {result['author']}\n\n"

        formatted += "💡 你可以参考这些视频的创意和风格，用于优化你的视频生成方案"
        return formatted


search_video_by_platform_tool = SearchVideoByPlatformTool()
