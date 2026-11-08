"""Autenticación por clave compartida.

Las rutas de consulta y matrícula requieren la cabecera X-API-Key. La clave
esperada se lee de API_ACCESS_KEY y se compara con tiempo constante.
"""
from __future__ import annotations

import hmac

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from .config import access_key

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(key: str | None = Security(api_key_header)) -> None:
    """Exige la clave compartida antes de consultar o modificar estudiantes."""
    expected = access_key()
    if not expected or not key or not hmac.compare_digest(key, expected):
        raise HTTPException(status_code=401, detail="Clave de API no válida")
