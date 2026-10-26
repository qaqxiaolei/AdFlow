"""图片 / 视频生成的积分扣减与失败退回。"""

from __future__ import annotations

from typing import Any, Dict

from services.auth_service import IMAGE_CREDIT_COST, VIDEO_CREDIT_COST
from services.db_service import db_service

_COSTS = {
    "image": IMAGE_CREDIT_COST,
    "video": VIDEO_CREDIT_COST,
}


def generation_credit_cost(kind: str) -> float:
    try:
        return float(_COSTS[kind])
    except KeyError as exc:
        raise ValueError("kind 只能是 image 或 video") from exc


def _model_label(kind: str, model: str) -> str:
    label = (model or "").strip()
    if len(label) > 120:
        label = label[:120]
    return label or kind


async def consume_generation_credits(
    user_id: str, kind: str, model: str = "", quantity: int = 1
) -> Dict[str, Any]:
    """按类型扣生成费用。quantity 为本次生成张数/条数。余额不足时抛出 ValueError。"""
    if quantity not in (1, 2):
        raise ValueError("quantity 只能是 1 或 2")
    unit_cost = generation_credit_cost(kind)
    cost = unit_cost * quantity
    label = _model_label(kind, model)
    reason = f"{kind}:{label}" if quantity == 1 else f"{kind}x{quantity}:{label}"
    result = await db_service.adjust_user_credits(user_id, -cost, reason)
    balance = float(result["credits"])
    return {
        "kind": kind,
        "model": label,
        "quantity": quantity,
        "cost": cost,
        "reason": reason,
        "balance": f"{balance:.2f}",
    }


async def refund_generation_credits(
    user_id: str, kind: str, model: str = ""
) -> Dict[str, Any]:
    """生成失败时退回一次扣费。仅供服务端生成流程调用。"""
    cost = generation_credit_cost(kind)
    label = _model_label(kind, model)
    reason = f"{kind}_refund:{label}"
    result = await db_service.adjust_user_credits(user_id, cost, reason)
    balance = float(result["credits"])
    return {
        "kind": kind,
        "model": label,
        "cost": cost,
        "reason": reason,
        "balance": f"{balance:.2f}",
    }
