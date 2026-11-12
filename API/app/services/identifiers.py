"""Utilidades de identificadores de estudiante.

El identificador se forma con la casa, el nombre y el primer apellido:
dos letras de la casa, tres del nombre y tres del primer apellido.
"""
from __future__ import annotations

import re
import unicodedata

from fastapi import HTTPException


def first_surname(apellido: str) -> str:
    """Devuelve el primer apellido, conservando partículas como «de» o «van»."""
    words = apellido.split()
    surname = [words[0]]
    index = 1
    particles = {"de", "del", "la", "las", "los", "van", "von", "da", "das", "do", "dos", "di"}
    while surname[-1].casefold() in particles and index < len(words):
        surname.append(words[index])
        index += 1
    return " ".join(surname)


def identity_prefix(value: str, size: int) -> str:
    """Toma las primeras letras ASCII en mayúscula del valor indicado."""
    normalized = unicodedata.normalize("NFKD", value)
    letters = "".join(char for char in normalized if char.isascii() and char.isalpha()).upper()
    if not letters:
        raise HTTPException(422, "Nombre, apellido y casa deben contener letras")
    return letters[:size]


def matches_student_base(student_id: str, base: str) -> bool:
    """Comprueba si el ID es el base o una variante con sufijo -NN."""
    return student_id == base or re.fullmatch(re.escape(base) + r"-\d+", student_id) is not None
