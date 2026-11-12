"""Consultas a las fuentes históricas: Derby, HSQLDB, H2 y Oracle.

Los CSV de CSV_DIR inicializan las tablas históricas vacías; las búsquedas se
hacen siempre contra las bases vivas y nunca las modifican.
"""
from __future__ import annotations

import csv
import os
import re
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import jaydebeapi
import jpype
import oracledb
from fastapi import HTTPException

from ..config import CSV_DIR, JDBC
from ..models.schemas import StudentOut
from .identifiers import matches_student_base

SOURCES = {
    "Gryffindor": {"csv": "gryffindor.csv", "kind": "derby"},
    "Slytherin": {"csv": "slytherin.csv", "kind": "hsqldb"},
    "Hufflepuff": {"csv": "hufflepuff.csv", "kind": "h2"},
    "Ravenclaw": {"csv": "ravenclaw.csv", "kind": "oracle"},
}

COLUMNS = ("id", "nombre", "apellido", "casa", "alias", "especie", "genero",
           "nacimiento", "nacionalidad", "patronus", "patronus_origen", "imagen", "wiki")
SELECT = "SELECT " + ",".join(COLUMNS) + " FROM students"

JDBC_JARS = [str(path) for path in sorted(Path(JDBC).glob("*.jar"))]
if not jpype.isJVMStarted():
    jpype.startJVM(classpath=JDBC_JARS)


