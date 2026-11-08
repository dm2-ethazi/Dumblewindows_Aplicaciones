"""Rutas de alta, modificación y baja de matrículas."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..models.schemas import EnrollmentCreate, EnrollmentIn, EnrollmentOut
from ..security import require_api_key
from ..services import enrollments

router = APIRouter(tags=["Matrículas"])


@router.post("/enrollments", dependencies=[Depends(require_api_key)], response_model=EnrollmentOut, status_code=201, include_in_schema=False)
@router.post("/matriculas", dependencies=[Depends(require_api_key)], response_model=EnrollmentOut, status_code=201, summary="Crear matrícula", description="Guarda la matrícula primero en SQLite y después la replica en MariaDB. Si se omite house, usa Central. Genera student_id con las dos primeras letras de la casa, las tres del nombre y las tres del primer apellido; ignora el ID enviado por el cliente. Comprueba SQLite, MariaDB y las cuatro bases históricas y añade -02, -03, etc. si el ID ya existe. No escribe en bases históricas.")
def create_enrollment(data: EnrollmentCreate) -> EnrollmentOut:
    """Inserta una matrícula nueva con SQLite como primera escritura."""
    return enrollments.create(data)


@router.put("/enrollments/{student_id}", dependencies=[Depends(require_api_key)], response_model=EnrollmentOut, include_in_schema=False)
@router.put("/matriculas/{student_id}", dependencies=[Depends(require_api_key)], response_model=EnrollmentOut, summary="Modificar matrícula", description="Actualiza exclusivamente una matrícula nueva de MariaDB y refresca su copia local en SQLite.")
def update_enrollment(student_id: str, data: EnrollmentIn) -> EnrollmentOut:
    """Modifica en MariaDB la matrícula nueva indicada."""
    return enrollments.update(student_id, data)


@router.delete("/enrollments/{student_id}", dependencies=[Depends(require_api_key)], include_in_schema=False)
@router.delete("/matriculas/{student_id}", dependencies=[Depends(require_api_key)], summary="Eliminar matrícula", description="Elimina exclusivamente una matrícula nueva de MariaDB y su copia local en SQLite.")
def delete_enrollment(student_id: str) -> dict[str, str]:
    """Elimina de MariaDB una matrícula nueva; no toca las casas."""
    return enrollments.delete(student_id)
