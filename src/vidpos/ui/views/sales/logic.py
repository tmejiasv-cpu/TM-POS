"""Lógica de negocio del POS: agregar al carrito, borrador, cobrar."""
from __future__ import annotations

import logging

from vidpos.services.sales import (
    AddonSelection,
    CartItem,
    InsufficientPaymentError,
    SaleError,
)
from vidpos.ui import theme
from vidpos.ui.widgets import modal

log = logging.getLogger(__name__)


class SalesLogicMixin:
    """Mixin: métodos de negocio del POS."""

    # =========================================================================
    # Agregar al carrito
    # =========================================================================
    def _add_to_cart(self, product, qty, presentation=None,
                     selected_addons=None) -> None:
        selected_addons = selected_addons or []

        if presentation is None:
            factor = 1.0
            price = float(product["sale_price"])
            pres_name = product["unit"] or "Unidad"
        else:
            factor = float(presentation["factor"])
            price = float(presentation["sale_price"])
            pres_name = presentation["name"]

        is_service = product["product_type"] == "SERVICE"
        inventory_qty = 0.0 if is_service else qty * factor

        # Validar stock del producto
        if not is_service:
            stock = self.inventory.current_stock(int(product["id"]))
            in_cart = sum(x.inventory_qty for x in self.cart
                          if x.product_id == int(product["id"]))
            if inventory_qty + in_cart > stock + 1e-9:
                modal.warning(
                    self, "Stock insuficiente",
                    f"Producto: {product['name']}\n"
                    f"Disponible: {stock:.2f} {product['unit']}\n"
                    f"Solicitado: {inventory_qty + in_cart:.2f}",
                )
                return

        # Validar componentes de adicionales
        for addon in selected_addons:
            comp_id = addon.get("component_product_id")
            comp_qty = float(addon.get("component_qty") or 0) * qty
            if comp_id and comp_qty > 0:
                stock = self.inventory.current_stock(int(comp_id))
                already = sum(
                    float(a.get("component_qty") or 0) * x.sale_qty
                    for x in self.cart for a in x.addons
                    if a.component_product_id == comp_id
                )
                if already + comp_qty > stock + 1e-9:
                    comp = self.products.get(int(comp_id))
                    modal.warning(
                        self, "Stock insuficiente (adicional)",
                        f"Componente: {comp['name'] if comp else comp_id}\n"
                        f"Disponible: {stock:.2f}\n"
                        f"Necesario: {already + comp_qty:.2f}",
                    )
                    return

        addon_sels = [
            AddonSelection(
                addon_id=int(a["id"]) if a.get("id") is not None else None,
                name=a["name"],
                extra_price=float(a["extra_price"]),
                component_product_id=a.get("component_product_id"),
                component_qty=float(a.get("component_qty") or 0),
            )
            for a in selected_addons
        ]

        item = CartItem(
            product_id=int(product["id"]),
            sku=product["sku"],
            name=product["name"],
            product_type=product["product_type"],
            presentation_name=pres_name,
            presentation_factor=factor,
            sale_qty=qty,
            inventory_qty=inventory_qty,
            unit_price=price,
            addons=addon_sels,
        )
        self.cart.append(item)

        for v in self.addon_vars:
            v.set(False)
        self.qty_var.set("1")
        self.product_combo.clear()

        self._refresh_cart()
        self._save_draft()
        self.barcode_entry.focus_set()

    # =========================================================================
    # Borrador
    # =========================================================================
    def _save_draft(self) -> None:
        try:
            method = getattr(self, "payment_method_var", None)
            method = method.get() if method else "Efectivo"
            received = getattr(self, "received_var", None)
            received = received.get() if received else ""
            cash_session_id = int(self.cash_session.id) if self.cash_session else None
            self.sales.save_draft(
                user_id=int(self.user["id"]),
                cart=self.cart,
                payment_method=method,
                amount_received=received,
                cash_session_id=cash_session_id,
            )
        except Exception:
            log.exception("No se pudo guardar el borrador")

    def _recover_draft(self) -> None:
        try:
            draft = self.sales.get_draft(int(self.user["id"]))
            if not draft or not draft["cart"]:
                return

            total = sum(item.subtotal for item in draft["cart"])
            ok = modal.confirm(
                self, "Venta pendiente recuperable",
                (f"Se encontró una venta en curso guardada el {draft['updated_at']}.\n\n"
                 f"Artículos: {len(draft['cart'])}\n"
                 f"Total aproximado: ${total:.2f}\n\n¿Desea recuperarla?"),
                primary_text="RECUPERAR", secondary_text="DESCARTAR",
            )
            if ok:
                self.cart = draft["cart"]
                self.payment_method_var.set(draft["payment_method"] or "Efectivo")
                self.received_var.set(draft["amount_received"] or "")
                self._update_payment_ui()
                self._refresh_cart()
                self._calculate_change()
            else:
                self.sales.clear_draft(int(self.user["id"]))
        except Exception:
            log.exception("No se pudo recuperar el borrador")

    # =========================================================================
    # Caja
    # =========================================================================
    def _refresh_cash_status(self) -> None:
        self.cash_session = self.cash.get_open_session(int(self.user["id"]))
        if self.cash_session:
            self.cash_status_label.configure(
                text="● CAJA ABIERTA", bg=theme.COLORS["accent"],
            )
        else:
            self.cash_status_label.configure(
                text="● CAJA CERRADA", bg=theme.COLORS["danger"],
            )

    # =========================================================================
    # Cobrar
    # =========================================================================
    def _finalize_sale(self) -> None:
        if not self.cash_session:
            modal.warning(
                self, "Caja cerrada",
                "Debe abrir caja antes de registrar ventas.\n"
                "Vaya al módulo Caja y abra una jornada.",
            )
            return

        if not self.cart:
            modal.warning(self, "Venta vacía",
                          "No hay productos en la venta actual.")
            return

        method = self.payment_method_var.get()
        amount_received: float | None = None

        if method == "Efectivo":
            raw = self.received_var.get().strip()
            try:
                amount_received = float(raw) if raw else 0.0
            except ValueError:
                modal.warning(self, "Monto inválido",
                              "El efectivo recibido no es un número válido.")
                self.received_entry.focus_set()
                return

            total = self._current_total()
            if amount_received < total:
                modal.warning(
                    self, "Pago incompleto",
                    f"El efectivo recibido no cubre el total.\n\n"
                    f"Total: ${total:.2f}\n"
                    f"Recibido: ${amount_received:.2f}\n"
                    f"Falta: ${total - amount_received:.2f}",
                )
                self.received_entry.focus_set()
                return

        try:
            result = self.sales.register_sale(
                user_id=int(self.user["id"]),
                cash_session_id=int(self.cash_session.id),
                cart=self.cart,
                payment_method=method,
                amount_received=amount_received,
            )
        except InsufficientPaymentError as e:
            modal.error(self, "Pago insuficiente", str(e))
            return
        except SaleError as e:
            modal.error(self, "No se pudo registrar", str(e))
            return
        except Exception as e:
            log.exception("Error registrando venta")
            modal.error(self, "Error inesperado",
                        "No se pudo completar la venta. Revisa el log.",
                        detail=str(e))
            return

        detail = f"Venta #{result.sale_id}  ·  Total ${result.total:.2f}"
        if method == "Efectivo" and amount_received is not None:
            detail += (f"\nRecibido ${amount_received:.2f}  ·  "
                       f"Cambio ${result.change_given:.2f}")

        modal.success(self, "Venta registrada",
                      "La venta fue guardada correctamente.",
                      detail=detail)

        # Reset
        self.cart = []
        self.received_var.set("")
        self.payment_method_var.set("Efectivo")
        self._refresh_cart()
        self._update_payment_ui()
        self._calculate_change()
        self._refresh_cash_status()
        self.barcode_entry.focus_set()