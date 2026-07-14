"""本地手机号登录注册：密码 bcrypt 加密、JWT、短信验证码。"""

from __future__ import annotations

import hashlib
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import bcrypt
import jwt

from services.config_service import USER_DATA_DIR
from services.password_policy import validate_password, validate_phone

# 新用户免费视频积分；单次视频生成消耗
NEW_USER_FREE_CREDITS = float(os.environ.get("NEW_USER_FREE_CREDITS", "450"))
VIDEO_CREDIT_COST = float(os.environ.get("VIDEO_CREDIT_COST", "75"))

JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = int(os.environ.get("JWT_EXPIRE_DAYS", "30"))
SMS_CODE_TTL_SECONDS = int(os.environ.get("SMS_CODE_TTL_SECONDS", "300"))
SMS_SEND_INTERVAL_SECONDS = int(os.environ.get("SMS_SEND_INTERVAL_SECONDS", "60"))
# 本地开发默认开启调试：接口可返回验证码；生产请设 AUTH_SMS_DEBUG=0
AUTH_SMS_DEBUG = os.environ.get("AUTH_SMS_DEBUG", "1") == "1"

_jwt_secret: Optional[str] = None
# phone+purpose -> last send monotonic time
_sms_rate_limit: Dict[str, float] = {}
# In-memory SMS store fallback for rate checks (DB is source of truth for codes)
_sms_memory: Dict[str, Dict[str, Any]] = {}
# captcha_id -> { code, expires_at }
_captcha_store: Dict[str, Dict[str, Any]] = {}
CAPTCHA_TTL_SECONDS = int(os.environ.get("CAPTCHA_TTL_SECONDS", "300"))
CAPTCHA_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _get_jwt_secret() -> str:
    global _jwt_secret
    if _jwt_secret:
        return _jwt_secret
    env_secret = os.environ.get("JWT_SECRET")
    if env_secret:
        _jwt_secret = env_secret
        return _jwt_secret
    secret_path = os.path.join(USER_DATA_DIR, "jwt_secret.txt")
    os.makedirs(USER_DATA_DIR, exist_ok=True)
    if os.path.exists(secret_path):
        with open(secret_path, "r", encoding="utf-8") as f:
            _jwt_secret = f.read().strip()
    if not _jwt_secret:
        _jwt_secret = secrets.token_urlsafe(48)
        with open(secret_path, "w", encoding="utf-8") as f:
            f.write(_jwt_secret)
    return _jwt_secret


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"), password_hash.encode("utf-8")
        )
    except Exception:
        return False


def hash_sms_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def create_access_token(user_id: str, phone: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "phone": phone,
        "iat": now,
        "exp": now + timedelta(days=JWT_EXPIRE_DAYS),
    }
    return jwt.encode(payload, _get_jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    return jwt.decode(token, _get_jwt_secret(), algorithms=[JWT_ALGORITHM])


def generate_sms_code() -> str:
    return f"{secrets.randbelow(10**6):06d}"


def _cleanup_expired_captchas() -> None:
    now = time.monotonic()
    expired = [
        cid
        for cid, entry in _captcha_store.items()
        if entry.get("expires_at", 0) < now
    ]
    for cid in expired:
        _captcha_store.pop(cid, None)


def generate_captcha_code(length: int = 4) -> str:
    return "".join(secrets.choice(CAPTCHA_CHARS) for _ in range(length))


def create_captcha_image(code: str) -> bytes:
    """Generate a simple PNG captcha image; returns PNG bytes."""
    from io import BytesIO

    from PIL import Image, ImageDraw, ImageFont

    width, height = 120, 40
    image = Image.new("RGB", (width, height), (245, 247, 250))
    draw = ImageDraw.Draw(image)

    try:
        font = ImageFont.truetype("arial.ttf", 28)
    except OSError:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 26)
        except OSError:
            font = ImageFont.load_default()

    # Noise lines
    for _ in range(4):
        draw.line(
            (
                secrets.randbelow(width),
                secrets.randbelow(height),
                secrets.randbelow(width),
                secrets.randbelow(height),
            ),
            fill=(
                160 + secrets.randbelow(60),
                160 + secrets.randbelow(60),
                160 + secrets.randbelow(60),
            ),
            width=1,
        )

    # Noise dots
    for _ in range(40):
        draw.point(
            (secrets.randbelow(width), secrets.randbelow(height)),
            fill=(
                100 + secrets.randbelow(120),
                100 + secrets.randbelow(120),
                100 + secrets.randbelow(120),
            ),
        )

    char_width = width // (len(code) + 1)
    for i, ch in enumerate(code):
        x = char_width * (i + 0.4) + secrets.randbelow(6) - 3
        y = 4 + secrets.randbelow(8)
        color = (
            20 + secrets.randbelow(80),
            20 + secrets.randbelow(80),
            20 + secrets.randbelow(80),
        )
        draw.text((x, y), ch, font=font, fill=color)

    buf = BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def issue_captcha() -> Dict[str, Any]:
    """Create captcha, store answer, return id + png bytes."""
    _cleanup_expired_captchas()
    captcha_id = secrets.token_urlsafe(16)
    code = generate_captcha_code()
    _captcha_store[captcha_id] = {
        "code": code.upper(),
        "expires_at": time.monotonic() + CAPTCHA_TTL_SECONDS,
    }
    image_bytes = create_captcha_image(code)
    return {"captcha_id": captcha_id, "image_bytes": image_bytes}


