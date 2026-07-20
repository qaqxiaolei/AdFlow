"""微信支付：H5 跳转支付 + Native 扫码，支持模拟模式。"""

from __future__ import annotations

import base64
import io
import json
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import quote

logger = logging.getLogger(__name__)

SERVER_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    """从 server/.env 加载配置（若已安装 python-dotenv）。"""
    env_path = SERVER_DIR / ".env"
    if not env_path.is_file():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path, override=False)
    except ImportError:
        # 简易解析，避免强依赖
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


_load_dotenv()


def _env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return default


WECHAT_PAY_MOCK = _env("WECHAT_PAY_MOCK", default="1") == "1"
WECHAT_MCH_ID = _env("WECHAT_MCH_ID")
WECHAT_APP_ID = _env("WECHAT_APP_ID", "WECHAT_APPID")
WECHAT_API_V3_KEY = _env("WECHAT_API_V3_KEY", "WECHAT_APIV3_KEY")
WECHAT_CERT_SERIAL_NO = _env("WECHAT_CERT_SERIAL_NO")
WECHAT_PRIVATE_KEY_PATH = _env(
    "WECHAT_PRIVATE_KEY_PATH", default="./certs/apiclient_key.pem"
)
WECHAT_NOTIFY_URL = _env("WECHAT_NOTIFY_URL")
WECHAT_CERT_DIR = _env("WECHAT_CERT_DIR", default="./certs")


def _resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    if not path.is_absolute():
        path = (SERVER_DIR / path).resolve()
    return path


def _read_private_key() -> str:
    key_path = _resolve_path(WECHAT_PRIVATE_KEY_PATH)
    if not key_path.is_file():
        raise FileNotFoundError(
            f"未找到商户私钥文件: {key_path}。"
            "请将微信支付 apiclient_key.pem 放到 server/certs/ 目录。"
        )
    return key_path.read_text(encoding="utf-8")


def missing_wechat_credentials() -> list[str]:
    """返回尚未配置完整的微信支付项（便于前端/日志提示）。"""
    missing: list[str] = []
    if not WECHAT_MCH_ID:
        missing.append("WECHAT_MCH_ID")
    if not WECHAT_APP_ID:
        missing.append("WECHAT_APP_ID")
    if not WECHAT_API_V3_KEY:
        missing.append("WECHAT_API_V3_KEY")
    if not WECHAT_CERT_SERIAL_NO:
        missing.append("WECHAT_CERT_SERIAL_NO")
    if not WECHAT_NOTIFY_URL:
        missing.append("WECHAT_NOTIFY_URL（需公网 HTTPS 回调地址）")
    try:
        key_path = _resolve_path(WECHAT_PRIVATE_KEY_PATH)
        if not key_path.is_file():
            missing.append(f"商户私钥文件 {key_path}")
    except Exception:
        missing.append("WECHAT_PRIVATE_KEY_PATH")
    return missing


def has_wechat_credentials() -> bool:
    return not missing_wechat_credentials()


def is_wechat_mock_mode() -> bool:
    """仅当显式开启 WECHAT_PAY_MOCK=1 时走模拟支付。"""
    return WECHAT_PAY_MOCK


def require_wechat_ready() -> None:
    """正式支付前校验配置，缺失则抛出可读错误。"""
    if is_wechat_mock_mode():
        return
    missing = missing_wechat_credentials()
    if missing:
        raise RuntimeError(
            "微信支付配置不完整，无法跳转真实收银台。请补全："
            + "；".join(missing)
        )


@lru_cache(maxsize=1)
def _get_wxpay():
    from wechatpayv3 import WeChatPay, WeChatPayType

    private_key = _read_private_key()
    cert_dir = str(_resolve_path(WECHAT_CERT_DIR))
    os.makedirs(cert_dir, exist_ok=True)

    return WeChatPay(
        wechatpay_type=WeChatPayType.NATIVE,
        mchid=WECHAT_MCH_ID,
        private_key=private_key,
        cert_serial_no=WECHAT_CERT_SERIAL_NO,
        apiv3_key=WECHAT_API_V3_KEY,
        appid=WECHAT_APP_ID,
        notify_url=WECHAT_NOTIFY_URL,
        cert_dir=cert_dir,
    )


