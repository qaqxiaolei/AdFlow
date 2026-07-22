"""本地手机号登录 / 注册 / 找回密码 API。"""

from __future__ import annotations

import base64
from typing import Optional

import nanoid
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from services.auth_service import (
    NEW_USER_FREE_CREDITS,
    create_access_token,
    decode_access_token,
    hash_password,
    issue_captcha,
    user_public_dict,
    validate_password,
    validate_phone,
    verify_and_consume_captcha,
    verify_password,
)
from services.db_service import db_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    phone: str
    password: str
    captcha_id: str
    captcha_code: str


class LoginRequest(BaseModel):
    phone: str
    password: str


class ResetPasswordRequest(BaseModel):
    phone: str
    password: str
    captcha_id: str
    captcha_code: str


async def get_current_user_id(
    authorization: Optional[str] = Header(default=None),
) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    token = authorization[7:].strip()
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="无效令牌")
        return str(user_id)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")


async def get_optional_user_id(
    authorization: Optional[str] = Header(default=None),
) -> Optional[str]:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        payload = decode_access_token(authorization[7:].strip())
        return str(payload.get("sub")) if payload.get("sub") else None
    except Exception:
        return None


@router.get("/captcha")
async def get_captcha():
    data = issue_captcha()
    image_b64 = base64.b64encode(data["image_bytes"]).decode("ascii")
    return {
        "status": "success",
        "captcha_id": data["captcha_id"],
        "image_base64": f"data:image/png;base64,{image_b64}",
    }


@router.post("/register")
async def register(body: RegisterRequest):
    captcha_err = verify_and_consume_captcha(body.captcha_id, body.captcha_code)
    if captcha_err:
        raise HTTPException(status_code=400, detail=captcha_err)

    phone_err = validate_phone(body.phone)
    if phone_err:
        raise HTTPException(status_code=400, detail=phone_err)

    phone = body.phone.strip()
    pwd_err = validate_password(body.password, phone)
    if pwd_err:
        raise HTTPException(status_code=400, detail=pwd_err)

    existing = await db_service.get_user_by_phone(phone)
    if existing:
        raise HTTPException(status_code=400, detail="该手机号已注册，请直接登录")

    user_id = nanoid.generate()
    password_hash = hash_password(body.password)
    user = await db_service.create_user(
        user_id, phone, password_hash, NEW_USER_FREE_CREDITS
    )
    token = create_access_token(user_id, phone)
    return {
        "status": "success",
        "token": token,
        "user_info": user_public_dict(user),
        "message": f"注册成功，已赠送 {int(NEW_USER_FREE_CREDITS)} 积分",
    }


@router.post("/login")
async def login(body: LoginRequest):
    phone_err = validate_phone(body.phone)
    if phone_err:
        raise HTTPException(status_code=400, detail=phone_err)

    phone = body.phone.strip()
    if not body.password:
        raise HTTPException(status_code=400, detail="请输入密码")

    user = await db_service.get_user_by_phone(phone)
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="手机号或密码错误")

    token = create_access_token(user["id"], phone)
    return {
        "status": "success",
        "token": token,
        "user_info": user_public_dict(user),
        "message": "登录成功",
    }


@router.post("/forgot-password/reset")
async def forgot_password_reset(body: ResetPasswordRequest):
    captcha_err = verify_and_consume_captcha(body.captcha_id, body.captcha_code)
    if captcha_err:
        raise HTTPException(status_code=400, detail=captcha_err)

    phone_err = validate_phone(body.phone)
    if phone_err:
        raise HTTPException(status_code=400, detail=phone_err)

    phone = body.phone.strip()
    pwd_err = validate_password(body.password, phone)
    if pwd_err:
        raise HTTPException(status_code=400, detail=pwd_err)

    user = await db_service.get_user_by_phone(phone)
    if not user:
        raise HTTPException(status_code=404, detail="该手机号未注册")

    await db_service.update_user_password(user["id"], hash_password(body.password))
    return {
        "status": "success",
        "message": "密码已重置，请使用新密码登录",
    }


@router.get("/me")
async def me(user_id: str = Depends(get_current_user_id)):
    user = await db_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    return {"status": "success", "user_info": user_public_dict(user)}


@router.get("/refresh-token")
async def refresh_token(user_id: str = Depends(get_current_user_id)):
    user = await db_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    new_token = create_access_token(user["id"], user["phone"])
    return {"status": "success", "new_token": new_token, "user_info": user_public_dict(user)}
