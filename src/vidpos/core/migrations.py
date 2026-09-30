"""Sistema de migraciones de vidPOS.

Cada migración es una tupla (versión, nombre, función).
Las funciones reciben una conexión sqlite3 y aplican cambios.

Para añadir una migración nueva:
  1. Incrementa SCHEMA_VERSION en schema.py
  2. Añade (N, "descripcion", _migration_N) al final de MIGRATIONS
  3. Escribe la función _migration_N
"""
from __future__ import annotations

import logging
import sqlite3
from typing import Callable

from vidpos.core.schema import INITIAL_SCHEMA, SCHEMA_VERSION

log = logging.getLogger(__name__)

Migration = tuple[int, str, Callable[[sqlite3.Connection], None]]


def _migration_001_initial(conn: sqlite3.Connection) -> None:
    """Esquema inicial completo."""
    conn.executescript(INITIAL_SCHEMA)


# Registro ordenado de migraciones.
# A partir de aquí, cada cambio va como migración nueva.
MIGRATIONS: list[Migration] = [
    (1, "initial_schema", _migration_001_initial),
    # Ejemplo de migración futura:
    # (2, "add_customers_table", _migration_002_customers),
]


def get_user_version(conn: sqlite3.Connection) -> int:
    return int(conn.execute("PRAGMA user_version").fetchone()[0])


def set_user_version(conn: sqlite3.Connection, version: int) -> None:
    # PRAGMA no acepta parámetros, pero version es int controlado por nosotros.
    conn.execute(f"PRAGMA user_version = {int(version)}")


def apply_migrations(conn: sqlite3.Connection) -> int:
    """Aplica todas las migraciones pendientes.

    Devuelve la versión final de la base de datos.
    """
    current = get_user_version(conn)
    log.info("Esquema actual: v%s · objetivo: v%s", current, SCHEMA_VERSION)

    if current > SCHEMA_VERSION:
        raise RuntimeError(
            f"La base de datos es más nueva (v{current}) que esta versión "
            f"de vidPOS (v{SCHEMA_VERSION}). Actualice el programa."
        )

    applied = 0
    for version, name, fn in MIGRATIONS:
        if version <= current:
            continue
        log.info("Aplicando migración %s: %s", version, name)
        try:
            conn.execute("BEGIN")
            fn(conn)
            set_user_version(conn, version)
            conn.commit()
            applied += 1
        except Exception:
            conn.rollback()
            log.exception("Fallo aplicando migración %s (%s)", version, name)
            raise

    if applied:
        log.info("%s migración(es) aplicada(s).", applied)
    else:
        log.info("Sin migraciones pendientes.")
    return get_user_version(conn)