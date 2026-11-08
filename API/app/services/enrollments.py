"""Altas, modificaciones y bajas de matrículas.

Orden de escritura:

    * Alta: primero SQLite (queda como pendiente) y después MariaDB. Si MariaDB
      falla, la fila permanece en SQLite y se replica en el siguiente arranque.
    * Modificación y baja: se aplican en MariaDB y después se refresca la copia
      local, para no dejar una fila local que MariaDB desconozca.
"""
from __future__ import annotations

import csv
from datetime import date
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select

from ..db import mariadb, sqlite
from ..models.enrollment import Enrollment
from ..models.schemas import EnrollmentCreate, EnrollmentIn, EnrollmentOut
from . import history
from .identifiers import first_surname, identity_prefix


def generate_student_id(session: Any, data: EnrollmentIn, exclude_id: str | None = None) -> str:
    """Genera un identificador libre comprobando SQLite, MariaDB e históricos."""
    base = "-".join((identity_prefix(data.house, 2), identity_prefix(data.full_name, 3),
                     identity_prefix(first_surname(data.apellido), 3)))
    used = set(session.scalars(select(Enrollment.student_id)).all())
    used |= sqlite.identifiers()
    for config in history.SOURCES.values():
        try:
            with history.source_connection(config["kind"]) as connection:
                cursor = connection.cursor()
                try:
                    cursor.execute("SELECT id FROM students")
                    used.update(str(row[0]) for row in cursor.fetchall())
                finally:
                    cursor.close()
        except Exception as error:
            raise HTTPException(503, "No se pueden verificar los identificadores históricos") from error
    if exclude_id:
        used.discard(exclude_id)
    candidate = base
    suffix = 2
    while candidate in used:
        candidate = f"{base}-{suffix:02d}"
        suffix += 1
    return candidate


def _values(data: EnrollmentIn, student_id: str) -> dict[str, Any]:
    """Campos de la matrícula listos para SQLite y MariaDB."""
    return {**data.model_dump(exclude={"student_id"}), "student_id": student_id}


def _birth(value: Any) -> date | None:
    """Convierte la fecha guardada como texto ISO en el tipo esperado por MariaDB."""
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def create(data: EnrollmentCreate) -> EnrollmentOut:
    """Guarda la matrícula primero en SQLite y después la replica en MariaDB."""
    values = data.model_dump(exclude={"student_id"})
    stored = False
    try:
        with mariadb.identity_session() as session:
            values["student_id"] = generate_student_id(session, data)
            sqlite.save_enrollment(values)
            stored = True
            row = Enrollment(**values)
            session.add(row)
            session.flush()
            mariadb_id = row.id
    except HTTPException:
        raise
    except Exception as error:
        detail = ("Matrícula guardada en SQLite pendiente de sincronizar con MariaDB"
                  if stored else "MariaDB no está disponible")
        raise HTTPException(503, detail) from error
    sqlite.mark_synced(values["student_id"], mariadb_id)
    return EnrollmentOut(id=mariadb_id, **values)


def update(student_id: str, data: EnrollmentIn) -> EnrollmentOut:
    """Modifica en MariaDB la matrícula indicada y refresca la copia local."""
    with mariadb.identity_session() as session:
        row = session.scalar(select(Enrollment).where(Enrollment.student_id == student_id))
        local = sqlite.enrollment(student_id)
        if not row and not local:
            raise HTTPException(404, "Matrícula no encontrada en MariaDB")
        changed = (data.full_name, data.apellido, data.house) != (
            row.full_name, row.apellido, row.house) if row else True
        new_id = generate_student_id(session, data, exclude_id=student_id) if changed else student_id
        values = _values(data, new_id)
        if not row:
            # Pendiente de sincronizar: solo existe en SQLite.
            sqlite.save_enrollment(values, previous_id=student_id)
            return EnrollmentOut(id=local.get("mariadb_id") or 0, **values)
        for key, value in data.model_dump(exclude={"student_id"}).items():
            setattr(row, key, value)
        row.student_id = new_id
        session.flush()
        sqlite.save_enrollment(values, previous_id=student_id)
        sqlite.mark_synced(new_id, row.id)
        return EnrollmentOut(id=row.id, **values)


def delete(student_id: str) -> dict[str, str]:
    """Elimina de MariaDB una matrícula nueva y después su copia local."""
    with mariadb.Session.begin() as session:
        row = session.scalar(select(Enrollment).where(Enrollment.student_id == student_id))
        if not row:
            if not sqlite.delete_enrollment(student_id):
                raise HTTPException(404, "Matrícula no encontrada en MariaDB")
            return {"status": "deleted"}
        session.delete(row)
    sqlite.delete_enrollment(student_id)
    return {"status": "deleted"}


def seed_from_csv() -> None:
    """Carga Central.csv en MariaDB solo si no hay matrículas, sin sobrescribirlas."""
    path = history.CSV_DIR / "Central.csv"
    if not path.exists():
        return
    with mariadb.identity_session() as session:
        if session.scalar(select(Enrollment.id).limit(1)) is not None:
            return
        with path.open(encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            required = {"student_id", "full_name", "apellido", "house", "birth_date"}
            if not required.issubset(reader.fieldnames or []):
                raise ValueError("Central.csv: faltan columnas de matrícula")
            seen = set()
            for line, row in enumerate(reader, start=2):
                student_id = (row.get("student_id") or "").strip()
                if not student_id or len(student_id) > 64 or student_id in seen:
                    raise ValueError(f"Central.csv, línea {line}: student_id vacío, duplicado o demasiado largo")
                values = EnrollmentIn(
                    student_id=student_id,
                    full_name=row.get("full_name") or "",
                    apellido=row.get("apellido") or "",
                    house=row.get("house") or "",
                    birth_date=row.get("birth_date") or None,
                )
                if values.house != "Central":
                    raise ValueError(f"Central.csv, línea {line}: la casa debe ser Central")
                session.add(Enrollment(**values.model_dump()))
                seen.add(student_id)
            session.flush()


def push_pending() -> None:
    """Replica en MariaDB las altas que solo quedaron guardadas en SQLite."""
    for row in sqlite.pending():
        values = {
            "student_id": row["student_id"],
            "full_name": row["full_name"],
            "apellido": row["apellido"],
            "house": row["house"],
            "birth_date": _birth(row.get("birth_date")),
        }
        try:
            with mariadb.identity_session() as session:
                existing = session.scalar(select(Enrollment).where(Enrollment.student_id == values["student_id"]))
                if existing:
                    mariadb_id = existing.id
                else:
                    new = Enrollment(**values)
                    session.add(new)
                    session.flush()
                    mariadb_id = new.id
        except Exception as error:
            print(f"pending enrollment sync failed: {error}", flush=True)
            continue
        sqlite.mark_synced(values["student_id"], mariadb_id)


def mirror_from_mariadb() -> None:
    """Copia en SQLite las matrículas que todavía no están en la copia local."""
    with mariadb.Session() as session:
        rows = session.scalars(select(Enrollment).order_by(Enrollment.id)).all()
        for row in rows:
            sqlite.mirror_enrollment(
                {
                    "student_id": row.student_id,
                    "full_name": row.full_name,
                    "apellido": row.apellido,
                    "house": row.house,
                    "birth_date": row.birth_date,
                },
                row.id,
            )


def sync() -> None:
    """Prepara los datos iniciales, reintenta pendientes y completa SQLite."""
    seed_from_csv()
    push_pending()
    mirror_from_mariadb()
