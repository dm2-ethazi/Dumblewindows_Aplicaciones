"""Conexión a MariaDB, réplica central de las matrículas.

Las altas se escriben primero en SQLite y después se replican aquí. El bloqueo
de MariaDB serializa la generación de identificadores entre procesos.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from ..config import MARIADB_URL


class Base(DeclarativeBase):
    """Base SQLAlchemy de las tablas alojadas en MariaDB."""
    pass


engine = create_engine(MARIADB_URL, pool_pre_ping=True)
Session = sessionmaker(engine, expire_on_commit=False)


def create_schema() -> None:
    """Crea la tabla de matrículas a partir de los modelos ya importados."""
    Base.metadata.create_all(engine)


@contextmanager
def identity_session() -> Iterator[Any]:
    """Reserva el bloqueo de identificadores y agrupa la escritura en MariaDB."""
    with engine.connect() as connection:
        locked = connection.execute(text("SELECT GET_LOCK('student_identity', 15)")).scalar()
        connection.commit()
        if locked != 1:
            raise HTTPException(503, "No se pudo reservar el identificador; vuelve a intentarlo")
        try:
            with Session(bind=connection) as session:
                with session.begin():
                    yield session
        finally:
            connection.execute(text("SELECT RELEASE_LOCK('student_identity')"))
            connection.commit()
