"""Capa de acceso a la base de datos SQLite."""
from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

from vidpos.config import BACKUPS_DIR, DATA_DIR
from vidpos.core.migrations import apply_migrations

log = logging.getLogger(__name__)

DEFAULT_DB_PATH = DATA_DIR / "vidpos.db"


class Database:
    """Envoltura de sqlite3 con PRAGMAs, transacciones y helpers.

    Uso:
        db = Database()
        row = db.one("SELECT * FROM users WHERE id=?", (1,))
        rows = db.all("SELECT * FROM products")
        db.execute("UPDATE products SET active=0 WHERE id=?", (5,))
        with db.transaction():
            ...
        db.close()
    """

    def __init__(self, path: Path | str = DEFAULT_DB_PATH) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(
            self.path,
            isolation_level=None,      # control manual de transacciones
            detect_types=sqlite3.PARSE_DECLTYPES,
            timeout=10.0,
        )
        self.conn.row_factory = sqlite3.Row

        self._configure_pragmas()
        self._run_migrations()

    # ------------------------------------------------------------------ setup
    def _configure_pragmas(self) -> None:
        cur = self.conn.cursor()
        cur.execute("PRAGMA foreign_keys = ON")
        cur.execute("PRAGMA journal_mode = WAL")
        cur.execute("PRAGMA synchronous = FULL")
        cur.execute("PRAGMA busy_timeout = 5000")
        cur.execute("PRAGMA temp_store = MEMORY")
        cur.execute("PRAGMA cache_size = -8000")  # ~8 MB
        cur.close()
        log.debug("PRAGMAs configurados para %s", self.path)

    def _run_migrations(self) -> None:
        apply_migrations(self.conn)

    # -------------------------------------------------------------- helpers
    def one(
        self, sql: str, params: Sequence[Any] = ()
    ) -> sqlite3.Row | None:
        return self.conn.execute(sql, params).fetchone()

    def all(
        self, sql: str, params: Sequence[Any] = ()
    ) -> list[sqlite3.Row]:
        return self.conn.execute(sql, params).fetchall()

    def execute(
        self, sql: str, params: Sequence[Any] = ()
    ) -> sqlite3.Cursor:
        """Ejecuta una sentencia en autocommit (commit inmediato)."""
        cur = self.conn.execute(sql, params)
        self.conn.commit()
        return cur

    def executemany(
        self, sql: str, seq_params: Iterable[Sequence[Any]]
    ) -> sqlite3.Cursor:
        cur = self.conn.executemany(sql, seq_params)
        self.conn.commit()
        return cur

    def scalar(
        self, sql: str, params: Sequence[Any] = (), default: Any = None
    ) -> Any:
        row = self.one(sql, params)
        if row is None:
            return default
        value = row[0]
        return default if value is None else value

    # ------------------------------------------------------------ transacción
    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Transacción explícita con rollback automático ante error.

        with db.transaction():
            db.conn.execute(...)
            db.conn.execute(...)
            # commit automático al salir sin error
        """
        try:
            self.conn.execute("BEGIN")
            yield self.conn
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            log.exception("Transacción revertida")
            raise

    # ---------------------------------------------------------------- cierre
    def close(self) -> None:
        try:
            self.conn.commit()
        except Exception:
            log.exception("Error en commit final")
        finally:
            try:
                self.conn.close()
                log.info("Conexión cerrada: %s", self.path)
            except Exception:
                log.exception("Error cerrando la conexión")

    # --------------------------------------------------------------- respaldo
    def backup(self, dest_dir: Path | None = None, tag: str = "") -> Path:
        """Respaldo consistente usando la API de backup de SQLite.

        No requiere cerrar la aplicación.
        """
        dest_dir = dest_dir or BACKUPS_DIR
        dest_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = f"_{tag}" if tag else ""
        dest = dest_dir / f"vidpos_{stamp}{suffix}.db"

        target = sqlite3.connect(dest)
        try:
            with target:
                self.conn.backup(target)
        finally:
            target.close()

        log.info("Respaldo creado: %s", dest)
        return dest

    def rotate_backups(self, keep: int = 30, dest_dir: Path | None = None) -> int:
        """Elimina los respaldos más antiguos dejando solo `keep`."""
        dest_dir = dest_dir or BACKUPS_DIR
        files = sorted(
            dest_dir.glob("vidpos_*.db"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        removed = 0
        for old in files[keep:]:
            try:
                old.unlink()
                removed += 1
            except OSError:
                log.warning("No se pudo borrar respaldo %s", old)
        if removed:
            log.info("Respaldos rotados: %s eliminados", removed)
        return removed