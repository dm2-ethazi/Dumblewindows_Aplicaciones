"""API de estudiantes de Hogwarts.

Este módulo solo monta la aplicación: la configuración vive en `config`, la
autenticación en `security`, el acceso a datos en `db`, los modelos en `models`,
la lógica en `services` y las rutas en `routers`.

Arquitectura:
    * SQLite, en CACHE_PATH, guarda primero las matrículas nuevas y las
      respuestas históricas temporales (CACHE_TTL_SECONDS).
    * MariaDB replica las matrículas creadas por la API y conserva los datos de
      prueba de Central.csv cuando la tabla está vacía.
    * Derby, HSQLDB, H2 y Oracle contienen fuentes históricas separadas por
      casas; se consultan por identificador cuando hace falta.
    * Los CSV de CSV_DIR inicializan las tablas históricas vacías; las
      búsquedas consultan las bases de datos vivas.

Seguridad:
    Las rutas de consulta y matrícula requieren la cabecera X-API-Key.

Rutas públicas:
    /salud y /health informan del estado del servicio. Las rutas en español son
    la interfaz documentada; sus alias en inglés se mantienen para compatibilidad
    y se ocultan del esquema OpenAPI.
"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from .config import API_DESCRIPTION, API_TITLE, API_VERSION
from .db import mariadb, sqlite
from .models import Enrollment  # noqa: F401  (registra la tabla en Base.metadata)
from .routers import enrollments, students, system
from .services import enrollments as enrollments_service
from .services import history


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Prepara MariaDB, SQLite y, si es necesario, las fuentes históricas."""
    mariadb.create_schema()
    sqlite.connect().close()
    enrollments_service.sync()
    time.sleep(3)
    history.create_history_tables()
    yield


app = FastAPI(title=API_TITLE, version=API_VERSION, description=API_DESCRIPTION, lifespan=lifespan)
app.include_router(system.router)
app.include_router(students.router)
app.include_router(enrollments.router)
