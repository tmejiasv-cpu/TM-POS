"""Vista principal del POS. Une los mixins de paneles y lógica."""
from __future__ import annotations

import tkinter as tk

from vidpos.core.database import Database
from vidpos.services.cash import CashService
from vidpos.services.inventory import InventoryService
from vidpos.services.products import ProductService
from vidpos.services.sales import SalesService
from vidpos.ui import theme
from vidpos.ui.views.sales.logic import SalesLogicMixin
from vidpos.ui.views.sales.panels.capture import CapturePanelMixin
from vidpos.ui.views.sales.panels.cart import CartPanelMixin
from vidpos.ui.views.sales.panels.payment import PaymentPanelMixin


class SalesView(
    CapturePanelMixin,
    CartPanelMixin,
    PaymentPanelMixin,
    SalesLogicMixin,
    tk.Frame,
):
    """Pantalla principal del POS."""

    def __init__(self, parent: tk.Misc, *, db: Database, user: dict) -> None:
        super().__init__(parent, bg=theme.COLORS["light"])
        self.db = db
        self.user = user

        # Servicios
        self.products = ProductService(db)
        self.inventory = InventoryService(db)
        self.sales = SalesService(db, self.products, self.inventory)
        self.cash = CashService(db)

        # Estado del POS
        self.cart: list = []
        self.all_products: list[dict] = []
        self.current_presentations: list[dict] = []
        self.current_addons: list[dict] = []
        self.addon_vars: list[tk.BooleanVar] = []
        self.cash_session = None

        self._build_ui()
        self._reload_products()
        self._refresh_cart()
        self._refresh_cash_status()
        self._calculate_change()
        self._recover_draft()

    # =========================================================================
    # Estructura general
    # =========================================================================
    def _build_ui(self) -> None:
        header = tk.Frame(self, bg=theme.COLORS["light"])
        header.pack(fill="x", pady=(6, 10))

        tk.Label(header, text="Punto de venta", bg=theme.COLORS["light"],
                 fg=theme.COLORS["dark"], font=theme.FONTS["h1"]).pack(side="left")

        self.cash_status_label = tk.Label(
            header, text="", bg=theme.COLORS["danger"], fg="white",
            font=theme.FONTS["small_bold"], padx=14, pady=6,
        )
        self.cash_status_label.pack(side="right")

        self._build_capture_panel()

        work = tk.Frame(self, bg=theme.COLORS["light"])
        work.pack(fill="both", expand=True)

        self._build_cart_panel(work)
        self._build_payment_panel(work)