"""本地积分余额与微信支付充值（JSAPI / Native / H5）。"""

from __future__ import annotations

import base64
import logging
from typing import Dict, List, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import nanoid
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from routers.auth_router import get_current_user_id
from services.db_service import db_service
from services.wechat_pay_service import (
    WECHAT_NOTIFY_URL,
    build_oauth_authorize_url,
    create_h5_payment,
    create_jsapi_payment,
    create_native_payment,
    exchange_oauth_code_for_openid,
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
    {"id": "pack_1000", "credits": 980, "price_cny": 79, "label": "专业包"},
]


class CreateWechatOrderRequest(BaseModel):
    package_id: str = Field(..., description="充值套餐 ID")
    # jsapi: 微信内；native: 桌面扫码；h5: 手机浏览器（需已开通）
    trade_type: str = Field(default="jsapi", description="jsapi | native | h5")
    redirect_url: Optional[str] = Field(
        default=None, description="H5 支付完成后回跳地址"
    )
    openid: Optional[str] = Field(
        default=None, description="JSAPI 所需微信 openid"
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


def _public_origin(request: Request) -> str:
    proto = (
        request.headers.get("x-forwarded-proto")
        or request.url.scheme
        or "https"
    ).split(",")[0].strip()
    host = (
        request.headers.get("x-forwarded-host")
        or request.headers.get("host")
        or request.url.netloc
    )
    return f"{proto}://{host}"


def _oauth_public_origin(request: Request) -> str:
    """OAuth 回调必须用已配置的公网域名（微信不认局域网 IP）。"""
    if WECHAT_NOTIFY_URL:
        parsed = urlparse(WECHAT_NOTIFY_URL)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
    return _public_origin(request)


def _host_only(netloc: str) -> str:
    return (netloc or "").split("@")[-1].split(":")[0].lower()


def _is_private_host(host: str) -> bool:
    h = (host or "").lower()
    return (
        h in ("localhost", "127.0.0.1", "::1")
        or h.startswith("192.168.")
        or h.startswith("10.")
        or h.startswith("172.16.")
        or h.startswith("172.17.")
        or h.startswith("172.18.")
        or h.startswith("172.19.")
        or h.startswith("172.2")
        or h.startswith("172.30.")
        or h.startswith("172.31.")
    )


def _encode_return_state(return_url: str) -> str:
    return base64.urlsafe_b64encode(return_url.encode("utf-8")).decode("ascii")


def _decode_return_state(state: str) -> str:
    try:
        raw = base64.urlsafe_b64decode(state.encode("ascii")).decode("utf-8")
    except Exception as exc:
        raise HTTPException(status_code=400, detail="无效的 OAuth state") from exc
    return raw


def _allowed_hosts(request: Request) -> set[str]:
    hosts: set[str] = set()
    for candidate in (
        _public_origin(request),
        _oauth_public_origin(request),
        request.headers.get("origin") or "",
        request.headers.get("referer") or "",
    ):
        if not candidate:
            continue
        parsed = urlparse(candidate if "://" in candidate else f"https://{candidate}")
        host = _host_only(parsed.netloc)
        if host:
            hosts.add(host)
    return hosts


def _safe_return_url(return_url: str, request: Request) -> str:
    """仅允许跳回本站，防止开放重定向。"""
    origin = _oauth_public_origin(request)
    parsed = urlparse(return_url)
    if not parsed.scheme and not parsed.netloc:
        path = return_url if return_url.startswith("/") else f"/{return_url}"
        return f"{origin}{path}"

    host = _host_only(parsed.netloc)
    if _is_private_host(host):
        raise HTTPException(
            status_code=400,
            detail=(
                "JSAPI 不支持用局域网 IP 授权。请用微信打开 https://adflow.chat 再充值"
            ),
        )

    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="return_url 无效")

    allowed = _allowed_hosts(request)
    if host in allowed or _host_only(urlparse(origin).netloc) == host:
        return return_url

    raise HTTPException(
        status_code=400,
        detail="return_url 必须是本站地址，请使用 https://adflow.chat",
    )


def _append_query(url: str, **params: str) -> str:
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.update({k: v for k, v in params.items() if v is not None})
    return urlunparse(parsed._replace(query=urlencode(query)))


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


@router.get("/wechat/oauth/start")
async def wechat_oauth_start(
    request: Request,
    return_url: str = Query(..., description="授权完成后回跳的前端地址"),
):
    """跳转微信网页授权，静默获取 openid（需在微信内打开）。"""
    safe_return = _safe_return_url(return_url, request)
    callback = f"{_oauth_public_origin(request)}/api/billing/wechat/oauth/callback"
    state = _encode_return_state(safe_return)
    try:
        auth_url = build_oauth_authorize_url(callback, state=state)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return RedirectResponse(auth_url, status_code=302)


@router.get("/wechat/oauth/callback")
async def wechat_oauth_callback(
    request: Request,
    code: str = Query(default=""),
    state: str = Query(default=""),
):
    """微信 OAuth 回调：换 openid 后带回前端。"""
    if not code or not state:
        raise HTTPException(status_code=400, detail="缺少 code 或 state")
    return_url = _safe_return_url(_decode_return_state(state), request)
    try:
        openid = exchange_oauth_code_for_openid(code)
    except RuntimeError as e:
        fail_url = _append_query(return_url, wechat_oauth_error=str(e)[:120])
        return RedirectResponse(fail_url, status_code=302)
    ok_url = _append_query(return_url, wechat_openid=openid, open_recharge="1")
    return RedirectResponse(ok_url, status_code=302)


@router.post("/wechat/create-order")
async def create_wechat_order(
    body: CreateWechatOrderRequest,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    package = _get_package(body.package_id)
    trade_type = (body.trade_type or "jsapi").lower().strip()
    if trade_type not in ("jsapi", "native", "h5"):
        raise HTTPException(
            status_code=400, detail="trade_type 仅支持 jsapi、native 或 h5"
        )

    order_id = nanoid.generate(size=16)
    amount_cents = int(round(float(package["price_cny"]) * 100))
    description = f"蛮闪AI-{package['label']}-{int(package['credits'])}积分"

    code_url = ""
    qr_image = ""
    h5_url = ""
    jsapi_params: Dict[str, str] = {}
    is_mock = is_wechat_mock_mode()

    redirect_url = body.redirect_url
    if redirect_url and trade_type == "h5":
        sep = "&" if "?" in redirect_url else "?"
        redirect_url = f"{redirect_url}{sep}recharge_order={order_id}"

    try:
        if trade_type == "jsapi":
            jsapi_params, is_mock = create_jsapi_payment(
                order_id=order_id,
                amount_cents=amount_cents,
                description=description,
                openid=body.openid or "",
            )
        elif trade_type == "h5":
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
        code_url=code_url or (jsapi_params.get("package") or ""),
        channel="wechat",
    )

    messages = {
        "jsapi": "请在微信中完成支付",
        "h5": "请完成微信支付",
        "native": "请使用微信扫码支付",
    }

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
        "jsapi_params": jsapi_params or None,
        "mock": is_mock,
        "message": messages.get(trade_type, "请完成微信支付"),
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
