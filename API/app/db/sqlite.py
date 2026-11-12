"""SQLite local: primera escritura de las matrículas y caché de históricos.

Dos tablas independientes conviven en CACHE_PATH:

    * local_enrollments guarda las matrículas escritas por la API. Es el primer
      destino de un alta y la copia local que se consulta antes que MariaDB.
      La columna synced indica si la fila ya se replicó en MariaDB.
    * student_cache conserva respuestas históricas temporales (CACHE_TTL) para
      no repetir consultas a Derby, HSQLDB, H2 y Oracle.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from typing import Any, Iterator

from ..config import CACHE_PATH, CACHE_TTL

CACHE_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS student_cache ("
    "cache_key TEXT PRIMARY KEY, payload TEXT NOT NULL, cached_at TEXT NOT NULL)"
)

ENROLLMENT_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS local_enrollments ("
    "student_id TEXT PRIMARY KEY, "
    "full_name TEXT NOT NULL, "
    "apellido TEXT NOT NULL, "
    "house TEXT, "
    "birth_date TEXT, "
    "mariadb_id INTEGER, "
    "synced INTEGER NOT NULL DEFAULT 0, "
    "updated_at TEXT NOT NULL)"
)

ENROLLMENT_COLUMNS = "student_id, full_name, apellido, house, birth_date"


def _now() -> str:
    return datetime.utcnow().isoformat()


def _iso_date(value: Any) -> str | None:
    """Guarda la fecha como texto ISO, que es el formato de SQLite."""
    if value is None or value == "":
        return None
    return value.isoformat() if isinstance(value, date) else str(value)


def _like(value: str) -> str:
    """Prepara un patrón LIKE escapando los comodines del valor buscado."""
    escaped = value.lower().replace("!", "!!").replace("%", "!%").replace("_", "!_")
    return f"%{escaped}%"


def connect() -> sqlite3.Connection:
    """Abre SQLite y garantiza las tablas de caché y de matrículas locales."""
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(CACHE_PATH)
    db.row_factory = sqlite3.Row
    db.execute(CACHE_SCHEMA)
    db.execute(ENROLLMENT_SCHEMA)
    db.commit()
    return db


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    """Cierra la conexión siempre, aunque la operación falle."""
    db = connect()
    try:
        yield db
        db.commit()
    finally:
        db.close()


def cached(key: str) -> Any | None:
    """Devuelve una respuesta histórica guardada mientras no expire el TTL."""
    with connection() as db:
        row = db.execute("SELECT payload,cached_at FROM student_cache WHERE cache_key=?", (key,)).fetchone()
        if not row or datetime.fromisoformat(row["cached_at"]) + CACHE_TTL <= datetime.utcnow():
            return None
        return json.loads(row["payload"])


def cache(key: str, payload: Any) -> None:
    """Guarda respuestas de consultas históricas en el archivo SQLite."""
    with connection() as db:
        db.execute(
            "INSERT OR REPLACE INTO student_cache(cache_key,payload,cached_at) VALUES(?,?,?)",
            (key, json.dumps(payload, ensure_ascii=False), _now()),
        )


def save_enrollment(values: dict[str, Any], previous_id: str | None = None) -> None:
    """Escribe la matrícula en SQLite antes de enviarla a MariaDB.

    Queda marcada como pendiente (synced=0) hasta que MariaDB confirma el alta.
    Si el identificador cambió, se elimina la fila anterior.
    """
    with connection() as db:
        if previous_id and previous_id != values["student_id"]:
            db.execute("DELETE FROM local_enrollments WHERE student_id=?", (previous_id,))
        db.execute(
            "INSERT INTO local_enrollments(student_id,full_name,apellido,house,birth_date,mariadb_id,synced,updated_at) "
            "VALUES(?,?,?,?,?,NULL,0,?) "
            "ON CONFLICT(student_id) DO UPDATE SET full_name=excluded.full_name, "
            "apellido=excluded.apellido, house=excluded.house, birth_date=excluded.birth_date, "
            "mariadb_id=NULL, synced=0, updated_at=excluded.updated_at",
            (
                values["student_id"],
                values["full_name"],
                values["apellido"],
                values.get("house"),
                _iso_date(values.get("birth_date")),
                _now(),
            ),
        )


def mirror_enrollment(values: dict[str, Any], mariadb_id: int | None) -> None:
    """Copia en SQLite una matrícula ya confirmada en MariaDB.

    No sobrescribe filas locales pendientes de sincronizar.
    """
    with connection() as db:
        db.execute(
            "INSERT OR IGNORE INTO local_enrollments"
            "(student_id,full_name,apellido,house,birth_date,mariadb_id,synced,updated_at) "
            "VALUES(?,?,?,?,?,?,1,?)",
            (
                values["student_id"],
                values["full_name"],
                values["apellido"],
                values.get("house"),
                _iso_date(values.get("birth_date")),
                mariadb_id,
                _now(),
            ),
        )


def mark_synced(student_id: str, mariadb_id: int | None) -> None:
    """Marca como replicada en MariaDB una matrícula guardada en SQLite."""
    with connection() as db:
        db.execute(
            "UPDATE local_enrollments SET mariadb_id=?, synced=1 WHERE student_id=?",
            (mariadb_id, student_id),
        )


def enrollment(student_id: str) -> dict[str, Any] | None:
    """Devuelve la copia local de una matrícula concreta."""
    with connection() as db:
        row = db.execute(
            "SELECT * FROM local_enrollments WHERE student_id=?",
            (student_id,),
        ).fetchone()
    return dict(row) if row else None


def enrollments(name: str | None = None, house: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    """Busca matrículas locales por nombre y casa, en orden de alta."""
    query = f"SELECT {ENROLLMENT_COLUMNS} FROM local_enrollments"
    clauses: list[str] = []
    params: list[Any] = []
    if name:
        clauses.append("LOWER(full_name || ' ' || apellido) LIKE ? ESCAPE '!'")
        params.append(_like(name))
    if house:
        clauses.append("LOWER(house) = LOWER(?)")
        params.append(house)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY rowid LIMIT ?"
    params.append(limit)
    with connection() as db:
        return [dict(row) for row in db.execute(query, params).fetchall()]


def enrollments_by_base(base: str) -> list[dict[str, Any]]:
    """Devuelve el ID base y sus variantes locales con sufijo -NN."""
    escaped = base.replace("!", "!!").replace("%", "!%").replace("_", "!_")
    with connection() as db:
        rows = db.execute(
            f"SELECT {ENROLLMENT_COLUMNS} FROM local_enrollments "
            "WHERE student_id = ? OR student_id LIKE ? ESCAPE '!' ORDER BY student_id",
            (base, escaped + "-%"),
        ).fetchall()
    return [dict(row) for row in rows]


def identifiers() -> set[str]:
    """Identificadores ya usados por las matrículas locales."""
    with connection() as db:
        return {row[0] for row in db.execute("SELECT student_id FROM local_enrollments").fetchall()}


def pending() -> list[dict[str, Any]]:
    """Matrículas guardadas en SQLite que aún no están en MariaDB."""
    with connection() as db:
        rows = db.execute(
            f"SELECT {ENROLLMENT_COLUMNS} FROM local_enrollments WHERE synced=0 ORDER BY rowid"
        ).fetchall()
    return [dict(row) for row in rows]


def delete_enrollment(student_id: str) -> bool:
    """Elimina la copia local e informa de si existía."""
    with connection() as db:
        deleted = db.execute("DELETE FROM local_enrollments WHERE student_id=?", (student_id,)).rowcount > 0
    return deleted
