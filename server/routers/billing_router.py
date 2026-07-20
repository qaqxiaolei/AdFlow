"""本地积分余额与微信支付充值（H5 跳转 / Native 扫码）。"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

import nanoid
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from routers.auth_router import get_current_user_id
from services.db_service import db_service
from services.wechat_pay_service import (
    create_h5_payment,
    create_native_payment,
    has_wechat_credentials,
    is_wechat_mock_mode,
    missing_wechat_credentials,
    parse_notify,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/billing", tags=["billing"])

RECHARGE_PACKAGES: List[Dict] = [
    {"id": "pack_50", "credits": 50, "price_cny": 5, "label": "体验包"},
    {"id": "pack_100", "credits": 100, "price_cny": 9, "label": "基础包"},
    {"id": "pack_300", "credits": 300, "price_cny": 25, "label": "进阶包"},
    {"id": "pack_1000", "credits": 1000, "price_cny": 79, "label": "专业包"},
]


class CreateWechatOrderRequest(BaseModel):
    package_id: str = Field(..., description="充值套餐 ID")
    # h5: 手机浏览器跳转微信支付；native: 桌面扫码
    trade_type: str = Field(default="h5", description="h5 | native")
    redirect_url: Optional[str] = Field(
        default=None, description="H5 支付完成后回跳地址"
    )


def _get_package(package_id: str) -> Dict:
    package = next((p for p in RECHARGE_PACKAGES if p["id"] == package_id), None)
    if not package:
        raise HTTPException(status_code=400, detail="无效的充值套餐")
    return package


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "127.0.0.1"


@router.get("/getBalance")
async def get_balance(user_id: str = Depends(get_current_user_id)):
    credits = await db_service.get_user_credits(user_id)
    return {"balance": f"{credits:.2f}"}


@router.get("/packages")
async def list_packages():
    mock = is_wechat_mock_mode()
    missing = missing_wechat_credentials() if not mock else []
    return {
        "packages": RECHARGE_PACKAGES,
        "wechat_mock": mock,
        "wechat_ready": mock or has_wechat_credentials(),
        "wechat_missing": missing,
    }


@router.post("/wechat/create-order")
async def create_wechat_order(
    body: CreateWechatOrderRequest,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    package = _get_package(body.package_id)
    trade_type = (body.trade_type or "h5").lower().strip()
    if trade_type not in ("h5", "native"):
        raise HTTPException(status_code=400, detail="trade_type 仅支持 h5 或 native")

    order_id = nanoid.generate(size=16)
    amount_cents = int(round(float(package["price_cny"]) * 100))
    description = f"蛮闪AI-{package['label']}-{int(package['credits'])}积分"

    code_url = ""
    qr_image = ""
    h5_url = ""
    is_mock = is_wechat_mock_mode()

    redirect_url = body.redirect_url
    if redirect_url and trade_type == "h5":
        sep = "&" if "?" in redirect_url else "?"
        redirect_url = f"{redirect_url}{sep}recharge_order={order_id}"

    try:
        if trade_type == "h5":
            h5_url, is_mock = create_h5_payment(
                order_id=order_id,
                amount_cents=amount_cents,
                description=description,
                client_ip=_client_ip(request),
                redirect_url=redirect_url,
            )
            code_url = h5_url
        else:
            code_url, qr_image, is_mock = create_native_payment(
                order_id, amount_cents, description
            )
    except FileNotFoundError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception("create wechat order failed")
        raise HTTPException(status_code=500, detail=f"创建支付订单失败: {e}") from e

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
        "trade_type": trade_type,
        "qr_image": qr_image,
        "code_url": code_url,
        "h5_url": h5_url,
        "mock": is_mock,
        "message": (
            "请完成微信支付"
            if trade_type == "h5"
            else "请使用微信扫码支付"
        ),
    }


@router.post("/wechat/notify")
@router.post("/payment/wechat/notify")
async def wechat_pay_notify(request: Request):
    """微信支付结果通知（无需登录）。"""
    body = await request.body()
    try:
        resource = parse_notify(dict(request.headers), body)
    except Exception:
        logger.exception("wechat notify verify failed")
        return JSONResponse(
            status_code=500,
            content={"code": "FAIL", "message": "验签失败"},
        )

    if not resource:
        return JSONResponse(
            status_code=400,
            content={"code": "FAIL", "message": "无效通知"},
        )

    out_trade_no = resource.get("out_trade_no")
    if not out_trade_no:
        return JSONResponse(
            status_code=400,
            content={"code": "FAIL", "message": "缺少订单号"},
        )

    order = await db_service.get_payment_order(out_trade_no)
    if not order:
        logger.warning("wechat notify unknown order: %s", out_trade_no)
        # 仍返回 SUCCESS，避免微信反复重试无效单
        return {"code": "SUCCESS", "message": "成功"}

    try:
        await db_service.mark_payment_order_paid(out_trade_no, order["user_id"])
    except ValueError as e:
        logger.warning("wechat notify mark paid: %s", e)

    return {"code": "SUCCESS", "message": "成功"}


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
    """仅模拟模式：一键确认支付成功。正式微信支付走 notify。"""
    if not is_wechat_mock_mode():
        raise HTTPException(status_code=400, detail="当前为正式支付模式，请使用微信支付")

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
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """兼容旧接口。"""
    return await create_wechat_order(body, request, user_id)
