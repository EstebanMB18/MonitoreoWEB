from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time


def generate_totp_secret() -> str:
    return base64.b32encode(
        secrets.token_bytes(20)
    ).decode("ascii").rstrip("=")


def _decode_secret(
    secret: str,
) -> bytes:
    padding = "=" * (
        (8 - len(secret) % 8) % 8
    )

    return base64.b32decode(
        secret.upper() + padding
    )


def totp_code(
    secret: str,
    timestamp: int | None = None,
    interval: int = 30,
    digits: int = 6,
) -> str:
    now = (
        int(time.time())
        if timestamp is None
        else int(timestamp)
    )

    counter = now // interval

    msg = struct.pack(
        ">Q",
        counter,
    )

    digest = hmac.new(
        _decode_secret(secret),
        msg,
        hashlib.sha1,
    ).digest()

    offset = digest[-1] & 0x0F

    value = (
        struct.unpack(
            ">I",
            digest[offset:offset + 4],
        )[0]
        & 0x7FFFFFFF
    )

    return str(
        value % (10 ** digits)
    ).zfill(digits)


def verify_totp(
    secret: str,
    code: str,
    window: int = 1,
) -> bool:
    clean = str(code).strip()

    if (
        len(clean) != 6
        or not clean.isdigit()
    ):
        return False

    now = int(time.time())

    for delta in range(
        -window,
        window + 1,
    ):
        candidate = totp_code(
            secret,
            timestamp=(
                now + delta * 30
            ),
        )

        if hmac.compare_digest(
            candidate,
            clean,
        ):
            return True

    return False


def build_otpauth_uri(
    secret: str,
    email: str,
) -> str:
    from urllib.parse import quote

    issuer = "Nexus Monitoreo"

    label = quote(
        f"{issuer}:{email}"
    )

    issuer_encoded = quote(
        issuer
    )

    return (
        f"otpauth://totp/{label}"
        f"?secret={secret}"
        f"&issuer={issuer_encoded}"
        f"&algorithm=SHA1"
        f"&digits=6"
        f"&period=30"
    )
