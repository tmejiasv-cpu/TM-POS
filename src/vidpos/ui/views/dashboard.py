"""Vista del dashboard: métricas del día y estado del sistema."""
from __future__ import annotations

import tkinter as tk
from datetime import datetime

from vidpos.core.database import Database
from vidpos.services.cash import CashService
from vidpos.services.expenses import ExpensesService
from vidpos.ui import theme


class DashboardView(tk.Frame):
    """Pantalla de inicio con métricas y estado de caja."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        db: Database,
        user: dict,
    ) -> None:
        super().__init__(parent, bg=theme.COLORS["light"])
        self.db = db
        self.user = user

        self.cash = CashService(db)
        self.expenses = ExpensesService(db)

        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        # Encabezado
        header = tk.Frame(self, bg=theme.COLORS["light"])
        header.pack(fill="x", pady=(8, 14))

        tk.Label(
            header, text=f"Bienvenido, {self.user['full_name']}",
            bg=theme.COLORS["light"], fg=theme.COLORS["dark"],
            font=theme.FONTS["h1"],
        ).pack(anchor="w")

        # Fecha en español (sin depender del locale del sistema)
        MESES_ES = [
            "enero", "febrero", "marzo", "abril", "mayo", "junio",
            "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
        ]
        DIAS_ES = [
            "lunes", "martes", "miércoles", "jueves",
            "viernes", "sábado", "domingo",
        ]
        hoy = datetime.now()
        fecha = (
            f"{DIAS_ES[hoy.weekday()]}, {hoy.day} de "
            f"{MESES_ES[hoy.month - 1]} de {hoy.year}"
        ).capitalize()

        tk.Label(
            header, text=fecha,
            bg=theme.COLORS["light"], fg=theme.COLORS["gray"],
            font=theme.FONTS["small"],
        ).pack(anchor="w", pady=(2, 0))

        # Fila de tarjetas de métricas
        cards_row = tk.Frame(self, bg=theme.COLORS["light"])
        cards_row.pack(fill="x", pady=(0, 16))
        for i in range(4):
            cards_row.grid_columnconfigure(i, weight=1)

        self.card_sales = self._make_card(cards_row, 0, "Ventas netas hoy")
        self.card_returns = self._make_card(cards_row, 1, "Devoluciones hoy")
        self.card_pending = self._make_card(cards_row, 2, "Gastos pendientes")
        self.card_low_stock = self._make_card(cards_row, 3, "Productos con stock bajo")

        # Estado de caja (tarjeta ancha)
        cash_card = tk.Frame(
            self, bg=theme.COLORS["white"],
            highlightthickness=1, highlightbackground=theme.COLORS["border"],
        )
        cash_card.pack(fill="x", pady=(0, 16))

        tk.Label(
            cash_card, text="ESTADO DE CAJA",
            bg=theme.COLORS["white"], fg=theme.COLORS["gray"],
            font=theme.FONTS["small_bold"],
        ).pack(anchor="w", padx=20, pady=(16, 4))

        self.cash_status_label = tk.Label(
            cash_card, text="", bg=theme.COLORS["white"],
            fg=theme.COLORS["text"], font=theme.FONTS["h4"],
        )
        self.cash_status_label.pack(anchor="w", padx=20)

        self.cash_detail_label = tk.Label(
            cash_card, text="", bg=theme.COLORS["white"],
            fg=theme.COLORS["gray"], font=theme.FONTS["small"],
            justify="left",
        )
        self.cash_detail_label.pack(anchor="w", padx=20, pady=(2, 16))

        # Nota inferior
        tk.Label(
            self,
            text="Los datos se recalculan cada vez que entras a esta pantalla.",
            bg=theme.COLORS["light"], fg=theme.COLORS["gray"],
            font=theme.FONTS["tiny"],
        ).pack(anchor="w", pady=(8, 0))

    def _make_card(self, parent, col: int, title: str) -> tk.Label:
        card = tk.Frame(
            parent, bg=theme.COLORS["white"],
            highlightthickness=1, highlightbackground=theme.COLORS["border"],
        )
        card.grid(row=0, column=col, sticky="nsew",
                  padx=(0 if col == 0 else 6, 6))

        tk.Label(
            card, text=title, bg=theme.COLORS["white"],
            fg=theme.COLORS["gray"], font=theme.FONTS["small_bold"],
            anchor="w",
        ).pack(anchor="w", padx=16, pady=(14, 2))

        value_label = tk.Label(
            card, text="—", bg=theme.COLORS["white"],
            fg=theme.COLORS["dark"], font=theme.FONTS["price_med"],
            anchor="w",
        )
        value_label.pack(anchor="w", padx=16, pady=(0, 14))
        return value_label

    # ------------------------------------------------------------- datos
    def refresh(self) -> None:
        today = datetime.now().strftime("%Y-%m-%d")

        # Ventas brutas hoy
        gross = float(self.db.scalar(
            """SELECT COALESCE(SUM(total), 0) FROM sales
               WHERE date(created_at) = ? AND status = 'COMPLETED'""",
            (today,), default=0.0,
        ) or 0.0)

        # Devoluciones hoy
        returns = float(self.db.scalar(
            """SELECT COALESCE(SUM(total_refund), 0) FROM sale_returns
               WHERE date(created_at) = ?""",
            (today,), default=0.0,
        ) or 0.0)

        self.card_sales.configure(text=f"${gross - returns:,.2f}")
        self.card_returns.configure(text=f"${returns:,.2f}")

        # Gastos pendientes
        pending = self.expenses.count_pending()
        self.card_pending.configure(text=str(pending))

        # Productos con stock bajo (una sola consulta)
        low = int(self.db.scalar(
            """SELECT COUNT(*) FROM (
                   SELECT p.id, p.min_stock,
                          COALESCE(SUM(l.qty_remaining), 0) AS stock
                   FROM products p
                   LEFT JOIN inventory_lots l ON l.product_id = p.id
                   WHERE p.active = 1 AND p.product_type = 'PRODUCT'
                   GROUP BY p.id
                   HAVING stock <= p.min_stock
               )""",
            default=0,
        ) or 0)
        self.card_low_stock.configure(text=str(low))

        # Estado de caja
        session = self.cash.get_open_session(int(self.user["id"]))
        if session:
            summary = self.cash.get_summary(session.id)
            self.cash_status_label.configure(
                text=f"● CAJA ABIERTA · {session.user_name}",
                fg=theme.COLORS["success"],
            )
            self.cash_detail_label.configure(
                text=(
                    f"Apertura: {session.opened_at}   ·   "
                    f"Fondo inicial: ${summary.opening_amount:,.2f}   ·   "
                    f"Ventas efectivo: ${summary.sales_cash:,.2f}   ·   "
                    f"Ventas transferencia: ${summary.sales_transfer:,.2f}   ·   "
                    f"Efectivo esperado: ${summary.expected_cash:,.2f}"
                )
            )
        else:
            self.cash_status_label.configure(
                text="● CAJA CERRADA",
                fg=theme.COLORS["danger"],
            )
            self.cash_detail_label.configure(
                text="Debe abrir caja antes de registrar ventas."
            )