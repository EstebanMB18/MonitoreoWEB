from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
)
from pydantic import BaseModel

from api.auth_dependencies import (
    get_current_user,
    require_roles,
)
from core.security.auth import (
    begin_mfa_setup,
    bootstrap_admin,
    confirm_mfa,
    create_user,
    login,
    logout,
    user_count,
)


router = APIRouter()


class BootstrapRequest(BaseModel):
    email: str
    password: str
    display_name: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str
    mfa_code: str | None = None


class CreateUserRequest(BaseModel):
    email: str
    password: str
    display_name: str | None = None
    role: str = "CONSULTA"


class MFAConfirmRequest(BaseModel):
    code: str


@router.get("/auth/status")
def auth_status():
    count = user_count()

    return {
        "initialized": count > 0,
        "users": count,
        "bootstrap_required": count == 0,
    }


@router.post("/auth/bootstrap")
def auth_bootstrap(
    payload: BootstrapRequest,
):
    try:
        user = bootstrap_admin(
            email=payload.email,
            password=payload.password,
            display_name=payload.display_name,
        )

        return {
            "user": user,
            "message": (
                "Administrador inicial "
                "creado correctamente."
            ),
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


@router.post("/auth/login")
def auth_login(
    payload: LoginRequest,
):
    try:
        return login(
            email=payload.email,
            password=payload.password,
            mfa_code=payload.mfa_code,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=401,
            detail=str(exc),
        )


@router.get("/auth/me")
def auth_me(
    user: dict = Depends(
        get_current_user
    ),
):
    return user


@router.post("/auth/logout")
def auth_logout(
    authorization: str | None = Header(
        default=None
    ),
    user: dict = Depends(
        get_current_user
    ),
):
    _, _, token = (
        authorization.partition(" ")
    )

    logout(
        token.strip()
    )

    return {
        "ok": True,
    }


@router.post("/auth/users")
def auth_create_user(
    payload: CreateUserRequest,
    user: dict = Depends(
        require_roles("ADMIN")
    ),
):
    try:
        created = create_user(
            email=payload.email,
            password=payload.password,
            display_name=payload.display_name,
            role=payload.role,
        )

        return {
            "user": created,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


@router.post("/auth/mfa/setup")
def auth_mfa_setup(
    user: dict = Depends(
        get_current_user
    ),
):
    try:
        return begin_mfa_setup(
            user["user_id"]
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


@router.post("/auth/mfa/confirm")
def auth_mfa_confirm(
    payload: MFAConfirmRequest,
    user: dict = Depends(
        get_current_user
    ),
):
    try:
        ok = confirm_mfa(
            user["user_id"],
            payload.code,
        )

        if not ok:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Codigo MFA invalido."
                ),
            )

        return {
            "enabled": True,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )
