"""Modelos de datos: tabla SQLAlchemy de matrículas y esquemas Pydantic."""
from .enrollment import Enrollment, enrollment_to_student, local_to_student
from .schemas import EnrollmentCreate, EnrollmentIn, EnrollmentOut, StudentOut

__all__ = [
    "Enrollment",
    "EnrollmentCreate",
    "EnrollmentIn",
    "EnrollmentOut",
    "StudentOut",
    "enrollment_to_student",
    "local_to_student",
]
