from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import uuid
from datetime import (
    datetime,
    timedelta,
)

from api.storage import get_connection
from core.platform import get_secret_store
from core.security.totp import (
    build_otpauth_uri,
    generate_totp_secret,
    verify_totp,
)


ROLES = {
    "ADMIN",
    "MONITOR_OFICIAL",
    "OPERADOR",
    "CONSULTA",
}

SESSION_HOURS = 12

PASSWORD_SCHEME = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 600_000
PASSWORD_SALT_BYTES = 16
PASSWORD_HASH_BYTES = 32


def hash_password(
    password: str,
) -> str:
    if not password:
        raise ValueError(
            "La contrase?a no puede estar vacia."
        )

    salt = secrets.token_bytes(
        PASSWORD_SALT_BYTES
    )

    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_ITERATIONS,
        dklen=PASSWORD_HASH_BYTES,
    )

    salt_b64 = base64.urlsafe_b64encode(
        salt
    ).decode("ascii")

    hash_b64 = base64.urlsafe_b64encode(
        derived
    ).decode("ascii")

    return (
        f"{PASSWORD_SCHEME}"
        f"${PASSWORD_ITERATIONS}"
        f"${salt_b64}"
        f"${hash_b64}"
    )


def verify_password(
    password: str,
    stored: str,
) -> bool:
    try:
        scheme, raw_iterations, salt_b64, hash_b64 = (
            stored.split("$", 3)
        )

        if scheme != PASSWORD_SCHEME:
            return False

        iterations = int(
            raw_iterations
        )

        if iterations < 100_000:
            return False

        salt = base64.urlsafe_b64decode(
            salt_b64.encode("ascii")
        )

        expected = base64.urlsafe_b64decode(
            hash_b64.encode("ascii")
        )

        candidate = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            iterations,
            dklen=len(expected),
        )

        return hmac.compare_digest(
            candidate,
            expected,
        )

    except (
        ValueError,
        TypeError,
        UnicodeError,
    ):
        return False


def _now() -> datetime:
    return datetime.now()


def _token_hash(
    token: str,
) -> str:
    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


def normalize_email(
    email: str,
) -> str:
    return email.strip().lower()


def user_count() -> int:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS total "
            "FROM users"
        ).fetchone()

    return int(row["total"])


def create_user(
    *,
    email: str,
    password: str,
    display_name: str | None,
    role: str,
) -> dict:
    email = normalize_email(email)
    role = role.upper()

    if not email or "@" not in email:
        raise ValueError(
            "Correo invalido."
        )

    if len(password) < 10:
        raise ValueError(
            "La contraseña debe tener "
            "al menos 10 caracteres."
        )

    if role not in ROLES:
        raise ValueError(
            "Rol invalido."
        )

    user_id = str(
        uuid.uuid4()
    )

    now = _now().isoformat()

    password_hash = hash_password(
        password
    )

    try:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO users (
                    user_id,
                    email,
                    display_name,
                    password_hash,
                    role,
                    active,
                    mfa_enabled,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, 1, 0, ?, ?)
                """,
                (
                    user_id,
                    email,
                    display_name,
                    password_hash,
                    role,
                    now,
                    now,
                ),
            )
            conn.commit()
    except Exception as exc:
        raise ValueError(
            "El usuario ya existe "
            "o no pudo ser creado."
        ) from exc

    return get_user(
        user_id
    )


def bootstrap_admin(
    *,
    email: str,
    password: str,
    display_name: str | None,
) -> dict:
    if user_count() != 0:
        raise ValueError(
            "El administrador inicial "
            "ya fue creado."
        )

    return create_user(
        email=email,
        password=password,
        display_name=display_name,
        role="ADMIN",
    )


def get_user(
    user_id: str,
) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT
                user_id,
                email,
                display_name,
                role,
                active,
                mfa_enabled,
                created_at,
                updated_at,
                last_login_at
            FROM users
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

    if row is None:
        return None

    item = dict(row)

    item["active"] = bool(
        item["active"]
    )

    item["mfa_enabled"] = bool(
        item["mfa_enabled"]
    )

    return item


def get_user_by_email(
    email: str,
):
    email = normalize_email(
        email
    )

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM users
            WHERE email = ?
            """,
            (email,),
        ).fetchone()

    return (
        dict(row)
        if row
        else None
    )


