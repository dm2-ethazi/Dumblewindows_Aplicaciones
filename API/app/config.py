"""Configuración del servicio leída de variables de entorno.

Todas las rutas y credenciales se toman del entorno para no escribirlas en el
código. Los valores por defecto permiten arrancar dentro de Docker Compose.
"""
from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

MARIADB_URL = os.getenv(
    "MARIADB_URL",
    "mysql+pymysql://hogwarts_app:hogwarts_app@mariadb:3306/hogwarts",
)

# SQLite es el primer almacén de las matrículas nuevas y la caché de históricos.
CACHE_PATH = Path(os.getenv("CACHE_PATH", "/data/cache.sqlite3"))
CACHE_TTL = timedelta(seconds=int(os.getenv("CACHE_TTL_SECONDS", "86400")))

CSV_DIR = Path(os.getenv("HISTORY_CSV_DIR", "/app/data"))
JDBC = os.getenv("JDBC_DIR", "/opt/jdbc")

API_TITLE = "API de estudiantes de Hogwarts"
API_VERSION = "2.2.0"
API_DESCRIPTION = (
    "SQLite guarda primero las matrículas nuevas y su caché histórica; MariaDB replica las matrículas "
    "y conserva los datos de prueba de Central.csv. Derby, HSQLDB, H2 y Oracle son fuentes históricas "
    "de consulta. Las rutas en inglés siguen operativas para clientes anteriores pero no aparecen en /docs."
)


def access_key() -> str:
    """Clave compartida que deben enviar las rutas protegidas en X-API-Key."""
    return os.getenv("API_ACCESS_KEY", "")
