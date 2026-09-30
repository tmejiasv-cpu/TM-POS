"""Vista de catálogo de productos."""
from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk

from vidpos.core.database import Database
from vidpos.services.inventory import InventoryService
from vidpos.services.products import (
    DuplicateError,
    ProductError,
    ProductService,
    ProductType,
)
from vidpos.ui import theme
from vidpos.ui.widgets import modal

log = logging.getLogger(__name__)


class ProductsView(tk.Frame):
    """Catálogo de productos con CRUD, búsqueda y gestión."""

    def __init__(self, parent: tk.Misc, *, db: Database, user: dict) -> None:
        super().__init__(parent, bg=theme.COLORS["light"])
        self.db = db
        self.user = user
        self.products = ProductService(db)
        self.inventory = InventoryService(db)

        self._build_ui()
        self._load_products()

    # =========================================================================
    # UI
    # =========================================================================
    def _build_ui(self) -> None:
        # ---------- Header ----------
        header = tk.Frame(self, bg=theme.COLORS["light"])
        header.pack(fill="x", pady=(8, 12))

        tk.Label(
            header, text="Catálogo de productos",
            bg=theme.COLORS["light"], fg=theme.COLORS["dark"],
            font=theme.FONTS["h1"],
        ).pack(side="left")

        self.count_label = tk.Label(
            header, text="",
            bg=theme.COLORS["light"], fg=theme.COLORS["gray"],
            font=theme.FONTS["small"],
        )
        self.count_label.pack(side="right")

        # ---------- Barra de búsqueda y acciones ----------
        toolbar = tk.Frame(
            self, bg=theme.COLORS["white"],
            highlightthickness=1, highlightbackground=theme.COLORS["border"],
        )
        toolbar.pack(fill="x", pady=(0, 10))

        search_frame = tk.Frame(toolbar, bg=theme.COLORS["white"])
        search_frame.pack(fill="x", padx=14, pady=10)

        tk.Label(
            search_frame, text="Buscar:",
            bg=theme.COLORS["white"], fg=theme.COLORS["text"],
            font=theme.FONTS["small_bold"],
        ).pack(side="left")

        self.search_var = tk.StringVar()
        self.search_entry = theme.make_entry(
            search_frame, textvariable=self.search_var, width=40,
        )
        self.search_entry.pack(side="left", padx=8, ipady=5)

        theme.make_button(
            search_frame, "LIMPIAR", self._clear_search,
            kind="neutral", padx=12, pady=5, font_key="tiny",
        ).pack(side="left", padx=(0, 20))

        theme.make_button(
            search_frame, "+ NUEVO PRODUCTO", self._new_product,
            kind="primary", padx=18, pady=6, font_key="small_bold",
        ).pack(side="right")

        # ---------- Tabla ----------
        table_frame = tk.Frame(
            self, bg=theme.COLORS["white"],
            highlightthickness=1, highlightbackground=theme.COLORS["border"],
        )
        table_frame.pack(fill="both", expand=True)

        cols = ("id", "sku", "barcode", "name", "type", "category",
                "price", "stock", "min")
        self.tree = ttk.Treeview(
            table_frame, columns=cols, show="headings", selectmode="browse",
        )
        for c, h, w, anchor in [
            ("id", "ID", 50, "center"),
            ("sku", "Código", 110, "w"),
            ("barcode", "Cód. barras", 120, "w"),
            ("name", "Producto", 260, "w"),
            ("type", "Tipo", 90, "center"),
            ("category", "Categoría", 130, "w"),
            ("price", "Precio", 90, "e"),
            ("stock", "Existencia", 90, "e"),
            ("min", "Mínimo", 80, "e"),
        ]:
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor=anchor)

        vscroll = ttk.Scrollbar(table_frame, orient="vertical",
                                command=self.tree.yview)
        self.tree.configure(yscrollcommand=vscroll.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=10)
        vscroll.pack(side="right", fill="y", pady=10)

        # Doble clic = modificar
        self.tree.bind("<Double-1>", lambda e: self._edit_selected())
        self.tree.bind("<Return>", lambda e: self._edit_selected())

        # ---------- Barra inferior de acciones ----------
        actions = tk.Frame(self, bg=theme.COLORS["light"])
        actions.pack(fill="x", pady=(8, 4))

        theme.make_button(
            actions, "MODIFICAR", self._edit_selected,
            kind="info", padx=16, pady=7, font_key="small_bold",
        ).pack(side="left", padx=(0, 6))

        theme.make_button(
            actions, "PRESENTACIONES", self._manage_presentations,
            kind="accent", padx=16, pady=7, font_key="small_bold",
        ).pack(side="left", padx=6)

        theme.make_button(
            actions, "ADICIONALES", self._manage_addons,
            kind="info", padx=16, pady=7, font_key="small_bold",
        ).pack(side="left", padx=6)

        # Solo admin puede desactivar
        if self.user["role"] == "admin":
            theme.make_button(
                actions, "DESACTIVAR", self._deactivate_selected,
                kind="danger", padx=16, pady=7, font_key="small_bold",
            ).pack(side="left", padx=6)

        theme.make_button(
            actions, "ACTUALIZAR", self._load_products,
            kind="neutral", padx=14, pady=7, font_key="small_bold",
        ).pack(side="right")

        # Búsqueda en vivo
        self.search_var.trace_add("write", lambda *a: self._load_products())
        self.search_entry.focus_set()

    # =========================================================================
    # Carga de datos
    # =========================================================================
    def _load_products(self) -> None:
        for row in self.tree.get_children():
            self.tree.delete(row)

        term = self.search_var.get().strip()
        products = self.products.list_products(search=term, only_active=True)

        for p in products:
            is_service = p["product_type"] == "SERVICE"
            stock_text = "—" if is_service else (
                f"{self.inventory.current_stock(int(p['id'])):.2f}"
            )
            min_text = "—" if is_service else f"{float(p['min_stock']):.2f}"

            self.tree.insert("", "end", iid=str(p["id"]), values=(
                p["id"],
                p["sku"],
                p["barcode"] or "",
                p["name"],
                "Servicio" if is_service else "Producto",
                p["category"] or "",
                f"${float(p['sale_price']):.2f}",
                stock_text,
                min_text,
            ))

        total = len(products)
        self.count_label.configure(
            text=f"{total} producto{'s' if total != 1 else ''}"
        )

    def _clear_search(self) -> None:
        self.search_var.set("")
        self.search_entry.focus_set()

    # =========================================================================
    # Acciones
    # =========================================================================
    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return int(sel[0])

    def _new_product(self) -> None:
        self._product_form()

    def _edit_selected(self) -> None:
        pid = self._selected_id()
        if not pid:
            modal.warning(self, "Seleccione un producto",
                          "Debe seleccionar un producto de la lista.")
            return
        self._product_form(pid)

    def _deactivate_selected(self) -> None:
        pid = self._selected_id()
        if not pid:
            modal.warning(self, "Seleccione un producto",
                          "Debe seleccionar un producto de la lista.")
            return

        product = self.products.get(pid)
        if not product:
            return

        has_history = self.products.has_history(pid)

        if has_history:
            ok = modal.confirm(
                self, "Desactivar producto",
                f"{product['name']} ya tiene historial de ventas, compras o movimientos.\n\n"
                "Se marcará como inactivo y dejará de aparecer en nuevas operaciones.",
                primary_text="DESACTIVAR",
                secondary_text="VOLVER",
            )
            if not ok:
                return
            self.products.deactivate(pid)
            modal.success(self, "Producto desactivado",
                          f"{product['name']} ya no aparecerá en el catálogo activo.")
        else:
            ok = modal.confirm(
                self, "Eliminar producto",
                f"{product['name']} no tiene historial.\n\n"
                "Se eliminará permanentemente del catálogo.\n"
                "¿Está seguro?",
                primary_text="ELIMINAR",
                secondary_text="VOLVER",
            )
            if not ok:
                return
            if self.products.delete_if_no_history(pid):
                modal.success(self, "Producto eliminado",
                              f"{product['name']} fue eliminado del catálogo.")
            else:
                modal.error(self, "No se pudo eliminar",
                            "El producto tiene historial. Se desactivará en su lugar.")
                self.products.deactivate(pid)

        self._load_products()

    def _manage_presentations(self) -> None:
        pid = self._selected_id()
        if not pid:
            modal.warning(self, "Seleccione un producto",
                          "Debe seleccionar un producto para gestionar presentaciones.")
            return
        self._presentations_form(pid)

    def _manage_addons(self) -> None:
        pid = self._selected_id()
        if not pid:
            modal.warning(self, "Seleccione un producto",
                          "Debe seleccionar un producto para gestionar adicionales.")
            return
        self._addons_form(pid)

    # =========================================================================
    # Formulario de producto
    # =========================================================================
    def _product_form(self, product_id: int | None = None) -> None:
        existing = self.products.get(product_id) if product_id else None

        win = tk.Toplevel(self)
        win.title("Modificar producto" if existing else "Nuevo producto")
        win.configure(bg=theme.COLORS["white"])
        win.transient(self.winfo_toplevel())
        win.grab_set()
        win.resizable(False, False)
        win.geometry("520x680")

        # Container con scroll por si acaso
        outer = tk.Frame(win, bg=theme.COLORS["white"])
        outer.pack(fill="both", expand=True)

        canvas = tk.Canvas(outer, bg=theme.COLORS["white"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        box = tk.Frame(canvas, bg=theme.COLORS["white"], padx=30, pady=22)
        box_id = canvas.create_window((0, 0), window=box, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(box_id, width=e.width))
        box.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        tk.Label(
            box, text="Modificar producto" if existing else "Registrar producto",
            bg=theme.COLORS["white"], fg=theme.COLORS["dark"],
            font=theme.FONTS["h2"],
        ).pack(anchor="w", pady=(0, 16))

        fields: dict[str, tk.Entry] = {}

        def add_field(label: str, key: str, value: str = "",
                      readonly: bool = False) -> tk.Entry:
            tk.Label(box, text=label, bg=theme.COLORS["white"],
                     fg=theme.COLORS["text"], font=theme.FONTS["small_bold"]).pack(anchor="w")
            e = theme.make_entry(box, font_key="h4")
            e.pack(fill="x", pady=(4, 12), ipady=6)
            e.insert(0, value)
            if readonly:
                e.configure(state="readonly")
            fields[key] = e
            return e

        # Tipo de producto
        tk.Label(box, text="Tipo", bg=theme.COLORS["white"],
                 fg=theme.COLORS["text"], font=theme.FONTS["small_bold"]).pack(anchor="w")
        type_combo = ttk.Combobox(
            box, state="readonly", values=["PRODUCT", "SERVICE"],
            font=theme.FONTS["h4"],
        )
        type_combo.pack(fill="x", pady=(4, 4))
        type_combo.set(existing["product_type"] if existing else "PRODUCT")
        tk.Label(
            box,
            text="PRODUCT = controla inventario · SERVICE = no maneja existencias",
            bg=theme.COLORS["white"], fg=theme.COLORS["gray"],
            font=theme.FONTS["tiny"],
        ).pack(anchor="w", pady=(0, 12))

        # SKU automático (readonly)
        if existing:
            add_field("Código interno (SKU)", "sku", existing["sku"], readonly=True)
        else:
            auto_sku = self.products.generate_sku()
            add_field("Código interno (SKU) — automático", "sku", auto_sku, readonly=True)

        add_field("Código de barras",
                  "barcode", existing["barcode"] or "" if existing else "")
        add_field("Nombre *", "name", existing["name"] if existing else "")

        # Categoría con combo editable
        tk.Label(box, text="Categoría", bg=theme.COLORS["white"],
                 fg=theme.COLORS["text"], font=theme.FONTS["small_bold"]).pack(anchor="w")
        categories = self.products.list_categories()
        cat_combo = ttk.Combobox(box, values=categories, state="normal",
                                 font=theme.FONTS["h4"])
        cat_combo.pack(fill="x", pady=(4, 12), ipady=4)
        if existing:
            cat_combo.set(existing["category"] or "")

        add_field("Unidad", "unit", existing["unit"] if existing else "Unidad")
        add_field("Precio de venta *", "sale_price",
                  str(existing["sale_price"]) if existing else "")
        add_field("Stock mínimo", "min_stock",
                  str(existing["min_stock"]) if existing else "0")

        tk.Label(
            box,
            text="La existencia se modifica mediante compras/entradas, no desde aquí.",
            bg=theme.COLORS["white"], fg=theme.COLORS["gray"],
            font=theme.FONTS["tiny"], wraplength=430, justify="left",
        ).pack(anchor="w", pady=(0, 16))

        # ---------- Botones ----------
        btn_row = tk.Frame(box, bg=theme.COLORS["white"])
        btn_row.pack(fill="x")

        def save():
            try:
                name = fields["name"].get().strip()
                price = float(fields["sale_price"].get())
                min_stock = float(fields["min_stock"].get() or 0)
                barcode = fields["barcode"].get().strip() or None
                category = cat_combo.get().strip()
                unit = fields["unit"].get().strip() or "Unidad"
                product_type = type_combo.get() or "PRODUCT"

                if not name:
                    raise ValueError("El nombre es obligatorio.")
                if price < 0:
                    raise ValueError("El precio no puede ser negativo.")
                if min_stock < 0:
                    raise ValueError("El stock mínimo no puede ser negativo.")

                if existing:
                    self.products.update(
                        product_id=existing["id"],
                        name=name, sale_price=price, unit=unit,
                        category=category, barcode=barcode,
                        min_stock=min_stock, product_type=product_type,
                    )
                    modal.success(win, "Producto actualizado",
                                  f"{name} fue actualizado correctamente.")
                else:
                    self.products.create(
                        name=name, sale_price=price, unit=unit,
                        category=category, barcode=barcode,
                        min_stock=min_stock, product_type=product_type,
                        created_by=int(self.user["id"]),
                    )
                    modal.success(win, "Producto creado",
                                  f"{name} fue registrado correctamente.")

                win.destroy()
                self._load_products()
            except DuplicateError as e:
                modal.error(win, "Duplicado", str(e))
            except ProductError as e:
                modal.error(win, "Datos inválidos", str(e))
            except ValueError as e:
                modal.error(win, "Datos inválidos", str(e))
            except Exception as e:
                log.exception("Error guardando producto")
                modal.error(win, "Error inesperado", str(e))

        theme.make_button(
            btn_row, "GUARDAR", save,
            kind="primary", padx=20, pady=9, font_key="small_bold",
        ).pack(side="left", fill="x", expand=True, padx=(0, 4))

        theme.make_button(
            btn_row, "CANCELAR", win.destroy,
            kind="neutral", padx=20, pady=9, font_key="small_bold",
        ).pack(side="left", fill="x", expand=True, padx=(4, 0))

        win.bind("<Return>", lambda e: save())
        win.bind("<Escape>", lambda e: win.destroy())

        fields["name"].focus_set()

    # =========================================================================
    # Formulario de presentaciones (simplificado)
    # =========================================================================
    def _presentations_form(self, product_id: int) -> None:
        product = self.products.get(product_id)
        if not product:
            return

        win = tk.Toplevel(self)
        win.title(f"Presentaciones — {product['name']}")
        win.configure(bg=theme.COLORS["white"])
        win.transient(self.winfo_toplevel())
        win.grab_set()
        win.geometry("720x540")

        box = tk.Frame(win, bg=theme.COLORS["white"], padx=20, pady=18)
        box.pack(fill="both", expand=True)

        tk.Label(
            box, text=f"Presentaciones de {product['name']}",
            bg=theme.COLORS["white"], fg=theme.COLORS["dark"],
            font=theme.FONTS["h2"],
        ).pack(anchor="w")

        tk.Label(
            box,
            text=f"Unidad base: {product['unit']} · Precio base: ${float(product['sale_price']):.2f}",
            bg=theme.COLORS["white"], fg=theme.COLORS["gray"],
            font=theme.FONTS["small"],
        ).pack(anchor="w", pady=(2, 14))

        # Tabla
        table_frame = tk.Frame(box, bg=theme.COLORS["white"])
        table_frame.pack(fill="both", expand=True)

        cols = ("id", "name", "factor", "price", "barcode")
        tree = ttk.Treeview(table_frame, columns=cols, show="headings",
                            selectmode="browse")
        for c, h, w in [
            ("id", "ID", 50), ("name", "Presentación", 200),
            ("factor", "Equivale a", 100), ("price", "Precio", 100),
            ("barcode", "Cód. barras", 150),
        ]:
            tree.heading(c, text=h)
            tree.column(c, width=w)

        vscroll = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vscroll.set)
        tree.pack(side="left", fill="both", expand=True)
        vscroll.pack(side="right", fill="y")

        def reload_list():
            for item in tree.get_children():
                tree.delete(item)
            for p in self.products.list_presentations(product_id):
                tree.insert("", "end", iid=str(p["id"]), values=(
                    p["id"], p["name"], f"{float(p['factor']):g}",
                    f"${float(p['sale_price']):.2f}", p["barcode"] or "",
                ))

        reload_list()

        # Botonera
        actions = tk.Frame(box, bg=theme.COLORS["white"])
        actions.pack(fill="x", pady=(12, 0))

        def add_pres():
            self._presentation_edit_dialog(product_id, None, reload_list)

        def edit_pres():
            sel = tree.selection()
            if not sel:
                modal.warning(win, "Seleccione una presentación",
                              "Debe seleccionar una presentación de la lista.")
                return
            self._presentation_edit_dialog(product_id, int(sel[0]), reload_list)

        def del_pres():
            sel = tree.selection()
            if not sel:
                modal.warning(win, "Seleccione una presentación",
                              "Debe seleccionar una presentación de la lista.")
                return
            pres_id = int(sel[0])
            if modal.confirm(win, "Eliminar presentación",
                             "¿Desactivar esta presentación?"):
                self.products.deactivate_presentation(pres_id)
                reload_list()

        theme.make_button(actions, "+ NUEVA", add_pres,
                          kind="primary", padx=14, pady=6).pack(side="left", padx=(0, 4))
        theme.make_button(actions, "MODIFICAR", edit_pres,
                          kind="info", padx=14, pady=6).pack(side="left", padx=4)
        theme.make_button(actions, "DESACTIVAR", del_pres,
                          kind="danger", padx=14, pady=6).pack(side="left", padx=4)
        theme.make_button(actions, "CERRAR", win.destroy,
                          kind="neutral", padx=14, pady=6).pack(side="right")

    def _presentation_edit_dialog(self, product_id: int,
                                   presentation_id: int | None,
                                   on_save) -> None:
        product = self.products.get(product_id)
        existing = None
        if presentation_id:
            for p in self.products.list_presentations(product_id):
                if p["id"] == presentation_id:
                    existing = p
                    break

        win = tk.Toplevel(self)
        win.title("Modificar presentación" if existing else "Nueva presentación")
        win.configure(bg=theme.COLORS["white"])
        win.transient(self.winfo_toplevel())
        win.grab_set()
        win.resizable(False, False)
        win.geometry("420x460")

        box = tk.Frame(win, bg=theme.COLORS["white"], padx=26, pady=22)
        box.pack(fill="both", expand=True)

        tk.Label(
            box, text="Modificar presentación" if existing else "Nueva presentación",
            bg=theme.COLORS["white"], fg=theme.COLORS["dark"],
            font=theme.FONTS["h2"],
        ).pack(anchor="w", pady=(0, 14))

        def add_field(label, value=""):
            tk.Label(box, text=label, bg=theme.COLORS["white"],
                     fg=theme.COLORS["text"], font=theme.FONTS["small_bold"]).pack(anchor="w")
            e = theme.make_entry(box, font_key="h4")
            e.pack(fill="x", pady=(4, 12), ipady=6)
            e.insert(0, value)
            return e

        e_name = add_field("Nombre *", existing["name"] if existing else "")
        e_factor = add_field(
            f"Cantidad de {product['unit']} que descuenta *",
            str(existing["factor"]) if existing else "1",
        )
        e_price = add_field(
            "Precio de venta *",
            str(existing["sale_price"]) if existing else str(product["sale_price"]),
        )
        e_barcode = add_field("Código de barras opcional",
                              existing["barcode"] or "" if existing else "")

        def save():
            try:
                name = e_name.get().strip()
                factor = float(e_factor.get())
                price = float(e_price.get())
                barcode = e_barcode.get().strip() or None

                if not name:
                    raise ValueError("El nombre es obligatorio.")
                if factor <= 0:
                    raise ValueError("El factor debe ser mayor que cero.")
                if price < 0:
                    raise ValueError("El precio no puede ser negativo.")

                if existing:
                    self.products.update_presentation(
                        existing["id"], name=name, factor=factor,
                        sale_price=price, barcode=barcode,
                    )
                else:
                    self.products.add_presentation(
                        product_id, name=name, factor=factor,
                        sale_price=price, barcode=barcode,
                        created_by=int(self.user["id"]),
                    )
                win.destroy()
                on_save()
            except DuplicateError as e:
                modal.error(win, "Duplicado", str(e))
            except (ProductError, ValueError) as e:
                modal.error(win, "Datos inválidos", str(e))
            except Exception as e:
                log.exception("Error guardando presentación")
                modal.error(win, "Error inesperado", str(e))

        btn_row = tk.Frame(box, bg=theme.COLORS["white"])
        btn_row.pack(fill="x", pady=(8, 0))
        theme.make_button(btn_row, "GUARDAR", save,
                          kind="primary", padx=18, pady=9).pack(
            side="left", fill="x", expand=True, padx=(0, 4))
        theme.make_button(btn_row, "CANCELAR", win.destroy,
                          kind="neutral", padx=18, pady=9).pack(
            side="left", fill="x", expand=True, padx=(4, 0))

        e_name.focus_set()

    # =========================================================================
    # Formulario de adicionales (simplificado)
    # =========================================================================
    def _addons_form(self, product_id: int) -> None:
        product = self.products.get(product_id)
        if not product:
            return

        win = tk.Toplevel(self)
        win.title(f"Adicionales — {product['name']}")
        win.configure(bg=theme.COLORS["white"])
        win.transient(self.winfo_toplevel())
        win.grab_set()
        win.geometry("780x540")

        box = tk.Frame(win, bg=theme.COLORS["white"], padx=20, pady=18)
        box.pack(fill="both", expand=True)

        tk.Label(
            box, text=f"Adicionales de {product['name']}",
            bg=theme.COLORS["white"], fg=theme.COLORS["dark"],
            font=theme.FONTS["h2"],
        ).pack(anchor="w")

        tk.Label(
            box,
            text="Un adicional puede sumar precio sin consumir inventario, "
                 "o consumir otro producto del catálogo.",
            bg=theme.COLORS["white"], fg=theme.COLORS["gray"],
            font=theme.FONTS["small"],
        ).pack(anchor="w", pady=(2, 14))

        table_frame = tk.Frame(box, bg=theme.COLORS["white"])
        table_frame.pack(fill="both", expand=True)

        cols = ("id", "name", "price", "component", "qty")
        tree = ttk.Treeview(table_frame, columns=cols, show="headings",
                            selectmode="browse")
        for c, h, w in [
            ("id", "ID", 45), ("name", "Adicional", 200),
            ("price", "Precio extra", 100),
            ("component", "Producto que consume", 220),
            ("qty", "Cantidad", 90),
        ]:
            tree.heading(c, text=h)
            tree.column(c, width=w)

        vscroll = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vscroll.set)
        tree.pack(side="left", fill="both", expand=True)
        vscroll.pack(side="right", fill="y")

        def reload_list():
            for item in tree.get_children():
                tree.delete(item)
            for a in self.products.list_addons(product_id):
                tree.insert("", "end", iid=str(a["id"]), values=(
                    a["id"], a["name"], f"${float(a['extra_price']):.2f}",
                    a["component_name"] or "Solo servicio",
                    f"{float(a['component_qty']):g}",
                ))

        reload_list()

        actions = tk.Frame(box, bg=theme.COLORS["white"])
        actions.pack(fill="x", pady=(12, 0))

        def add_addon():
            self._addon_edit_dialog(product_id, None, reload_list)

        def edit_addon():
            sel = tree.selection()
            if not sel:
                modal.warning(win, "Seleccione un adicional",
                              "Debe seleccionar un adicional de la lista.")
                return
            self._addon_edit_dialog(product_id, int(sel[0]), reload_list)

        def del_addon():
            sel = tree.selection()
            if not sel:
                return
            if modal.confirm(win, "Eliminar adicional",
                             "¿Desactivar este adicional?"):
                self.products.deactivate_addon(int(sel[0]))
                reload_list()

        theme.make_button(actions, "+ NUEVO", add_addon,
                          kind="primary", padx=14, pady=6).pack(side="left", padx=(0, 4))
        theme.make_button(actions, "MODIFICAR", edit_addon,
                          kind="info", padx=14, pady=6).pack(side="left", padx=4)
        theme.make_button(actions, "DESACTIVAR", del_addon,
                          kind="danger", padx=14, pady=6).pack(side="left", padx=4)
        theme.make_button(actions, "CERRAR", win.destroy,
                          kind="neutral", padx=14, pady=6).pack(side="right")

    def _addon_edit_dialog(self, product_id: int,
                            addon_id: int | None, on_save) -> None:
        existing = None
        if addon_id:
            for a in self.products.list_addons(product_id):
                if a["id"] == addon_id:
                    existing = a
                    break

        win = tk.Toplevel(self)
        win.title("Modificar adicional" if existing else "Nuevo adicional")
        win.configure(bg=theme.COLORS["white"])
        win.transient(self.winfo_toplevel())
        win.grab_set()
        win.resizable(False, False)
        win.geometry("480x540")

        box = tk.Frame(win, bg=theme.COLORS["white"], padx=26, pady=22)
        box.pack(fill="both", expand=True)

        tk.Label(
            box, text="Modificar adicional" if existing else "Nuevo adicional",
            bg=theme.COLORS["white"], fg=theme.COLORS["dark"],
            font=theme.FONTS["h2"],
        ).pack(anchor="w", pady=(0, 14))

        tk.Label(box, text="Nombre *", bg=theme.COLORS["white"],
                 fg=theme.COLORS["text"], font=theme.FONTS["small_bold"]).pack(anchor="w")
        e_name = theme.make_entry(box, font_key="h4")
        e_name.pack(fill="x", pady=(4, 12), ipady=6)
        if existing:
            e_name.insert(0, existing["name"])

        tk.Label(box, text="Precio adicional *", bg=theme.COLORS["white"],
                 fg=theme.COLORS["text"], font=theme.FONTS["small_bold"]).pack(anchor="w")
        e_price = theme.make_entry(box, font_key="h4")
        e_price.pack(fill="x", pady=(4, 12), ipady=6)
        e_price.insert(0, str(existing["extra_price"]) if existing else "0")

        tk.Label(box, text="Producto que consume", bg=theme.COLORS["white"],
                 fg=theme.COLORS["text"], font=theme.FONTS["small_bold"]).pack(anchor="w")

        inventory_products = self.products.list_products(
            product_type=ProductType.PRODUCT, only_active=True,
        )
        choices = ["Solo servicio / no consume inventario"] + [
            f"{p['sku']} — {p['name']}" for p in inventory_products
        ]
        comp_combo = ttk.Combobox(box, state="readonly", values=choices,
                                   font=theme.FONTS["body"])
        comp_combo.pack(fill="x", pady=(4, 12), ipady=4)
        comp_combo.current(0)

        if existing and existing.get("component_product_id"):
            for idx, p in enumerate(inventory_products, 1):
                if p["id"] == existing["component_product_id"]:
                    comp_combo.current(idx)
                    break

        tk.Label(box, text="Cantidad que consume", bg=theme.COLORS["white"],
                 fg=theme.COLORS["text"], font=theme.FONTS["small_bold"]).pack(anchor="w")
        e_qty = theme.make_entry(box, font_key="h4")
        e_qty.pack(fill="x", pady=(4, 12), ipady=6)
        e_qty.insert(0, str(existing["component_qty"]) if existing else "0")

        tk.Label(
            box,
            text="Ejemplos:\n"
                 "· Preparación: precio $0.25, sin producto.\n"
                 "· Cremora: precio $0.10, producto Cremora, cantidad 1.",
            bg=theme.COLORS["white"], fg=theme.COLORS["gray"],
            font=theme.FONTS["tiny"], justify="left",
        ).pack(anchor="w", pady=(0, 14))

        def save():
            try:
                name = e_name.get().strip()
                price = float(e_price.get())
                qty = float(e_qty.get() or 0)

                if not name:
                    raise ValueError("El nombre es obligatorio.")
                if price < 0:
                    raise ValueError("El precio no puede ser negativo.")
                if qty < 0:
                    raise ValueError("La cantidad no puede ser negativa.")

                comp_id = None
                idx = comp_combo.current()
                if idx > 0:
                    comp_id = int(inventory_products[idx - 1]["id"])
                    if qty <= 0:
                        raise ValueError(
                            "Si consume un producto, indique una cantidad mayor que cero."
                        )
                else:
                    qty = 0.0

                if existing:
                    self.products.update_addon(
                        existing["id"], name=name, extra_price=price,
                        component_product_id=comp_id, component_qty=qty,
                    )
                else:
                    self.products.add_addon(
                        product_id, name=name, extra_price=price,
                        component_product_id=comp_id, component_qty=qty,
                        created_by=int(self.user["id"]),
                    )
                win.destroy()
                on_save()
            except (ProductError, ValueError) as e:
                modal.error(win, "Datos inválidos", str(e))
            except Exception as e:
                log.exception("Error guardando adicional")
                modal.error(win, "Error inesperado", str(e))

        btn_row = tk.Frame(box, bg=theme.COLORS["white"])
        btn_row.pack(fill="x", pady=(8, 0))
        theme.make_button(btn_row, "GUARDAR", save,
                          kind="primary", padx=18, pady=9).pack(
            side="left", fill="x", expand=True, padx=(0, 4))
        theme.make_button(btn_row, "CANCELAR", win.destroy,
                          kind="neutral", padx=18, pady=9).pack(
            side="left", fill="x", expand=True, padx=(4, 0))

        e_name.focus_set()