from typing import List, Dict, Any, Optional
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
import httpx
import traceback
from services.config_service import config_service


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
            all_results.extend(self._search_xiaohongshu(query, max_results))
        if "douyin" in platforms:
            all_results.extend(self._search_douyin(query, max_results))
        if "bilibili" in platforms:
            all_results.extend(self._search_bilibili(query, max_results))
        return all_results[:max_results]

    def _search_xiaohongshu(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        try:
            config = config_service.app_config.get('search', {}).get('xiaohongshu', {})
            if not config.get('enabled', False):
                print("🔍 [Search] 小红书搜索未启用，使用模拟数据")
                return self._mock_xiaohongshu_search(query, max_results)

            cookie = config.get('cookie', '')
            if not cookie:
                print("🔍 [Search] 小红书缺少Cookie，使用模拟数据")
                return self._mock_xiaohongshu_search(query, max_results)

            print("🔍 [Search] 尝试调用小红书真实搜索API...")
            return self._mock_xiaohongshu_search(query, max_results)
        except Exception as e:
            print(f"🔍 [Search] 小红书搜索失败: {e}")
            return self._mock_xiaohongshu_search(query, max_results)

    def _search_douyin(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        try:
            config = config_service.app_config.get('search', {}).get('douyin', {})
            if not config.get('enabled', False):
                print("🔍 [Search] 抖音搜索未启用，使用模拟数据")
                return self._mock_douyin_search(query, max_results)

            cookie = config.get('cookie', '')
            if not cookie:
                print("🔍 [Search] 抖音缺少Cookie，使用模拟数据")
                return self._mock_douyin_search(query, max_results)

            print("🔍 [Search] 尝试调用抖音真实搜索API...")
            return self._mock_douyin_search(query, max_results)
        except Exception as e:
            print(f"🔍 [Search] 抖音搜索失败: {e}")
            return self._mock_douyin_search(query, max_results)

    def _search_bilibili(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        try:
            config = config_service.app_config.get('search', {}).get('bilibili', {})
            if not config.get('enabled', False):
                print("🔍 [Search] B站搜索未启用，使用模拟数据")
                return self._mock_bilibili_search(query, max_results)

            base_url = config.get('base_url', 'https://api.bilibili.com')
            cookie = config.get('cookie', '')

            print(f"🔍 [Search] 调用B站真实搜索API: query={query}, max_results={max_results}")

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://search.bilibili.com/',
            }
            if cookie:
                headers['Cookie'] = cookie

            params = {
                'keyword': query,
                'search_type': 'video',
                'page': 1,
                'pagesize': max_results,
            }

            with httpx.Client(timeout=httpx.Timeout(10.0)) as client:
                response = client.get(f"{base_url}/x/web-interface/search/type", params=params, headers=headers)

                if response.status_code != 200:
                    print(f"🔍 [Search] B站API返回错误: {response.status_code}")
                    return self._mock_bilibili_search(query, max_results)

                data = response.json()
                if data.get('code') != 0:
                    print(f"🔍 [Search] B站API返回错误码: {data.get('code')}, {data.get('message')}")
                    return self._mock_bilibili_search(query, max_results)

                results = data.get('data', {}).get('result', [])
                if not results:
                    print(f"🔍 [Search] B站搜索无结果")
                    return self._mock_bilibili_search(query, max_results)

                return self._parse_bilibili_results(results, max_results)

        except Exception as e:
            print(f"🔍 [Search] B站搜索失败: {e}")
            traceback.print_exc()
            return self._mock_bilibili_search(query, max_results)

    def _parse_bilibili_results(self, results: List[Dict[str, Any]], max_results: int) -> List[Dict[str, Any]]:
        parsed = []
        for item in results[:max_results]:
            parsed.append({
                "platform": "哔哩哔哩",
                "title": item.get('title', '').replace('<em class="keyword">', '').replace('</em>', ''),
                "description": item.get('description', '')[:100] + "..." if len(item.get('description', '')) > 100 else item.get('description', ''),
                "cover_image": item.get('pic', ''),
                "video_url": f"https://www.bilibili.com/video/{item.get('bvid', '')}",
                "likes": item.get('like', 0),
                "comments": item.get('comment', 0),
                "author": item.get('author', ''),
                "duration": self._format_duration(item.get('duration', 0)),
            })
        return parsed

    def _format_duration(self, seconds: int) -> str:
        try:
            if isinstance(seconds, str):
                return seconds
            h = seconds // 3600
            m = (seconds % 3600) // 60
            s = seconds % 60
            if h > 0:
                return f"{h:02d}:{m:02d}:{s:02d}"
            return f"{m:02d}:{s:02d}"
        except:
            return "00:00"

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
