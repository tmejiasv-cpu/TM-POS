"""Ventana principal de vidPOS con sidebar y área de trabajo."""
from __future__ import annotations

import logging
import tkinter as tk
from typing import Callable

from vidpos.config import APP_VERSION
from vidpos.core.database import Database
from vidpos.ui import branding, theme

log = logging.getLogger(__name__)


class MainWindow(tk.Frame):
    """Ventana principal. Contiene sidebar + área de trabajo intercambiable."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        db: Database,
        user: dict,
        on_logout: Callable[[], None],
    ) -> None:
        super().__init__(parent, bg=theme.COLORS["light"])
        self.db = db
        self.user = user
        self.on_logout = on_logout

        self.current_page_name: str | None = None
        self.pages: dict[str, tk.Frame] = {}
        self.nav_buttons: dict[str, tk.Button] = {}

        self._build_ui()
        self.show_page("Inicio")

    # =========================================================================
    # UI
    # =========================================================================
    def _build_ui(self) -> None:
        shell = tk.Frame(self, bg=theme.COLORS["light"])
        shell.pack(fill="both", expand=True)

        self._build_sidebar(shell)

        work_area = tk.Frame(shell, bg=theme.COLORS["light"])
        work_area.pack(side="left", fill="both", expand=True)

        self._build_header(work_area)

        self.page_container = tk.Frame(work_area, bg=theme.COLORS["light"])
        self.page_container.pack(fill="both", expand=True, padx=20, pady=16)

        self._create_pages()

    def _build_sidebar(self, parent: tk.Frame) -> None:
        sidebar = tk.Frame(parent, bg=theme.COLORS["dark"], width=220)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        self.sidebar = sidebar

        # ---------- Logo blanco ----------
        logo_frame = tk.Frame(sidebar, bg=theme.COLORS["dark"], height=110)
        logo_frame.pack(fill="x")
        logo_frame.pack_propagate(False)

        logo_photo = branding.logo_white(width=170, height=60)
        if logo_photo:
            lbl = tk.Label(logo_frame, image=logo_photo, bg=theme.COLORS["dark"])
            lbl.image = logo_photo
            lbl.pack(pady=(24, 8))
        else:
            tk.Label(
                logo_frame, text="vidPOS", bg=theme.COLORS["dark"], fg="white",
                font=theme.FONTS["h2"],
            ).pack(pady=(30, 8))

        tk.Label(
            logo_frame, text=f"v{APP_VERSION}",
            bg=theme.COLORS["dark"], fg=theme.COLORS["gray"],
            font=theme.FONTS["tiny"],
        ).pack()

        tk.Frame(sidebar, bg=theme.COLORS["dark_2"], height=1).pack(
            fill="x", pady=(8, 6)
        )

        tk.Label(
            sidebar, text="MENÚ", bg=theme.COLORS["dark"],
            fg=theme.COLORS["gray"], font=theme.FONTS["tiny"], anchor="w",
        ).pack(fill="x", padx=20, pady=(4, 6))

        # ---------- Navegación ----------
        nav_frame = tk.Frame(sidebar, bg=theme.COLORS["dark"])
        nav_frame.pack(fill="x")

        menu_items = [
            "Inicio", "Ventas", "Productos", "Compras", "Caja", "Gastos",
        ]
        if self.user["role"] == "admin":
            menu_items.extend([
                "Empleados", "Devoluciones", "Finanzas", "Reportes",
            ])

        for name in menu_items:
            btn = self._make_nav_button(nav_frame, name)
            self.nav_buttons[name] = btn

        tk.Frame(sidebar, bg=theme.COLORS["dark"]).pack(fill="both", expand=True)

        # ---------- Footer ----------
        footer = tk.Frame(sidebar, bg=theme.COLORS["dark_2"])
        footer.pack(fill="x", side="bottom")

        tk.Label(
            footer, text=self.user["full_name"], bg=theme.COLORS["dark_2"],
            fg="white", font=theme.FONTS["small_bold"], anchor="w",
        ).pack(fill="x", padx=16, pady=(10, 0))

        rol = "Gerencia" if self.user["role"] == "admin" else "Empleado"
        tk.Label(
            footer, text=rol, bg=theme.COLORS["dark_2"],
            fg=theme.COLORS["gray"], font=theme.FONTS["tiny"], anchor="w",
        ).pack(fill="x", padx=16)

        theme.make_button(
            footer, "CERRAR SESIÓN", self.on_logout,
            kind="danger", padx=12, pady=7, font_key="tiny",
        ).pack(fill="x", padx=12, pady=(10, 12))

    def _make_nav_button(self, parent: tk.Frame, name: str) -> tk.Button:
        btn = tk.Button(
            parent, text=f"  {name}", anchor="w",
            command=lambda n=name: self.show_page(n),
            bg=theme.COLORS["dark"], fg="white",
            activebackground=theme.COLORS["primary"],
            activeforeground="white",
            relief="flat", bd=0,
            font=theme.FONTS["body"], padx=18, pady=10, cursor="hand2",
        )
        btn.pack(fill="x", padx=8, pady=1)
        return btn

    def _build_header(self, parent: tk.Frame) -> None:
        header = tk.Frame(parent, bg=theme.COLORS["white"], height=70)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Frame(header, bg=theme.COLORS["border"], height=1).pack(
            side="bottom", fill="x"
        )

        self.header_title = tk.Label(
            header, text="", bg=theme.COLORS["white"],
            fg=theme.COLORS["dark"], font=theme.FONTS["h3"],
        )
        self.header_title.pack(side="left", padx=24, pady=20)

    # =========================================================================
    # Crear páginas
    # =========================================================================
    def _create_pages(self) -> None:
        """Crea todas las páginas. Las no implementadas usan placeholder."""
        # --- Inicio (Dashboard) ---
        from vidpos.ui.views.dashboard import DashboardView
        self.pages["Inicio"] = DashboardView(
            self.page_container, db=self.db, user=self.user,
        )

        # --- Ventas (POS) ---
        try:
            from vidpos.ui.views.sales import SalesView
            self.pages["Ventas"] = SalesView(
                self.page_container, db=self.db, user=self.user,
            )
        except Exception:
            log.exception("Error cargando SalesView")
            self.pages["Ventas"] = self._make_placeholder(
                "Punto de venta — error al cargar"
            )

        # --- Productos ---
        try:
            from vidpos.ui.views.products import ProductsView
            self.pages["Productos"] = ProductsView(
                self.page_container, db=self.db, user=self.user,
            )
        except Exception:
            log.exception("Error cargando ProductsView")
            self.pages["Productos"] = self._make_placeholder(
                "Catálogo de productos — error al cargar"
            )

        # --- Placeholders temporales ---
        placeholders = {
            "Compras": "Entradas de inventario — próximamente",
            "Caja": "Gestión de caja — próximamente",
            "Gastos": "Movimientos financieros — próximamente",
        }

        if self.user["role"] == "admin":
            placeholders.update({
                "Empleados": "Gestión de usuarios — próximamente",
                "Devoluciones": "Devoluciones y anulaciones — próximamente",
                "Finanzas": "Estado de resultados — próximamente",
                "Reportes": "Reportes y auditoría — próximamente",
            })

        for name, msg in placeholders.items():
            self.pages[name] = self._make_placeholder(msg)

    def _make_placeholder(self, message: str) -> tk.Frame:
        """Página temporal con un mensaje centrado."""
        frame = tk.Frame(self.page_container, bg=theme.COLORS["light"])
        tk.Label(
            frame, text=message, bg=theme.COLORS["light"],
            fg=theme.COLORS["gray"], font=theme.FONTS["h3"],
        ).pack(expand=True)
        return frame

    # =========================================================================
    # Navegación
    # =========================================================================
    def show_page(self, name: str) -> None:
        """Muestra una página y marca su botón como activo."""
        if name not in self.pages:
            log.warning("Página no encontrada: %s", name)
            return

        page = self.pages[name]

        # Refrescar módulos que dependen de datos recientes
        if name == "Inicio" and hasattr(page, "refresh"):
            try:
                page.refresh()
            except Exception:
                log.exception("Error refrescando dashboard")

        # Ocultar todas las páginas
        for p in self.pages.values():
            p.pack_forget()

        # Mostrar la seleccionada
        page.pack(fill="both", expand=True)
        self.current_page_name = name

        # Actualizar estilos de botones
        for n, btn in self.nav_buttons.items():
            if n == name:
                btn.configure(
                    bg=theme.COLORS["primary"], fg="white",
                    font=(theme.FONT_FAMILY, 10, "bold"),
                )
            else:
                btn.configure(
                    bg=theme.COLORS["dark"], fg="white",
                    font=theme.FONTS["body"],
                )

        self.header_title.configure(text=name)