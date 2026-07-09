from typing import Dict, Any, Optional, Tuple
from langgraph.graph.graph import CompiledGraph
from langchain_core.language_models import BaseChatModel
from models.config_model import ModelInfo
from models.tool_model import ToolInfoJson
from functools import lru_cache
import hashlib
import time


class AgentCache:
    def __init__(self, max_size: int = 10, ttl_seconds: int = 300):
        self._agent_cache: Dict[str, Tuple[CompiledGraph, float]] = {}
        self._model_cache: Dict[str, Tuple[BaseChatModel, float]] = {}
        self._swarm_cache: Dict[str, Tuple[Any, float]] = {}
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds

    def _generate_model_key(self, text_model: ModelInfo) -> str:
        model = text_model.get('model', '')
        provider = text_model.get('provider', '')
        url = text_model.get('url', '')
        return f"{provider}:{model}:{url}"

    def _generate_agent_key(self, text_model: ModelInfo, tool_list: list) -> str:
        model_key = self._generate_model_key(text_model)
        tool_ids = sorted([t.get('id', '') for t in tool_list])
        tool_str = ",".join(tool_ids)
        return f"{model_key}:{tool_str}"

    def get_model(self, text_model: ModelInfo) -> Optional[BaseChatModel]:
        key = self._generate_model_key(text_model)
        if key in self._model_cache:
            model, timestamp = self._model_cache[key]
            if time.time() - timestamp < self.ttl_seconds:
                return model
            else:
                del self._model_cache[key]
        return None

    def set_model(self, text_model: ModelInfo, model: BaseChatModel):
        key = self._generate_model_key(text_model)
        if len(self._model_cache) >= self.max_size:
            oldest_key = min(self._model_cache, key=lambda k: self._model_cache[k][1])
            del self._model_cache[oldest_key]
        self._model_cache[key] = (model, time.time())
        print(f"📦 缓存模型: {key}")

    def get_agents(self, text_model: ModelInfo, tool_list: list) -> Optional[list]:
        key = self._generate_agent_key(text_model, tool_list)
        if key in self._agent_cache:
            agents, timestamp = self._agent_cache[key]
            if time.time() - timestamp < self.ttl_seconds:
                return agents
            else:
                del self._agent_cache[key]
        return None

    def set_agents(self, text_model: ModelInfo, tool_list: list, agents: list):
        key = self._generate_agent_key(text_model, tool_list)
        if len(self._agent_cache) >= self.max_size:
            oldest_key = min(self._agent_cache, key=lambda k: self._agent_cache[k][1])
            del self._agent_cache[oldest_key]
        self._agent_cache[key] = (agents, time.time())
        print(f"📦 缓存智能体: {key}")

    def get_swarm(self, text_model: ModelInfo, tool_list: list) -> Optional[Any]:
        key = self._generate_agent_key(text_model, tool_list)
        if key in self._swarm_cache:
            swarm, timestamp = self._swarm_cache[key]
            if time.time() - timestamp < self.ttl_seconds:
                return swarm
            else:
                del self._swarm_cache[key]
        return None

    def set_swarm(self, text_model: ModelInfo, tool_list: list, swarm: Any):
        key = self._generate_agent_key(text_model, tool_list)
        if len(self._swarm_cache) >= self.max_size:
            oldest_key = min(self._swarm_cache, key=lambda k: self._swarm_cache[k][1])
            del self._swarm_cache[oldest_key]
        self._swarm_cache[key] = (swarm, time.time())
        print(f"📦 缓存Swarm: {key}")

    def clear(self):
        self._agent_cache.clear()
        self._model_cache.clear()
        self._swarm_cache.clear()
        print("🧹 缓存已清空")


agent_cache = AgentCache(max_size=10, ttl_seconds=300)