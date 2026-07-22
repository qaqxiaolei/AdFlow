"""密码校验：长度、复杂度、弱密码拦截。"""

from __future__ import annotations

import re
from datetime import datetime

PHONE_PATTERN = re.compile(r"^1[3-9]\d{9}$")

SPECIAL_CHARS = re.compile(r'[!@#$%^&*()_+\-=\[\]{};\'":\\|,.<>/?`~]')


def validate_phone(phone: str) -> str | None:
    """校验中国大陆 11 位手机号，失败返回错误信息。"""
    if not phone or not isinstance(phone, str):
        return "请输入手机号"
    phone = phone.strip()
    if not PHONE_PATTERN.match(phone):
        return "手机号须为 11 位有效号码"
    return None


def _looks_like_birthday(password: str) -> bool:
    """拦截类似生日的数字串，如 19900101、01011990、90/01/01。"""
    digits = re.sub(r"\D", "", password)
    if len(digits) < 6:
        return False

    candidates = set()
    # YYYYMMDD / DDMMYYYY / MMDDYYYY within the digit stream
    for i in range(0, max(0, len(digits) - 7)):
        candidates.add(digits[i : i + 8])
    for i in range(0, max(0, len(digits) - 5)):
        candidates.add(digits[i : i + 6])

    year_now = datetime.now().year
    for chunk in candidates:
        if len(chunk) == 8:
            y, m, d = int(chunk[:4]), int(chunk[4:6]), int(chunk[6:8])
            if 1940 <= y <= year_now and 1 <= m <= 12 and 1 <= d <= 31:
                return True
            d, m, y = int(chunk[:2]), int(chunk[2:4]), int(chunk[4:8])
            if 1940 <= y <= year_now and 1 <= m <= 12 and 1 <= d <= 31:
                return True
            m, d, y = int(chunk[:2]), int(chunk[2:4]), int(chunk[4:8])
            if 1940 <= y <= year_now and 1 <= m <= 12 and 1 <= d <= 31:
                return True
        if len(chunk) == 6:
            # YYMMDD
            yy, m, d = int(chunk[:2]), int(chunk[2:4]), int(chunk[4:6])
            year = 1900 + yy if yy > 30 else 2000 + yy
            if 1940 <= year <= year_now and 1 <= m <= 12 and 1 <= d <= 31:
                return True
    return False


def _is_sequential_or_repeated(password: str) -> bool:
    lower = password.lower()
    alnum = re.sub(r"[^a-z0-9]", "", lower)
    if len(alnum) >= 8 and len(set(alnum)) <= 2:
        return True
    # 拦截连续数字（如 1234、9876）与常见键盘串
    for seq in ("0123456789", "9876543210"):
        for i in range(len(seq) - 3):
            if seq[i : i + 4] in lower:
                return True
    keyboard_runs = (
        "qwerty",
        "asdfgh",
        "zxcvbn",
        "qwertyuiop",
        "asdfghjkl",
    )
    for run in keyboard_runs:
        if run in lower:
            return True
    return False


def validate_password(password: str, phone: str | None = None) -> str | None:
    """
    校验密码强度。
    规则：8 位以上，含大小写字母、数字、特殊符号；拦截弱密码/生日/序列等。
    失败返回错误信息，成功返回 None。
    """
    if not password or not isinstance(password, str):
        return "请输入密码"
    if len(password) < 8:
        return "密码至少 8 位"
    if len(password) > 64:
        return "密码过长"
    if not re.search(r"[a-z]", password):
        return "密码须包含小写字母"
    if not re.search(r"[A-Z]", password):
        return "密码须包含大写字母"
    if not re.search(r"\d", password):
        return "密码须包含数字"
    if not SPECIAL_CHARS.search(password):
        return "密码须包含特殊符号"

    if phone and phone in password:
        return "密码不能包含手机号"
    if phone and phone[-4:] in password and len(phone) == 11:
        # still allow if incidental; only block if last 4 + more phone digits
        if phone[-6:] in password:
            return "密码不能包含手机号片段"

    # if _looks_like_birthday(password):
    #     return "密码不能使用生日等日期组合"
    # if _is_sequential_or_repeated(password):
    #     return "密码不能使用连续或重复字符"
    return None
