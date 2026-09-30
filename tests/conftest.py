"""Configuración compartida de pytest."""
from __future__ import annotations

import sqlite3
import pytest

from vidpos.core.database import Database


@pytest.fixture
def db():
    """Base de datos en memoria, aislada por test."""
    # Usamos un archivo temporal para que WAL funcione correctamente.
    # SQLite en :memory: no soporta WAL de la misma forma.
    import tempfile
    from pathlib import Path

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    path = Path(tmp.name)

    database = Database(path)
    # Admin de prueba para satisfacer claves foráneas
    database.execute(
        """INSERT INTO users(full_name, username, password_hash, role, created_at)
           VALUES(?,?,?,?,?)""",
        ("Test Admin", "test", "x$x$x", "admin", "2026-01-01 00:00:00"),
    )
    yield database
    database.close()
    try:
        path.unlink()
        path.with_suffix(".db-wal").unlink(missing_ok=True)
        path.with_suffix(".db-shm").unlink(missing_ok=True)
    except OSError:
        pass


@pytest.fixture
def admin_id(db):
    return int(db.scalar("SELECT id FROM users WHERE username='test'"))