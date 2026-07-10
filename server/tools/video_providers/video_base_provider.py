from abc import ABC, abstractmethod

from typing import Optional, Dict, Any, List, Type

from models.config_model import ModelInfo

class VideoProviderBase(ABC):
    """视频生成 provider 抽象基类"""
    # 类属性：provider 注册表
    _providers: Dict[str, Type['VideoProviderBase']] = {}
    def __init_subclass__(cls, provider_name: Optional[str] = None, **kwargs: Any):
        """子类定义时自动注册到 provider 注册表"""
        super().__init_subclass__(**kwargs)
        if provider_name:
            cls._providers[provider_name] = cls

    @classmethod
    def create_provider(cls, provider_name: str) -> 'VideoProviderBase':
        """工厂方法：根据名称创建 provider 实例"""
        if provider_name not in cls._providers:
            raise ValueError(f"Unknown provider: {provider_name}")
        provider_class = cls._providers[provider_name]
        return provider_class()  # 各 provider 自行读取配置并初始化

    @classmethod
    def get_available_providers(cls) -> List[str]:
        """获取所有已注册的 provider 名称"""
        return list(cls._providers.keys())

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        model: str,
        resolution: str = "480p",
        duration: int = 5,
        aspect_ratio: str = "16:9",
        input_images: Optional[list[str]] = None,
        camera_fixed: bool = True,
        **kwargs: Any
    ) -> str:
        """
        生成视频并返回视频 URL
        Args:
            prompt: 视频生成提示词
            model: 用于生成的模型名称
            resolution: 视频分辨率（480p、1080p）
            duration: 视频时长（秒，如 5、10）
            aspect_ratio: 视频宽高比（1:1、16:9、4:3、21:9）
            input_images: 可选的参考图/首帧图片
            camera_fixed: 是否固定镜头
            **kwargs: 各 provider 特有的额外参数
        Returns:
            str: 可下载的视频 URL
        """
        pass

def get_default_provider(model_info_list: Optional[List[ModelInfo]] = None) -> str:
    """获取视频生成的默认 provider
    Args:
        model_info_list: 模型信息列表。若提供，则优先选用 volces/agnes；否则使用列表中第一项；未提供时默认返回 'volces'。
    Returns:
        str: provider 名称
    """
    if model_info_list:
        for model_info in model_info_list:
            provider = model_info.get('provider', '')
            if provider in ('volces', 'agnes'):
                return provider
        return model_info_list[0].get('provider', 'volces')
    return "agnes"


def resolve_video_provider(
    model_name: str,
    model_info_list: Optional[List[ModelInfo]] = None,
    tool_list: Optional[List[ModelInfo]] = None,
    explicit_provider: Optional[str] = None,
) -> str:
    """根据模型名和上下文解析视频 provider"""
    if explicit_provider:
        return explicit_provider

    normalized = model_name.lower()
    if "seedance" in normalized or normalized.startswith("doubao-"):
        return "volces"

    if model_info_list:
        provider = get_default_provider(model_info_list)
        if provider:
            return provider

    if tool_list:
        video_tools = [
            t for t in tool_list
            if isinstance(t, dict) and t.get("type") == "video" and t.get("provider")
        ]
        for tool in video_tools:
            if tool.get("provider") == "volces":
                return "volces"
        if video_tools:
            return str(video_tools[0].get("provider", "volces"))

    return "volces"

