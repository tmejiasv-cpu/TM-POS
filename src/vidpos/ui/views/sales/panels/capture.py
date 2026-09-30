"""Panel de captura: código de barras, búsqueda y combo editable."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from vidpos.ui import theme
from vidpos.ui.widgets import modal
from vidpos.ui.widgets.searchable_combo import SearchableCombo


class CapturePanelMixin:
    """Mixin: panel superior de captura de productos."""

    def _build_capture_panel(self) -> None:
        capture = tk.Frame(
            self, bg=theme.COLORS["white"],
            highlightthickness=1, highlightbackground=theme.COLORS["border"],
        )
        capture.pack(fill="x", pady=(0, 10))

        # ----- Fila 1: código de barras + cantidad + stock + presentación -----
        row1 = tk.Frame(capture, bg=theme.COLORS["white"])
        row1.pack(fill="x", padx=14, pady=(12, 6))

        tk.Label(row1, text="Código / barras", bg=theme.COLORS["white"],
                 fg=theme.COLORS["text"], font=theme.FONTS["small_bold"]).pack(side="left")

        self.barcode_var = tk.StringVar()
        self.barcode_entry = theme.make_entry(
            row1, textvariable=self.barcode_var, width=24, font_key="h4",
        )
        self.barcode_entry.pack(side="left", padx=(8, 18), ipady=5)

        tk.Label(row1, text="Cant.", bg=theme.COLORS["white"],
                 fg=theme.COLORS["text"], font=theme.FONTS["small_bold"]).pack(side="left")

        self.qty_var = tk.StringVar(value="1")
        self.qty_entry = theme.make_entry(row1, textvariable=self.qty_var, width=6)
        self.qty_entry.pack(side="left", padx=4, ipady=5)

        self.stock_label = tk.Label(row1, text="Stock: —", bg=theme.COLORS["white"],
                                    fg=theme.COLORS["gray"], font=theme.FONTS["small"])
        self.stock_label.pack(side="left", padx=10)

        tk.Label(row1, text="Presentación", bg=theme.COLORS["white"],
                 fg=theme.COLORS["text"], font=theme.FONTS["small_bold"]).pack(side="left", padx=(4, 4))

        self.presentation_combo = ttk.Combobox(row1, state="readonly", width=22,
                                               font=theme.FONTS["small"])
        self.presentation_combo.pack(side="left", padx=4)

        # ----- Fila 2: combo editable de productos + AGREGAR -----
        row2 = tk.Frame(capture, bg=theme.COLORS["white"])
        row2.pack(fill="x", padx=14, pady=(4, 8))

        tk.Label(row2, text="Producto", bg=theme.COLORS["white"],
                 fg=theme.COLORS["text"], font=theme.FONTS["small_bold"]).pack(side="left")

        self.product_combo = SearchableCombo(
            row2,
            on_select=self._on_product_change,
            on_enter=lambda _item: self._add_selected(),
            width=52,
        )
        self.product_combo.get_widget().pack(side="left", padx=(8, 12), ipady=4)

        # Hint al lado
        tk.Label(row2,
                 text="Escriba para filtrar · Enter para agregar · Esc para limpiar",
                 bg=theme.COLORS["white"], fg=theme.COLORS["gray"],
                 font=theme.FONTS["tiny"]).pack(side="left")

        self.add_btn = theme.make_button(
            row2, "AGREGAR", self._add_selected,
            kind="primary", padx=18, pady=6, font_key="small_bold",
        )
        self.add_btn.pack(side="right")

        # ----- Fila 3: adicionales -----
        self.addons_frame = tk.Frame(capture, bg=theme.COLORS["white"])
        self.addons_frame.pack(fill="x", padx=14, pady=(0, 12))

        tk.Label(self.addons_frame, text="Adicionales:", bg=theme.COLORS["white"],
                 fg=theme.COLORS["text"], font=theme.FONTS["small_bold"]).pack(side="left")

        self.addons_container = tk.Frame(self.addons_frame, bg=theme.COLORS["white"])
        self.addons_container.pack(side="left", padx=(8, 0))

        # ----- Eventos -----
        self.barcode_entry.bind("<Return>", self._scan_barcode)
        self.qty_entry.bind("<Return>", lambda e: self._add_selected())
        self.product_combo.get_widget().bind("<FocusIn>", self._on_product_focus_in)

        self.barcode_entry.focus_set()

    # =========================================================================
    # Catálogo
    # =========================================================================
    def _reload_products(self) -> None:
        """Carga el catálogo y llena el combo con formato 'SKU — Nombre · Categoría'."""
        self.all_products = self.products.list_products(only_active=True)
        self._refresh_product_combo()

    def _refresh_product_combo(self) -> None:
        items = []
        for p in self.all_products:
            category = p.get("category") or ""
            label = f"{p['sku']} — {p['name']}"
            if category:
                label += f"  ·  {category}"
            items.append((label, p))
        self.product_combo.set_items(items)

    def _on_product_focus_in(self, event=None) -> None:
        """Al enfocar el combo, selecciona el texto para que escribir reemplace."""
        self.product_combo.get_widget().select_range(0, "end")

    def _on_product_change(self, item: dict | None) -> None:
        """Al seleccionar un producto del combo, actualiza stock/presentaciones."""
        if not item:
            return

        if item["product_type"] == "SERVICE":
            self.stock_label.configure(text="Servicio · sin inventario",
                                       fg=theme.COLORS["gray"])
        else:
            stock = self.inventory.current_stock(int(item["id"]))
            self.stock_label.configure(
                text=f"Stock: {stock:.2f} {item['unit']}",
                fg=theme.COLORS["accent"] if stock > 0 else theme.COLORS["danger"],
            )

        self._load_presentations(item)
        self._load_addons(item)

    def _selected_product(self) -> dict | None:
        return self.product_combo.get_selected()

    def _load_presentations(self, product: dict) -> None:
        base = {
            "id": None,
            "name": product["unit"] or "Unidad",
            "factor": 1.0,
            "sale_price": float(product["sale_price"]),
            "barcode": product["barcode"] or "",
        }
        extras = []
        if product["product_type"] != "SERVICE":
            extras = self.products.list_presentations(int(product["id"]))

        self.current_presentations = [base] + extras
        values = [
            f"{x['name']} · {float(x['factor']):g}u · ${float(x['sale_price']):.2f}"
            for x in self.current_presentations
        ]
        self.presentation_combo["values"] = values
        if values:
            self.presentation_combo.current(0)

    def _load_addons(self, product: dict) -> None:
        self._clear_addons()
        self.current_addons = self.products.list_addons(int(product["id"]))
        for addon in self.current_addons:
            var = tk.BooleanVar(value=False)
            self.addon_vars.append(var)
            text = f"{addon['name']} (+${float(addon['extra_price']):.2f})"
            tk.Checkbutton(self.addons_container, text=text, variable=var,
                           bg=theme.COLORS["white"],
                           activebackground=theme.COLORS["white"],
                           font=theme.FONTS["tiny"]).pack(side="left", padx=6)

    def _clear_addons(self) -> None:
        for w in self.addons_container.winfo_children():
            w.destroy()
        self.addon_vars.clear()
        self.current_addons = []

    # =========================================================================
    # Escaneo / agregado
    # =========================================================================
    def _scan_barcode(self, event=None) -> None:
        code = self.barcode_var.get().strip()
        if not code:
            return
        resolved = self.products.resolve_barcode(code)
        if not resolved:
            modal.warning(self, "Código no encontrado",
                          f"No se encontró ningún producto con el código:\n{code}")
            self.barcode_entry.select_range(0, "end")
            return

        product = resolved["product"]
        presentation = resolved["presentation"]
        try:
            qty = float(self.qty_var.get() or 1)
        except ValueError:
            qty = 1.0

        self._add_to_cart(product, qty, presentation)
        self.barcode_var.set("")
        self.qty_var.set("1")
        self.barcode_entry.focus_set()

    def _add_selected(self) -> None:
        product = self._selected_product()
        if not product:
            modal.warning(self, "Venta",
                          "Escriba o seleccione un producto del combo.")
            self.product_combo.focus()
            return

        try:
            qty = float(self.qty_var.get())
        except ValueError:
            modal.warning(self, "Venta", "Ingrese una cantidad válida.")
            return
        if qty <= 0:
            modal.warning(self, "Venta", "La cantidad debe ser mayor que cero.")
            return

        pres_idx = self.presentation_combo.current()
        presentation = None
        if 0 <= pres_idx < len(self.current_presentations):
            presentation = self.current_presentations[pres_idx]

        selected_addons = [
            self.current_addons[i]
            for i, v in enumerate(self.addon_vars) if v.get()
        ]
        self._add_to_cart(product, qty, presentation, selected_addons)