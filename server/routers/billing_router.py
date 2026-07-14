"""本地积分余额与微信扫码充值。"""

from __future__ import annotations

from typing import Dict, List

import nanoid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from routers.auth_router import get_current_user_id
from services.db_service import db_service
from services.wechat_pay_service import create_wechat_native_qr, is_wechat_mock_mode

router = APIRouter(prefix="/api/billing", tags=["billing"])

# 预设充值套餐（积分）
RECHARGE_PACKAGES: List[Dict] = [
    {"id": "pack_50", "credits": 50, "price_cny": 5, "label": "体验包"},
    {"id": "pack_100", "credits": 100, "price_cny": 9, "label": "基础包"},
    {"id": "pack_300", "credits": 300, "price_cny": 25, "label": "进阶包"},
    {"id": "pack_1000", "credits": 1000, "price_cny": 79, "label": "专业包"},
]


class CreateWechatOrderRequest(BaseModel):
    package_id: str = Field(..., description="充值套餐 ID")


def _get_package(package_id: str) -> Dict:
    package = next((p for p in RECHARGE_PACKAGES if p["id"] == package_id), None)
    if not package:
        raise HTTPException(status_code=400, detail="无效的充值套餐")
    return package


@router.get("/getBalance")
async def get_balance(user_id: str = Depends(get_current_user_id)):
    credits = await db_service.get_user_credits(user_id)
    return {"balance": f"{credits:.2f}"}


@router.get("/packages")
async def list_packages():
    return {"packages": RECHARGE_PACKAGES, "wechat_mock": is_wechat_mock_mode()}


@router.post("/wechat/create-order")
async def create_wechat_order(
    body: CreateWechatOrderRequest,
    user_id: str = Depends(get_current_user_id),
):
    package = _get_package(body.package_id)
    order_id = nanoid.generate(size=16)
    amount_cents = int(round(float(package["price_cny"]) * 100))

    try:
        code_url, qr_image, is_mock = create_wechat_native_qr(order_id, amount_cents)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    order = await db_service.create_payment_order(
        order_id=order_id,
        user_id=user_id,
        package_id=package["id"],
        credits=float(package["credits"]),
        amount_cents=amount_cents,
        code_url=code_url,
        channel="wechat",
    )

    return {
        "status": "pending",
        "order_id": order["id"],
        "credits": package["credits"],
        "price_cny": package["price_cny"],
        "amount_cents": amount_cents,
        "qr_image": qr_image,
        "code_url": code_url,
        "mock": is_mock,
        "message": "请使用微信扫码支付",
    }


@router.get("/orders/{order_id}")
async def get_order_status(
    order_id: str, user_id: str = Depends(get_current_user_id)
):
    order = await db_service.get_payment_order(order_id)
    if not order or order["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="订单不存在")
    balance = await db_service.get_user_credits(user_id)
    return {
        "order_id": order["id"],
        "status": order["status"],
        "credits": order["credits"],
        "price_cny": round(order["amount_cents"] / 100, 2),
        "paid_at": order.get("paid_at"),
        "balance": f"{balance:.2f}",
    }


@router.post("/orders/{order_id}/mock-pay")
async def mock_pay_order(
    order_id: str, user_id: str = Depends(get_current_user_id)
):
    """仅模拟模式：扫码联调时一键确认支付成功。正式微信支付走 notify。"""
    if not is_wechat_mock_mode():
        raise HTTPException(status_code=400, detail="当前为正式支付模式，请使用微信扫码")

    try:
        result = await db_service.mark_payment_order_paid(order_id, user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    order = result["order"]
    balance = result.get("balance")
    if balance is None:
        balance = await db_service.get_user_credits(user_id)

    return {
        "status": "success",
        "already_paid": result["already_paid"],
        "order_id": order_id,
        "message": f"支付成功，到账 {int(order['credits'])} 积分",
        "balance": f"{float(balance):.2f}",
    }


@router.post("/recharge")
async def recharge_legacy(
    body: CreateWechatOrderRequest,
    user_id: str = Depends(get_current_user_id),
):
    """兼容旧接口：改为创建微信扫码订单。"""
    return await create_wechat_order(body, user_id)
