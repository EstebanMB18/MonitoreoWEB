from __future__ import annotations

from collections.abc import Callable

from fastapi import (
    Header,
    HTTPException,
)

from core.security.auth import (
    authenticate_token,
)


def get_current_user(
    authorization: str | None = Header(
        default=None
    ),
) -> dict:
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Autenticacion requerida.",
        )

    scheme, _, token = (
        authorization.partition(" ")
    )

    if (
        scheme.lower() != "bearer"
        or not token
    ):
        raise HTTPException(
            status_code=401,
            detail="Token invalido.",
        )

    user = authenticate_token(
        token.strip()
    )

    if user is None:
        raise HTTPException(
            status_code=401,
            detail=(
                "Sesion invalida "
                "o expirada."
            ),
        )

    return user


def require_roles(
    *roles: str,
) -> Callable:
    allowed = {
        role.upper()
        for role in roles
    }

    def dependency(
        authorization: str | None = Header(
            default=None
        ),
    ) -> dict:
        user = get_current_user(
            authorization
        )

        if user["role"] not in allowed:
            raise HTTPException(
                status_code=403,
                detail=(
                    "No tiene permisos "
                    "para esta operacion."
                ),
            )

        return user

    return dependency
