"""Short-lived caches for model/tool list endpoints (mobile-friendly)."""

import time
from typing import Any, Dict, List, Optional, Tuple

_ollama_cache: Optional[Tuple[float, List[str], bool]] = None
OLLAMA_SUCCESS_TTL = 120.0
OLLAMA_FAILURE_TTL = 300.0

_models_cache: Optional[Tuple[float, List[Any]]] = None
_tools_cache: Optional[Tuple[float, List[Any]]] = None
LIST_CACHE_TTL = 60.0


def get_cached_ollama_models() -> Optional[List[str]]:
    global _ollama_cache
    if _ollama_cache is None:
        return None
    cached_at, models, failed = _ollama_cache
    ttl = OLLAMA_FAILURE_TTL if failed else OLLAMA_SUCCESS_TTL
    if time.monotonic() - cached_at < ttl:
        return models
    return None


def set_cached_ollama_models(models: List[str], *, failed: bool) -> None:
    global _ollama_cache
    _ollama_cache = (time.monotonic(), models, failed)


def should_log_ollama_failure() -> bool:
    global _ollama_cache
    if _ollama_cache is None:
        return True
    cached_at, _, failed = _ollama_cache
    return failed and time.monotonic() - cached_at >= OLLAMA_FAILURE_TTL


def get_cached_models() -> Optional[List[Any]]:
    return _read_cache(_models_cache, LIST_CACHE_TTL)


def set_cached_models(models: List[Any]) -> None:
    global _models_cache
    _models_cache = (time.monotonic(), models)


def get_cached_tools() -> Optional[List[Any]]:
    return _read_cache(_tools_cache, LIST_CACHE_TTL)


def set_cached_tools(tools: List[Any]) -> None:
    global _tools_cache
    _tools_cache = (time.monotonic(), tools)


def invalidate_list_caches() -> None:
    global _models_cache, _tools_cache, _ollama_cache
    _models_cache = None
    _tools_cache = None
    _ollama_cache = None


def _read_cache(
    cache: Optional[Tuple[float, List[Any]]], ttl: float
) -> Optional[List[Any]]:
    if cache is None:
        return None
    cached_at, value = cache
    if time.monotonic() - cached_at < ttl:
        return value
    return None
