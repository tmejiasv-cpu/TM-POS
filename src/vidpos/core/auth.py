"""Autenticación: hash de contraseñas, login y sesiones."""
from __future__ import annotations

import hmac
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime

from vidpos.config import AppConfig
from vidpos.core.database import Database

log = logging.getLogger(__name__)


# --------------------------------------------------------------------- hashing
def hash_password(password: str, iterations: int = 120_000) -> str:
    """Devuelve 'iteraciones$salt$digest' con PBKDF2-SHA256."""
    if not password:
        raise ValueError("La contraseña no puede estar vacía")
    salt = secrets.token_hex(16)
    digest = _pbkdf2(password, salt, iterations)
    return f"{iterations}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    """Verifica una contraseña contra el hash almacenado.

    Formatos soportados:
      - 'iteraciones$salt$digest'  (formato nuevo)
      - 'salt$digest'              (formato antiguo, asume 120k iteraciones)
    """
    if not stored or not isinstance(stored, str):
        return False
    try:
        parts = stored.split("$")
        if len(parts) == 3:
            iterations, salt, digest_hex = parts
            iterations = int(iterations)
        elif len(parts) == 2:
            salt, digest_hex = parts
            iterations = 120_000
        else:
            return False
        computed = _pbkdf2(password, salt, iterations)
        return hmac.compare_digest(computed, digest_hex)
    except (ValueError, AttributeError):
        log.warning("Hash de contraseña con formato inválido")
        return False


def _pbkdf2(password: str, salt: str, iterations: int) -> str:
    import hashlib
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations
    ).hex()


# ----------------------------------------------------------------------- utils
def now_iso() -> str:
    """Marca de tiempo uniforme en toda la aplicación."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# -------------------------------------------------------------------- servicio
@dataclass
class AuthResult:
    ok: bool
    user_id: int | None = None
    role: str | None = None
    full_name: str | None = None
    must_change_password: bool = False
    message: str = ""


class AuthService:
    """Servicio de autenticación y sesiones."""

    def __init__(self, db: Database, config: AppConfig | None = None) -> None:
        self.db = db
        self.config = config or AppConfig.load()

    # ------------------------------------------------------------------ login
    def login(self, username: str, password: str) -> AuthResult:
        username = (username or "").strip()
        if not username or not password:
            return AuthResult(ok=False, message="Usuario y contraseña son obligatorios.")

        row = self.db.one(
            "SELECT * FROM users WHERE username=? AND active=1",
            (username,),
        )
        if not row or not verify_password(password, row["password_hash"]):
            log.info("Login fallido para usuario=%s", username)
            return AuthResult(ok=False, message="Usuario o contraseña incorrectos.")

        log.info("Login OK: %s (id=%s)", row["username"], row["id"])
        return AuthResult(
            ok=True,
            user_id=row["id"],
            role=row["role"],
            full_name=row["full_name"],
            must_change_password=bool(row["must_change_password"]),
        )

    # ---------------------------------------------------------------- sesiones
    def register_login(self, user_id: int, host: str = "") -> int:
        cur = self.db.execute(
            "INSERT INTO user_sessions(user_id, login_at, ip_or_host) VALUES(?,?,?)",
            (user_id, now_iso(), host),
        )
        return int(cur.lastrowid)

    def register_logout(self, session_id: int, logout_type: str = "CERRAR SESION") -> None:
        if not session_id:
            return
        try:
            self.db.execute(
                """UPDATE user_sessions
                   SET logout_at=?, logout_type=?
                   WHERE id=? AND logout_at IS NULL""",
                (now_iso(), logout_type, session_id),
            )
        except Exception:
            log.exception("No se pudo registrar el logout de la sesión %s", session_id)

    # -------------------------------------------------------------- contraseña
    def change_password(
        self,
        user_id: int,
        current_password: str,
        new_password: str,
        confirm_password: str | None = None,
    ) -> tuple[bool, str]:
        """Cambia la contraseña de un usuario. Devuelve (ok, mensaje)."""
        if confirm_password is not None and new_password != confirm_password:
            return False, "Las contraseñas nuevas no coinciden."

        if len(new_password) < 6:
            return False, "La contraseña debe tener al menos 6 caracteres."

        row = self.db.one("SELECT password_hash FROM users WHERE id=?", (user_id,))
        if not row:
            return False, "Usuario no encontrado."

        if not verify_password(current_password, row["password_hash"]):
            return False, "La contraseña actual es incorrecta."

        new_hash = hash_password(new_password, self.config.pbkdf2_iterations)
        self.db.execute(
            "UPDATE users SET password_hash=?, must_change_password=0, updated_at=? WHERE id=?",
            (new_hash, now_iso(), user_id),
        )
        log.info("Contraseña cambiada para user_id=%s", user_id)
        return True, "Contraseña actualizada correctamente."

    def admin_reset_password(
        self, user_id: int, new_password: str, must_change: bool = True
    ) -> tuple[bool, str]:
        """Reset realizado por un administrador."""
        if len(new_password) < 6:
            return False, "La contraseña debe tener al menos 6 caracteres."
        new_hash = hash_password(new_password, self.config.pbkdf2_iterations)
        self.db.execute(
            """UPDATE users
               SET password_hash=?, must_change_password=?, updated_at=?
               WHERE id=?""",
            (new_hash, 1 if must_change else 0, now_iso(), user_id),
        )
        return True, "Contraseña restablecida. El usuario deberá cambiarla al iniciar sesión."

    # ------------------------------------------------------------------ seed
    def ensure_admin_seed(self, default_username: str = "admin",
                          default_password: str = "admin123") -> None:
        """Crea el admin inicial si la tabla de usuarios está vacía."""
        count = int(self.db.scalar("SELECT COUNT(*) FROM users", default=0) or 0)
        if count > 0:
            return
        self.db.execute(
            """INSERT INTO users(
                   full_name, username, password_hash, role,
                   schedule_type, active, must_change_password, created_at
               ) VALUES(?,?,?,?,?,?,?,?)""",
            (
                "Gerente General",
                default_username,
                hash_password(default_password, self.config.pbkdf2_iterations),
                "admin",
                "Gerencia",
                1,
                1,  # debe cambiar la contraseña inicial
                now_iso(),
            ),
        )
        log.warning(
            "Usuario admin inicial creado (%s). Cambie la contraseña al primer ingreso.",
            default_username,
        )