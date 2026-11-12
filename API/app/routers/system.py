"""Rutas de estado del servicio."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from sqlalchemy import select

from ..db import mariadb, sqlite
from ..models.enrollment import Enrollment
from ..services import history

router = APIRouter(tags=["Sistema"])


@router.get("/health", include_in_schema=False)
@router.get("/salud", summary="Estado del servicio", description="Comprueba MariaDB y devuelve R01, fuentes y ubicación de la caché SQLite.")
def health() -> dict[str, Any]:
    """Comprueba MariaDB y devuelve el estado R01 del servicio."""
    with mariadb.Session() as session:
        session.execute(select(Enrollment.id).limit(1)).first()
    return {
        "status": "ok",
        "code": "R01",
        "cache": str(sqlite.CACHE_PATH),
        "sources": {house: config["kind"] for house, config in history.SOURCES.items()},
        "no_migration": True,
    }
