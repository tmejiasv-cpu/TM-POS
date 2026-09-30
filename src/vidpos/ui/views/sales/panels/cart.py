"""Panel del carrito + acciones."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from vidpos.ui import theme
from vidpos.ui.widgets import modal


class CartPanelMixin:
    """Mixin: panel izquierdo con la tabla del carrito."""

    def _build_cart_panel(self, parent: tk.Frame) -> None:
        left = tk.Frame(
            parent, bg=theme.COLORS["white"],
            highlightthickness=1, highlightbackground=theme.COLORS["border"],
        )
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))

        cart_header = tk.Frame(left, bg=theme.COLORS["white"])
        cart_header.pack(fill="x", padx=12, pady=(10, 6))

        tk.Label(cart_header, text="Detalle de venta", bg=theme.COLORS["white"],
                 fg=theme.COLORS["dark"], font=theme.FONTS["h4"]).pack(side="left")

        self.items_count_label = tk.Label(cart_header, text="0 unidades",
                                          bg=theme.COLORS["white"],
                                          fg=theme.COLORS["gray"],
                                          font=theme.FONTS["small"])
        self.items_count_label.pack(side="right")

        actions = tk.Frame(left, bg=theme.COLORS["white"])
        actions.pack(fill="x", padx=10, pady=(0, 8))

        theme.make_button(actions, "+1", self._increase_selected,
                          kind="accent", width=4, pady=5, font_key="small_bold"
                          ).pack(side="left", padx=(0, 5))
        theme.make_button(actions, "-1", self._decrease_selected,
                          kind="neutral", width=4, pady=5, font_key="small_bold"
                          ).pack(side="left", padx=5)
        theme.make_button(actions, "ELIMINAR ITEM", self._remove_selected,
                          kind="danger", padx=14, pady=6, font_key="small_bold"
                          ).pack(side="left", padx=5)
        theme.make_button(actions, "Vaciar venta", self._clear_cart,
                          kind="neutral", padx=12, pady=5, font_key="small"
                          ).pack(side="right")

        table_frame = tk.Frame(left, bg=theme.COLORS["white"])
        table_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        cols = ("sku", "name", "presentation", "qty", "price", "sub")
        self.cart_tree = ttk.Treeview(table_frame, columns=cols, show="headings",
                                      selectmode="browse")
        for c, h, w, anchor in [
            ("sku", "Código", 105, "w"),
            ("name", "Producto", 220, "w"),
            ("presentation", "Presentación", 140, "w"),
            ("qty", "Cant.", 70, "e"),
            ("price", "Precio", 85, "e"),
            ("sub", "Subtotal", 95, "e"),
        ]:
            self.cart_tree.heading(c, text=h)
            self.cart_tree.column(c, width=w, anchor=anchor)

        vscroll = ttk.Scrollbar(table_frame, orient="vertical",
                                command=self.cart_tree.yview)
        self.cart_tree.configure(yscrollcommand=vscroll.set)
        self.cart_tree.pack(side="left", fill="both", expand=True)
        vscroll.pack(side="right", fill="y")

        self.cart_tree.bind("<Delete>", lambda e: self._remove_selected())

    # =========================================================================
    # Manipulación del carrito
    # =========================================================================
    def _selected_cart_index(self) -> int | None:
        sel = self.cart_tree.selection()
        if not sel:
            return None
        return self.cart_tree.index(sel[0])

    def _increase_selected(self) -> None:
        idx = self._selected_cart_index()
        if idx is None:
            return
        item = self.cart[idx]
        if item.product_type != "SERVICE":
            stock = self.inventory.current_stock(item.product_id)
            if item.inventory_qty + item.presentation_factor > stock + 1e-9:
                modal.warning(self, "Stock insuficiente", f"Disponible: {stock:.2f}")
                return
        item.sale_qty += 1
        if item.product_type != "SERVICE":
            item.inventory_qty += item.presentation_factor
        self._refresh_cart()
        self._save_draft()

    def _decrease_selected(self) -> None:
        idx = self._selected_cart_index()
        if idx is None:
            return
        item = self.cart[idx]
        item.sale_qty -= 1
        if item.product_type != "SERVICE":
            item.inventory_qty -= item.presentation_factor
        if item.sale_qty <= 0:
            self.cart.pop(idx)
        self._refresh_cart()
        self._save_draft()

    def _remove_selected(self) -> None:
        idx = self._selected_cart_index()
        if idx is None:
            return
        self.cart.pop(idx)
        self._refresh_cart()
        self._save_draft()

    def _clear_cart(self) -> None:
        if not self.cart:
            return
        if modal.confirm(self, "Vaciar venta",
                         "¿Desea eliminar todos los artículos de la venta actual?",
                         primary_text="SÍ, VACIAR", secondary_text="VOLVER"):
            self.cart = []
            self._refresh_cart()
            self._save_draft()

    def _refresh_cart(self) -> None:
        for row in self.cart_tree.get_children():
            self.cart_tree.delete(row)

        total_units = 0.0
        for item in self.cart:
            unit_price = item.display_unit_price
            subtotal = item.subtotal
            total_units += item.inventory_qty

            pres_text = item.presentation_name
            if item.addons:
                addons_text = ", ".join(a.name for a in item.addons)
                pres_text = f"{pres_text} + {addons_text}"

            self.cart_tree.insert("", "end", values=(
                item.sku, item.name, pres_text,
                f"{item.sale_qty:.2f}", f"${unit_price:.2f}", f"${subtotal:.2f}",
            ))

        self.items_count_label.configure(
            text=f"{total_units:.2f} unidades · {len(self.cart)} ítems"
        )

        total = self._current_total()
        self.total_var.set(f"${total:,.2f}")
        self.subtotal_var.set(f"${total:,.2f}")
        self._calculate_change()