def generate_qr_data_url(payload: str) -> str:
    try:
        import qrcode
        from qrcode.constants import ERROR_CORRECT_M
    except ImportError as exc:
        raise RuntimeError("请安装 qrcode 包：pip install qrcode") from exc

    qr = qrcode.QRCode(
        version=1,
        error_correction=ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _mock_code_url(order_id: str, amount_cents: int) -> str:
    return (
        f"weixin://wxpay/bizpayurl?pr=MOCK{order_id.replace('-', '')[:20]}"
        f"&amount={amount_cents}"
    )


def create_native_payment(
    order_id: str, amount_cents: int, description: str
) -> Tuple[str, str, bool]:
    """
    Native 扫码支付。
    Returns: (code_url, qr_image_data_url, is_mock)
    """
    if is_wechat_mock_mode():
        code_url = _mock_code_url(order_id, amount_cents)
        return code_url, generate_qr_data_url(code_url), True

    require_wechat_ready()
    from wechatpayv3 import WeChatPayType

    wxpay = _get_wxpay()
    code, message = wxpay.pay(
        description=description[:127],
        out_trade_no=order_id,
        amount={"total": amount_cents, "currency": "CNY"},
        pay_type=WeChatPayType.NATIVE,
    )
    if code not in (200, 204):
        logger.error("WeChat Native pay failed: %s %s", code, message)
        raise RuntimeError(f"微信下单失败: {message}")

    data = json.loads(message) if isinstance(message, str) else message
    code_url = data.get("code_url") or ""
    if not code_url:
        raise RuntimeError(f"微信下单未返回 code_url: {message}")
    return code_url, generate_qr_data_url(code_url), False


def create_h5_payment(
    order_id: str,
    amount_cents: int,
    description: str,
    client_ip: str,
    redirect_url: Optional[str] = None,
) -> Tuple[str, bool]:
    """
    H5 支付，返回可跳转的收银台链接。
    Returns: (h5_url, is_mock)
    """
    if is_wechat_mock_mode():
        # 模拟：返回带标记的本地回跳，前端可识别并走 mock-pay
        base = redirect_url or "/"
        sep = "&" if "?" in base else "?"
        mock_url = f"{base}{sep}wechat_mock_pay=1&order_id={order_id}"
        return mock_url, True

    require_wechat_ready()
    from wechatpayv3 import WeChatPayType

    payer_ip = (client_ip or "127.0.0.1").split(",")[0].strip() or "127.0.0.1"
    wxpay = _get_wxpay()
    code, message = wxpay.pay(
        description=description[:127],
        out_trade_no=order_id,
        amount={"total": amount_cents, "currency": "CNY"},
        pay_type=WeChatPayType.H5,
        scene_info={
            "payer_client_ip": payer_ip,
            "h5_info": {"type": "Wap", "app_name": "蛮闪AI", "app_url": "https://adflow"},
        },
    )
    if code not in (200, 204):
        logger.error("WeChat H5 pay failed: %s %s", code, message)
        raise RuntimeError(f"微信 H5 下单失败: {message}")

    data = json.loads(message) if isinstance(message, str) else message
    h5_url = data.get("h5_url") or ""
    if not h5_url:
        raise RuntimeError(f"微信下单未返回 h5_url: {message}")

    if redirect_url:
        joiner = "&" if "?" in h5_url else "?"
        h5_url = f"{h5_url}{joiner}redirect_url={quote(redirect_url, safe='')}"

    return h5_url, False


def parse_notify(headers: Dict[str, Any], body: bytes) -> Optional[Dict[str, Any]]:
    """验签并解密微信支付回调，成功返回 resource 字典。"""
    if is_wechat_mock_mode():
        return None

    wxpay = _get_wxpay()
    # wechatpayv3 需要普通 dict headers
    header_dict = {k: v for k, v in headers.items()}
    result = wxpay.callback(header_dict, body)
    if not result:
        return None
    if result.get("event_type") != "TRANSACTION.SUCCESS":
        logger.info("Ignore wechat notify event: %s", result.get("event_type"))
        return None
    resource = result.get("resource") or {}
    if resource.get("trade_state") and resource.get("trade_state") != "SUCCESS":
        return None
    return resource


# 兼容旧调用
def create_wechat_native_qr(
    order_id: str, amount_cents: int
) -> Tuple[str, str, bool]:
    return create_native_payment(order_id, amount_cents, "蛮闪AI积分充值")
