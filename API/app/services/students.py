"""Consulta de estudiantes combinando SQLite, MariaDB y las fuentes históricas.

Orden de búsqueda: primero las matrículas de SQLite (primera escritura de la
API), después MariaDB como réplica central, luego la caché histórica en SQLite
y por último las bases históricas vivas.
"""
from __future__ import annotations

import json
import re

from fastapi import HTTPException
from sqlalchemy import select

from ..db import mariadb, sqlite
from ..models.enrollment import Enrollment, enrollment_to_student, local_to_student
from ..models.schemas import StudentOut
from . import history
from .identifiers import matches_student_base


def _local(name: str | None, house: str | None, limit: int) -> list[StudentOut]:
    """Matrículas guardadas en SQLite, la copia que se consulta primero."""
    return [local_to_student(row) for row in sqlite.enrollments(name, house, limit)]


def _mariadb(name: str | None, house: str | None, limit: int) -> list[StudentOut]:
    """Matrículas de MariaDB por si SQLite aún no las tiene replicadas."""
    with mariadb.Session() as session:
        query = select(Enrollment)
        if name:
            query = query.where((Enrollment.full_name + " " + Enrollment.apellido).icontains(name, autoescape=True))
        if house:
            query = query.where(Enrollment.house.ilike(house.replace("!", "!!").replace("%", "!%").replace("_", "!_"), escape="!"))
        rows = session.scalars(query.order_by(Enrollment.id).limit(limit)).all()
        return [enrollment_to_student(row) for row in rows]


def search(name: str | None, house: str | None, limit: int) -> list[StudentOut]:
    """Busca primero en SQLite, después en MariaDB y completa con históricos."""
    result = _local(name, house, limit)
    seen = {item.id for item in result}
    if len(result) < limit:
        for item in _mariadb(name, house, limit):
            if item.id not in seen:
                result.append(item)
                seen.add(item.id)
            if len(result) >= limit:
                break
    if len(result) >= limit:
        return result
    key = "search:live:v3:" + json.dumps([name or "", house or "", limit], ensure_ascii=False)
    hit = sqlite.cached(key)
    if hit is None:
        historical = history.find_history(name, house, limit)
        sqlite.cache(key, [item.model_dump() for item in historical])
    else:
        historical = [StudentOut(**item) for item in hit]
    for item in historical:
        if item.id not in seen:
            result.append(item)
            seen.add(item.id)
        if len(result) >= limit:
            break
    return result


def by_base(base: str) -> StudentOut | list[StudentOut]:
    """Devuelve todas las coincidencias de un ID base, sin duplicar identificadores."""
    result: dict[str, StudentOut] = {}
    for row in sqlite.enrollments_by_base(base):
        item = local_to_student(row)
        result[item.id] = item
    with mariadb.Session() as session:
        query = select(Enrollment).where(
            (Enrollment.student_id == base) | Enrollment.student_id.startswith(base + "-", autoescape=True)
        )
        for row in session.scalars(query.order_by(Enrollment.student_id)).all():
            if matches_student_base(row.student_id, base):
                result.setdefault(row.student_id, enrollment_to_student(row))
    key = f"student:base:v1:{base}"
    hit = sqlite.cached(key)
    if hit is None:
        historical = history.query_history_by_base(base)
        sqlite.cache(key, [item.model_dump() for item in historical])
    else:
        historical = [StudentOut(**item) for item in hit]
    for item in historical:
        result.setdefault(item.id, item)
    if not result:
        raise HTTPException(404, "Estudiante no encontrado")
    if len(result) == 1:
        return next(iter(result.values()))
    return sorted(result.values(), key=lambda item: item.id)


def get(student_id: str) -> StudentOut | list[StudentOut]:
    """Consulta un ID completo o todas las coincidencias de un ID base."""
    if re.fullmatch(r"[^-]+-[^-]+-[^-]+", student_id):
        return by_base(student_id)
    row = sqlite.enrollment(student_id)
    if row:
        return local_to_student(row)
    with mariadb.Session() as session:
        current = session.scalar(select(Enrollment).where(Enrollment.student_id == student_id))
        if current:
            return enrollment_to_student(current)
    hit = sqlite.cached(f"student:v3:{student_id}")
    if hit is not None:
        return StudentOut(**hit)
    result = history.query_history(student_id)
    if not result:
        raise HTTPException(404, "Estudiante no encontrado")
    sqlite.cache(f"student:v3:{student_id}", result.model_dump())
    return result
