"""Esquemas Pydantic de entrada y salida de la API."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EnrollmentIn(BaseModel):
    """Campos recibidos al crear o modificar una matrícula."""
    student_id: str | None = Field(default=None, max_length=64, description="Se genera automáticamente; el valor enviado no se utiliza")
    full_name: str = Field(min_length=1, max_length=200, description="Nombre o nombres de pila, sin apellido")
    apellido: str = Field(min_length=1, max_length=200)
    house: str = Field(min_length=2, max_length=80)

    @field_validator("full_name", "apellido", "house")
    @classmethod
    def validate_identity(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value or not any(char.isalpha() for char in value):
            raise ValueError("Debe contener un nombre real, no un campo vacío")
        if any(term in value.casefold() for term in ("father of", "mother of", "unnamed", "unknown", "quidditch player")):
            raise ValueError("No se admiten descripciones en lugar de nombres")
        return value

    birth_date: date | None = None


class EnrollmentCreate(EnrollmentIn):
    """Alta con casa Central por defecto e identificador generado por la API."""
    house: str = Field(default="Central", min_length=2, max_length=15)


class EnrollmentOut(EnrollmentIn):
    """Matrícula devuelta con su identificador interno de MariaDB."""
    model_config = ConfigDict(from_attributes=True)
    student_id: str
    id: int


class StudentOut(BaseModel):
    """Formato común de respuesta para estudiantes de cualquier origen."""
    id: str
    nombre: str
    apellido: str
    casa: str
    alias: str | None = None
    especie: str | None = None
    genero: str | None = None
    nacimiento: str | None = None
    fecha_nacimiento: str | None = None
    nacionalidad: str | None = None
    patronus: str | None = None
    patronus_origen: str | None = None
    imagen: str | None = None
    wiki: str | None = None
    origen: str
