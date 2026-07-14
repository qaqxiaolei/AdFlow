"""微信支付（Native 扫码）辅助：生成收款二维码。"""

from __future__ import annotations

import base64
import io
import os
from typing import Optional, Tuple

# 未配置真实商户时默认走模拟扫码（前端可确认支付）
WECHAT_PAY_MOCK = os.environ.get("WECHAT_PAY_MOCK", "1") == "1"
WECHAT_MCH_ID = os.environ.get("WECHAT_MCH_ID", "").strip()
WECHAT_APP_ID = os.environ.get("WECHAT_APP_ID", "").strip()


def is_wechat_mock_mode() -> bool:
    """真实商户号齐全且关闭 MOCK 时走正式接口占位。"""
    if WECHAT_PAY_MOCK:
        return True
    return not (WECHAT_MCH_ID and WECHAT_APP_ID)


def build_code_url(order_id: str, amount_cents: int) -> str:
    """
    生成微信 Native 支付 code_url。
    正式环境应调用微信支付统一下单 API 拿到真实 code_url。
    """
    if not is_wechat_mock_mode():
        # 占位：接入 wechatpayv3 后在此替换为真实下单结果
        # 当前没有私钥/证书时仍返回可扫码的约定串，便于联调结构
        return f"weixin://wxpay/bizpayurl?pr=ADFLOW{order_id.replace('-', '')[:16]}"

    return (
        f"weixin://wxpay/bizpayurl?pr=MOCK{order_id.replace('-', '')[:20]}"
        f"&amount={amount_cents}"
    )


def generate_qr_data_url(payload: str) -> str:
    """将支付链接绘制为 PNG Data URL，供前端展示扫码。"""
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


def create_wechat_native_qr(
    order_id: str, amount_cents: int
) -> Tuple[str, str, bool]:
    """
    Returns:
        (code_url, qr_image_data_url, is_mock)
    """
    mock = is_wechat_mock_mode()
    code_url = build_code_url(order_id, amount_cents)
    qr_image = generate_qr_data_url(code_url)
    return code_url, qr_image, mock