def verify_and_consume_captcha(captcha_id: str, captcha_code: str) -> Optional[str]:
    """
    Verify captcha; consume on success or expiry.
    Returns error message or None if ok.
    """
    _cleanup_expired_captchas()
    if not captcha_id or not captcha_code:
        return "请输入图形验证码"
    entry = _captcha_store.pop(captcha_id, None)
    if not entry:
        return "图形验证码已失效，请刷新后重试"
    if time.monotonic() > entry.get("expires_at", 0):
        return "图形验证码已过期，请刷新后重试"
    expected = str(entry.get("code") or "").upper()
    actual = captcha_code.strip().upper()
    if actual != expected:
        return "图形验证码错误"
    return None



def check_sms_rate_limit(phone: str, purpose: str) -> Optional[str]:
    key = f"{phone}:{purpose}"
    last = _sms_rate_limit.get(key)
    now = time.monotonic()
    if last is not None and now - last < SMS_SEND_INTERVAL_SECONDS:
        wait = int(SMS_SEND_INTERVAL_SECONDS - (now - last))
        return f"发送过于频繁，请 {wait} 秒后再试"
    return None


def mark_sms_sent(phone: str, purpose: str) -> None:
    _sms_rate_limit[f"{phone}:{purpose}"] = time.monotonic()


async def send_sms_code(phone: str, code: str, purpose: str) -> None:
    """
    发送短信验证码。
    当前为可插拔占位：无第三方网关时写入日志；后续可接入阿里云/腾讯云等。
    """
    print(f"📱 [SMS:{purpose}] phone={phone} code={code}")
    # Hook for real providers via env, e.g. SMS_PROVIDER=aliyun
    provider = os.environ.get("SMS_PROVIDER", "console")
    if provider == "console":
        return
    # Future: dispatch to aliyun / twilio adapters
    return


def user_public_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    phone = row.get("phone") or ""
    masked = f"{phone[:3]}****{phone[-4:]}" if len(phone) == 11 else phone
    return {
        "id": row["id"],
        "username": masked,
        "phone": phone,
        "email": "",
        "credits": float(row.get("credits") or 0),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


# Re-export validators for routers
__all__ = [
    "NEW_USER_FREE_CREDITS",
    "VIDEO_CREDIT_COST",
    "AUTH_SMS_DEBUG",
    "SMS_CODE_TTL_SECONDS",
    "hash_password",
    "verify_password",
    "hash_sms_code",
    "create_access_token",
    "decode_access_token",
    "generate_sms_code",
    "check_sms_rate_limit",
    "mark_sms_sent",
    "send_sms_code",
    "issue_captcha",
    "verify_and_consume_captcha",
    "user_public_dict",
    "validate_password",
    "validate_phone",
]
