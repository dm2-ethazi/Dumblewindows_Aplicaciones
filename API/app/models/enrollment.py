"""Modelo de matrículas de MariaDB y conversión al formato de respuesta."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..db.mariadb import Base
from .schemas import StudentOut


class Enrollment(Base):
    """Matrícula nueva de Secretaría; nunca es una fila histórica."""
    __tablename__ = "enrollments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[str] = mapped_column(String(64), unique=True)
    full_name: Mapped[str] = mapped_column(String(200))
    apellido: Mapped[str] = mapped_column(String(200))
    house: Mapped[str | None] = mapped_column(String(80), nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


def enrollment_to_student(row: Enrollment) -> StudentOut:
    """Convierte una matrícula de MariaDB al formato común, incluida la fecha ISO."""
    birth = row.birth_date.isoformat() if row.birth_date else None
    return _student(row.student_id, row.full_name, row.apellido, row.house, birth)


def local_to_student(values: dict[str, Any]) -> StudentOut:
    """Convierte una fila de la copia local SQLite al formato común."""
    birth = values.get("birth_date") or None
    return _student(values["student_id"], values["full_name"], values["apellido"], values.get("house"), birth)


def _student(student_id: str, full_name: str, apellido: str, house: str | None, birth: str | None) -> StudentOut:
    return StudentOut(id=student_id, nombre=full_name, apellido=apellido, casa=house or "",
                      nacimiento=birth, fecha_nacimiento=birth, origen="mariadb")