def _mfa_provider(
    user_id: str,
) -> str:
    return (
        "NEXUS_MFA_"
        + user_id.replace("-", "")
    )


def begin_mfa_setup(
    user_id: str,
) -> dict:
    user = get_user(
        user_id
    )

    if user is None:
        raise ValueError(
            "Usuario no encontrado."
        )

    secret = generate_totp_secret()

    store = get_secret_store()

    store.set(
        _mfa_provider(user_id),
        secret,
    )

    return {
        "secret": secret,
        "otpauth_uri": build_otpauth_uri(
            secret,
            user["email"],
        ),
    }


def confirm_mfa(
    user_id: str,
    code: str,
) -> bool:
    store = get_secret_store()

    secret = store.get(
        _mfa_provider(user_id)
    )

    if not secret:
        raise ValueError(
            "MFA no fue configurado."
        )

    if not verify_totp(
        secret,
        code,
    ):
        return False

    now = _now().isoformat()

    with get_connection() as conn:
        conn.execute(
            """
            UPDATE users
            SET
                mfa_enabled = 1,
                updated_at = ?
            WHERE user_id = ?
            """,
            (
                now,
                user_id,
            ),
        )
        conn.commit()

    return True


def login(
    *,
    email: str,
    password: str,
    mfa_code: str | None = None,
) -> dict:
    user = get_user_by_email(
        email
    )

    if (
        user is None
        or not bool(user["active"])
    ):
        raise ValueError(
            "Credenciales invalidas."
        )

    if not verify_password(
        password,
        user["password_hash"],
    ):
        raise ValueError(
            "Credenciales invalidas."
        )

    if bool(
        user["mfa_enabled"]
    ):
        if not mfa_code:
            return {
                "mfa_required": True,
            }

        store = get_secret_store()

        secret = store.get(
            _mfa_provider(
                user["user_id"]
            )
        )

        if (
            not secret
            or not verify_totp(
                secret,
                mfa_code,
            )
        ):
            raise ValueError(
                "Codigo MFA invalido."
            )

    token = secrets.token_urlsafe(
        48
    )

    created = _now()
    expires = (
        created
        + timedelta(
            hours=SESSION_HOURS
        )
    )

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO auth_sessions (
                token_hash,
                user_id,
                created_at,
                expires_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                _token_hash(token),
                user["user_id"],
                created.isoformat(),
                expires.isoformat(),
            ),
        )

        conn.execute(
            """
            UPDATE users
            SET last_login_at = ?
            WHERE user_id = ?
            """,
            (
                created.isoformat(),
                user["user_id"],
            ),
        )

        conn.commit()

    return {
        "mfa_required": False,
        "access_token": token,
        "token_type": "bearer",
        "expires_at": expires.isoformat(),
        "user": get_user(
            user["user_id"]
        ),
    }


def authenticate_token(
    token: str,
) -> dict | None:
    now = _now().isoformat()

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT s.user_id
            FROM auth_sessions s
            JOIN users u
              ON u.user_id = s.user_id
            WHERE s.token_hash = ?
              AND s.revoked_at IS NULL
              AND s.expires_at > ?
              AND u.active = 1
            """,
            (
                _token_hash(token),
                now,
            ),
        ).fetchone()

    if row is None:
        return None

    return get_user(
        row["user_id"]
    )


def logout(
    token: str,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE auth_sessions
            SET revoked_at = ?
            WHERE token_hash = ?
            """,
            (
                _now().isoformat(),
                _token_hash(token),
            ),
        )
        conn.commit()
