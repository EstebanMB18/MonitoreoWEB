from __future__ import annotations

import base64
import ctypes
import json
import platform
from ctypes import wintypes
from datetime import datetime
from pathlib import Path
from typing import Protocol

from core.platform.paths import (
    ensure_user_directories,
)


class SecretStore(Protocol):
    def set(
        self,
        provider: str,
        secret: str,
    ) -> None:
        ...

    def get(
        self,
        provider: str,
    ) -> str | None:
        ...

    def delete(
        self,
        provider: str,
    ) -> bool:
        ...

    def status(
        self,
        provider: str,
    ) -> dict:
        ...


class DATA_BLOB(ctypes.Structure):
    _fields_ = [
        (
            "cbData",
            wintypes.DWORD,
        ),
        (
            "pbData",
            ctypes.POINTER(
                ctypes.c_byte
            ),
        ),
    ]


def _blob(
    data: bytes,
) -> tuple[DATA_BLOB, object]:
    buffer = ctypes.create_string_buffer(
        data
    )

    blob = DATA_BLOB(
        len(data),
        ctypes.cast(
            buffer,
            ctypes.POINTER(
                ctypes.c_byte
            ),
        ),
    )

    return blob, buffer


class WindowsDPAPISecretStore:
    def __init__(
        self,
        directory: Path | None = None,
    ):
        if platform.system() != "Windows":
            raise RuntimeError(
                "DPAPI solo esta disponible "
                "en Windows."
            )

        paths = ensure_user_directories()

        self.directory = (
            directory
            or paths["secrets"]
        )

        self.directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.crypt32 = ctypes.windll.crypt32
        self.kernel32 = ctypes.windll.kernel32

    def _path(
        self,
        provider: str,
    ) -> Path:
        safe = "".join(
            ch
            for ch in provider.upper()
            if ch.isalnum()
            or ch in {"_", "-"}
        )

        if not safe:
            raise ValueError(
                "Proveedor invalido."
            )

        return (
            self.directory
            / f"{safe}.secret"
        )

    def _protect(
        self,
        value: str,
    ) -> bytes:
        data = value.encode(
            "utf-8"
        )

        in_blob, in_buffer = _blob(
            data
        )

        out_blob = DATA_BLOB()

        result = (
            self.crypt32.CryptProtectData(
                ctypes.byref(
                    in_blob
                ),
                "Nexus",
                None,
                None,
                None,
                0,
                ctypes.byref(
                    out_blob
                ),
            )
        )

        if not result:
            raise ctypes.WinError()

        try:
            return ctypes.string_at(
                out_blob.pbData,
                out_blob.cbData,
            )
        finally:
            self.kernel32.LocalFree(
                out_blob.pbData
            )

    def _unprotect(
        self,
        data: bytes,
    ) -> str:
        in_blob, in_buffer = _blob(
            data
        )

        out_blob = DATA_BLOB()

        result = (
            self.crypt32.CryptUnprotectData(
                ctypes.byref(
                    in_blob
                ),
                None,
                None,
                None,
                None,
                0,
                ctypes.byref(
                    out_blob
                ),
            )
        )

        if not result:
            raise ctypes.WinError()

        try:
            raw = ctypes.string_at(
                out_blob.pbData,
                out_blob.cbData,
            )

            return raw.decode(
                "utf-8"
            )
        finally:
            self.kernel32.LocalFree(
                out_blob.pbData
            )

    def set(
        self,
        provider: str,
        secret: str,
    ) -> None:
        if not secret:
            raise ValueError(
                "El secreto no puede "
                "estar vacio."
            )

        encrypted = self._protect(
            secret
        )

        payload = {
            "schema_version": 1,
            "provider": provider.upper(),
            "encrypted": base64.b64encode(
                encrypted
            ).decode("ascii"),
            "updated_at": (
                datetime.now().isoformat()
            ),
        }

        path = self._path(
            provider
        )

        tmp = path.with_suffix(
            ".tmp"
        )

        tmp.write_text(
            json.dumps(
                payload,
                indent=2,
            ),
            encoding="utf-8",
        )

        tmp.replace(
            path
        )

    def get(
        self,
        provider: str,
    ) -> str | None:
        path = self._path(
            provider
        )

        if not path.exists():
            return None

        payload = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

        encrypted = base64.b64decode(
            payload["encrypted"]
        )

        return self._unprotect(
            encrypted
        )

    def delete(
        self,
        provider: str,
    ) -> bool:
        path = self._path(
            provider
        )

        if not path.exists():
            return False

        path.unlink()

        return True

    def status(
        self,
        provider: str,
    ) -> dict:
        path = self._path(
            provider
        )

        if not path.exists():
            return {
                "provider": provider.upper(),
                "configured": False,
                "updated_at": None,
            }

        payload = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

        return {
            "provider": provider.upper(),
            "configured": True,
            "updated_at": payload.get(
                "updated_at"
            ),
        }


def get_secret_store() -> SecretStore:
    system = platform.system()

    if system == "Windows":
        return WindowsDPAPISecretStore()

    raise RuntimeError(
        (
            f"SecretStore seguro para "
            f"{system} aun no implementado."
        )
    )
