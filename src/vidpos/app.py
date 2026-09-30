"""Aplicación principal de vidPOS: orquesta login y ventana principal."""
from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk

from vidpos.config import APP_NAME, APP_SLOGAN, APP_VERSION, AppConfig
from vidpos.core.auth import AuthResult, AuthService
from vidpos.core.database import Database
from vidpos.core.logging_setup import setup_logging
from vidpos.ui import branding, theme
from vidpos.ui.main_window import MainWindow
from vidpos.ui.views.login import LoginView

log = logging.getLogger(__name__)


class VidPOSApp(tk.Tk):
    """Aplicación Tk raíz. Orquesta login y ventana principal."""

    def __init__(self) -> None:
        super().__init__()

        self.title(f"{APP_NAME} — {APP_SLOGAN}")
        self.geometry("1280x760")
        self.minsize(1024, 640)
        self.configure(bg=theme.COLORS["light"])

        # Servicios
        self.config_data = AppConfig.load()
        self.db = Database()
        self.auth = AuthService(self.db, self.config_data)

        # Asegurar admin inicial
        self.auth.ensure_admin_seed()

        # Estado de sesión
        self.user: dict | None = None
        self.session_id: int | None = None

        # Contenedor raíz
        self.container = tk.Frame(self, bg=theme.COLORS["light"])
        self.container.pack(fill="both", expand=True)

        # Estilos ttk
        theme.configure_ttk_styles(self)

        # Ícono de la ventana
        branding.set_window_icon(self)

        # Protocolo de cierre
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Intentar maximizar
        try:
            self.state("zoomed")
        except tk.TclError:
            pass

        # Empezar por el login
        self.show_login()

    # -------------------------------------------------------- navegación
    def _clear_container(self) -> None:
        for w in self.container.winfo_children():
            w.destroy()

    def show_login(self) -> None:
        """Muestra la pantalla de login."""
        self._clear_container()
        self.user = None
        self.session_id = None

        view = LoginView(
            self.container,
            auth=self.auth,
            config=self.config_data,
            on_success=self._on_login_success,
        )
        view.pack(fill="both", expand=True)

    def _on_login_success(self, result: AuthResult) -> None:
        """Callback cuando un usuario se autentica."""
        if not result.user_id:
            return

        # Cargar datos completos del usuario desde la BD
        row = self.db.one("SELECT * FROM users WHERE id = ?", (result.user_id,))
        if not row:
            log.error("Usuario autenticado no encontrado en BD: %s", result.user_id)
            return

        self.user = dict(row)

        # Registrar sesión
        try:
            self.session_id = self.auth.register_login(int(self.user["id"]))
        except Exception:
            log.exception("Error registrando login")

        log.info(
            "Usuario %s (%s) inició sesión",
            self.user["username"], self.user["role"],
        )

        self.show_main()

    def show_main(self) -> None:
        """Muestra la ventana principal con sidebar."""
        if not self.user:
            self.show_login()
            return

        self._clear_container()

        main = MainWindow(
            self.container,
            db=self.db,
            user=self.user,
            on_logout=self._do_logout,
        )
        main.pack(fill="both", expand=True)

    # ------------------------------------------------------------ cierre
    def _do_logout(self) -> None:
        """Cierra sesión y vuelve al login."""
        if self.session_id:
            try:
                self.auth.register_logout(self.session_id, "CERRAR SESION")
            except Exception:
                log.exception("Error registrando logout")
        self.session_id = None
        self.show_login()

    def _on_close(self) -> None:
        """Cierre limpio de la aplicación."""
        try:
            if self.session_id:
                try:
                    self.auth.register_logout(self.session_id, "CIERRE APLICACION")
                except Exception:
                    log.exception("Error registrando cierre")
            self.db.close()
        finally:
            self.destroy()


def main() -> int:
    """Punto de entrada."""
    setup_logging()
    log.info("=" * 60)
    log.info("Iniciando %s v%s", APP_NAME, APP_VERSION)
    log.info("=" * 60)

    try:
        app = VidPOSApp()
        app.mainloop()
        log.info("%s finalizado correctamente.", APP_NAME)
        return 0
    except Exception:
        log.exception("Error fatal en la aplicación")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())