def format_birth(value: str | None) -> tuple[str | None, str | None]:
    """Convierte fechas exactas al formato dd/mm/yyyy; respeta fechas inciertas."""
    if not value:
        return None, None
    match = re.search(r"\b(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\b", value)
    if not match:
        return value, None
    months = {"january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
              "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12}
    month = months.get(match.group(2).lower())
    if not month:
        return value, None
    formatted = f"{int(match.group(1)):02d}/{month:02d}/{match.group(3)}"
    return formatted, formatted


def csv_rows(house: str) -> list[dict[str, str]]:
    """Lee el CSV inicial de cada casa para inicialización y listado."""
    path = CSV_DIR / SOURCES[house]["csv"]
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    for row in rows:
        if "apellidos" in row and "apellido" not in row:
            row["apellido"] = row["apellidos"]
        if "género" in row and "genero" not in row:
            row["genero"] = row["género"]
    return rows


def jdbc_spec(kind: str) -> tuple[str, str, list[str]]:
    """Elige el controlador JDBC de Derby, HSQLDB o H2."""
    if kind == "derby":
        return "org.apache.derby.jdbc.ClientDriver", os.getenv("DERBY_URL", ""), [f"{JDBC}/derby.jar", f"{JDBC}/derbynet.jar", f"{JDBC}/derbyshared.jar", f"{JDBC}/derbyclient.jar", f"{JDBC}/derbytools.jar"]
    if kind == "hsqldb":
        return "org.hsqldb.jdbc.JDBCDriver", os.getenv("HSQLDB_URL", ""), [f"{JDBC}/hsqldb.jar"]
    return "org.h2.Driver", os.getenv("H2_URL", ""), [f"{JDBC}/h2.jar"]


@contextmanager
def source_connection(kind: str) -> Iterator[Any]:
    """Gestiona la conexión a Oracle Thin o al motor JDBC correspondiente."""
    if kind == "oracle":
        dsn = f"{os.getenv('ORACLE_HOST', 'oracle')}:{os.getenv('ORACLE_PORT', '1521')}/{os.getenv('ORACLE_SERVICE', 'FREEPDB1')}"
        connection = oracledb.connect(user=os.getenv("ORACLE_USER", "hogwarts_app"), password=os.getenv("ORACLE_PASSWORD", "hogwarts_app"), dsn=dsn)
        try:
            yield connection
        finally:
            connection.close()
        return
    driver, url, jars = jdbc_spec(kind)
    credentials = ["APP", "APP"] if kind == "derby" else (["SA", ""] if kind == "hsqldb" else ["SA", ""])
    connection = jaydebeapi.connect(driver, url, credentials)
    try:
        yield connection
    finally:
        connection.close()


def create_history_tables() -> None:
    """Crea y carga tablas históricas vacías durante el arranque inicial."""
    statements = {
        "derby": 'CREATE TABLE students (id VARCHAR(64) PRIMARY KEY, nombre VARCHAR(2000), apellido VARCHAR(2000) NOT NULL, casa VARCHAR(40), alias VARCHAR(2000), especie VARCHAR(100), genero VARCHAR(30), nacimiento VARCHAR(1000), nacionalidad VARCHAR(2000), patronus VARCHAR(2000), patronus_origen VARCHAR(2000), imagen VARCHAR(1000), wiki VARCHAR(1000))',
        "hsqldb": 'CREATE TABLE students (id VARCHAR(64) PRIMARY KEY, nombre VARCHAR(2000), apellido VARCHAR(2000) NOT NULL, casa VARCHAR(40), alias VARCHAR(2000), especie VARCHAR(100), genero VARCHAR(30), nacimiento VARCHAR(1000), nacionalidad VARCHAR(2000), patronus VARCHAR(2000), patronus_origen VARCHAR(2000), imagen VARCHAR(1000), wiki VARCHAR(1000))',
        "h2": 'CREATE TABLE students (id VARCHAR(64) PRIMARY KEY, nombre VARCHAR(2000), apellido VARCHAR(2000) NOT NULL, casa VARCHAR(40), alias VARCHAR(2000), especie VARCHAR(100), genero VARCHAR(30), nacimiento VARCHAR(1000), nacionalidad VARCHAR(2000), patronus VARCHAR(2000), patronus_origen VARCHAR(2000), imagen VARCHAR(1000), wiki VARCHAR(1000))',
        "oracle": 'CREATE TABLE students (id VARCHAR2(64) PRIMARY KEY, nombre VARCHAR2(2000), apellido VARCHAR2(2000) NOT NULL, casa VARCHAR2(40), alias VARCHAR2(2000), especie VARCHAR2(100), genero VARCHAR2(30), nacimiento VARCHAR2(1000), nacionalidad VARCHAR2(2000), patronus VARCHAR2(2000), patronus_origen VARCHAR2(2000), imagen VARCHAR2(1000), wiki VARCHAR2(1000))',
    }
    insert = "INSERT INTO students (id,nombre,apellido,casa,alias,especie,genero,nacimiento,nacionalidad,patronus,patronus_origen,imagen,wiki) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)"
    oracle_insert = "INSERT INTO students (id,nombre,apellido,casa,alias,especie,genero,nacimiento,nacionalidad,patronus,patronus_origen,imagen,wiki) VALUES (:1,:2,:3,:4,:5,:6,:7,:8,:9,:10,:11,:12,:13)"
    for house, config in SOURCES.items():
        kind = config["kind"]
        try:
            with source_connection(kind) as connection:
                cursor = connection.cursor()
                try:
                    cursor.execute(statements[kind])
                    connection.commit()
                except Exception as error:
                    if "already exists" not in str(error).lower() and "name is already used" not in str(error).lower():
                        raise
                cursor.execute("SELECT COUNT(*) FROM students")
                count = int(cursor.fetchone()[0])
                if count == 0:
                    for row in csv_rows(house):
                        values = [row.get(key) or None for key in COLUMNS]
                        cursor.execute(oracle_insert if kind == "oracle" else insert, values)
                    connection.commit()
                cursor.close()
        except Exception as error:
            print(f"history initialization pending for {house}: {error}", flush=True)


def row_to_student(row: Any, house: str) -> StudentOut:
    """Normaliza una fila histórica y anota la base de datos de origen."""
    values = {key: (None if value is None else str(value)) for key, value in zip(COLUMNS, row)}
    nacimiento, fecha = format_birth(values.get("nacimiento"))
    values["nacimiento"] = nacimiento
    values["fecha_nacimiento"] = fecha
    values["origen"] = f"{SOURCES[house]['kind']}:{house}"
    return StudentOut(**values)


def query_history(student_id: str) -> StudentOut | None:
    """Busca por ID en los cuatro motores históricos sin modificarlos."""
    for house, config in SOURCES.items():
        try:
            with source_connection(config["kind"]) as connection:
                cursor = connection.cursor()
                placeholder = ":1" if config["kind"] == "oracle" else "?"
                cursor.execute(f"{SELECT} WHERE id = {placeholder}", [student_id])
                row = cursor.fetchone()
                cursor.close()
                if row:
                    return row_to_student(row, house)
        except Exception as error:
            print(f"history query pending for {house}: {error}", flush=True)
    return None


def find_history(name: str | None, house: str | None, limit: int) -> list[StudentOut]:
    """Busca por nombre y casa en las tablas históricas vivas."""
    houses = [current_house for current_house in SOURCES if not house or current_house.casefold() == house.casefold()]
    result: list[StudentOut] = []
    for current_house in houses:
        kind = SOURCES[current_house]["kind"]
        try:
            with source_connection(kind) as connection:
                cursor = connection.cursor()
                try:
                    query = SELECT
                    params = []
                    if name:
                        placeholder = ":1" if kind == "oracle" else "?"
                        query += f" WHERE LOWER(nombre || ' ' || apellido) LIKE {placeholder} ESCAPE '!'"
                        escaped = name.lower().replace("!", "!!").replace("%", "!%").replace("_", "!_")
                        params.append(f"%{escaped}%")
                    query += " ORDER BY id"
                    cursor.execute(query, params)
                    result.extend(row_to_student(row, current_house) for row in cursor.fetchmany(limit - len(result)))
                finally:
                    cursor.close()
        except Exception as error:
            print(f"history search failed for {current_house}: {error}", flush=True)
            raise HTTPException(503, f"Fuente histórica no disponible: {current_house}") from error
        if len(result) >= limit:
            break
    return result


def query_history_by_base(base: str) -> list[StudentOut]:
    """Devuelve el ID histórico y sus variantes con sufijo -NN."""
    result: list[StudentOut] = []
    escaped = base.replace("!", "!!").replace("%", "!%").replace("_", "!_")
    for house, config in SOURCES.items():
        try:
            with source_connection(config["kind"]) as connection:
                cursor = connection.cursor()
                try:
                    placeholders = (":1", ":2") if config["kind"] == "oracle" else ("?", "?")
                    cursor.execute(
                        f"{SELECT} WHERE id = {placeholders[0]} OR id LIKE {placeholders[1]} ESCAPE '!' ORDER BY id",
                        [base, escaped + "-%"],
                    )
                    result.extend(
                        row_to_student(row, house)
                        for row in cursor.fetchall()
                        if matches_student_base(str(row[0]), base)
                    )
                finally:
                    cursor.close()
        except Exception as error:
            raise HTTPException(503, f"Fuente histórica no disponible: {house}") from error
    return result
