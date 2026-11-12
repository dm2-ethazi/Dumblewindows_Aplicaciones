"""Rutas de consulta de estudiantes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..models.schemas import StudentOut
from ..security import require_api_key
from ..services import students

router = APIRouter(tags=["Consultas"])


@router.get("/students", dependencies=[Depends(require_api_key)], response_model=list[StudentOut], include_in_schema=False)
@router.get("/estudiantes", dependencies=[Depends(require_api_key)], response_model=list[StudentOut], summary="Buscar estudiantes por datos", description="Busca primero las matrículas guardadas en SQLite, después las de MariaDB y finalmente los históricos en caché y en las bases vivas. Combina resultados sin duplicar IDs, con prioridad para las matrículas.")
def search_students(
    name: str | None = Query(default=None),
    house: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[StudentOut]:
    """Consulta las matrículas locales antes de la caché histórica."""
    return students.search(name, house, limit)


@router.get("/students/{student_id}", dependencies=[Depends(require_api_key)], response_model=StudentOut | list[StudentOut], include_in_schema=False)
@router.get("/estudiantes/{student_id}", dependencies=[Depends(require_api_key)], response_model=StudentOut | list[StudentOut], summary="Consultar estudiante por ID", description="Acepta el ID base (por ejemplo GR-HAR-POT) o un ID completo con sufijo. Si el ID base coincide con varios estudiantes, devuelve una lista con todos los datos de cada estudiante. Una sola coincidencia devuelve el detalle habitual; sin coincidencias, 404. Combina la copia local SQLite con MariaDB y con históricos cacheados en SQLite.")
def get_student(student_id: str) -> StudentOut | list[StudentOut]:
    """Consulta un ID completo o todas las coincidencias de un ID base."""
    return students.get(student_id)
