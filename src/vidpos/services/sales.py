"""Servicio de ventas: POS, cobro, anulación y devoluciones.

Este servicio es el corazón del negocio. Coordina:

  - ProductService  → información de productos, presentaciones, adicionales
  - InventoryService → consumo FIFO y restauración por devoluciones

Reglas críticas:
  - Una venta se registra en una sola transacción atómica.
  - El costo de venta se calcula con FIFO real por lotes.
  - El borrador de venta NO descuenta inventario.
  - Una venta confirmada limpia el borrador inmediatamente tras el COMMIT.
  - Anular una venta restaura inventario al costo original.
  - Las devoluciones parciales restauran solo la parte devuelta.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime

from vidpos.core.database import Database
from vidpos.services.inventory import (
    FIFOConsumption,
    InsufficientStockError,
    InventoryError,
    InventoryService,
    MovementType,
)
from vidpos.services.products import ProductService

log = logging.getLogger(__name__)


# =============================================================================
# Excepciones
# =============================================================================
class SaleError(Exception):
    """Error de dominio en ventas."""


class CartEmptyError(SaleError):
    """El carrito está vacío."""


class NoCashSessionError(SaleError):
    """No hay una jornada de caja abierta."""


class InsufficientPaymentError(SaleError):
    """El efectivo recibido no cubre el total."""

    def __init__(self, total: float, received: float):
        self.total = total
        self.received = received
        self.missing = total - received
        super().__init__(
            f"Faltan ${self.missing:.2f} (total ${total:.2f}, recibido ${received:.2f})"
        )


class SaleAlreadyVoidedError(SaleError):
    """La venta ya fue anulada."""


class SaleHasReturnsError(SaleError):
    """La venta tiene devoluciones parciales, no se puede anular completa."""


class ReturnExceedsSaleError(SaleError):
    """Se intenta devolver más de lo vendido."""


# =============================================================================
# DTOs
# =============================================================================
@dataclass
class AddonSelection:
    """Adicional seleccionado por el cajero."""
    addon_id: int | None
    name: str
    extra_price: float
    component_product_id: int | None = None
    component_qty: float = 0.0


@dataclass
class CartItem:
    """Ítem del carrito antes de confirmar la venta."""
    product_id: int
    sku: str
    name: str
    product_type: str
    presentation_name: str
    presentation_factor: float
    sale_qty: float
    inventory_qty: float
    unit_price: float
    addons: list[AddonSelection] = field(default_factory=list)

    @property
    def addon_total(self) -> float:
        return sum(a.extra_price for a in self.addons)

    @property
    def display_unit_price(self) -> float:
        return self.unit_price + self.addon_total

    @property
    def subtotal(self) -> float:
        return self.sale_qty * self.display_unit_price

    def to_dict(self) -> dict:
        return {
            "product_id": self.product_id,
            "sku": self.sku,
            "name": self.name,
            "product_type": self.product_type,
            "presentation_name": self.presentation_name,
            "presentation_factor": self.presentation_factor,
            "sale_qty": self.sale_qty,
            "inventory_qty": self.inventory_qty,
            "unit_price": self.unit_price,
            "addons": [
                {
                    "addon_id": a.addon_id,
                    "name": a.name,
                    "extra_price": a.extra_price,
                    "component_product_id": a.component_product_id,
                    "component_qty": a.component_qty,
                }
                for a in self.addons
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CartItem":
        return cls(
            product_id=data["product_id"],
            sku=data["sku"],
            name=data["name"],
            product_type=data["product_type"],
            presentation_name=data["presentation_name"],
            presentation_factor=data["presentation_factor"],
            sale_qty=data["sale_qty"],
            inventory_qty=data["inventory_qty"],
            unit_price=data["unit_price"],
            addons=[
                AddonSelection(**a) for a in data.get("addons", [])
            ],
        )


@dataclass
class SaleResult:
    """Resultado de registrar una venta."""
    sale_id: int
    total: float
    cost_total: float
    payment_method: str
    amount_received: float | None
    change_given: float
    created_at: str
    items_count: int


@dataclass
class ReturnResult:
    """Resultado de registrar una devolución."""
    return_id: int
    sale_id: int
    total_refund: float
    cost_restored: float
    items_count: int


# =============================================================================
# Servicio
# =============================================================================
class SalesService:
    """Registro de ventas, devoluciones y anulaciones."""

    def __init__(
        self,
        db: Database,
        products: ProductService | None = None,
        inventory: InventoryService | None = None,
    ) -> None:
        self.db = db
        self.products = products or ProductService(db)
        self.inventory = inventory or InventoryService(db)

    # =========================================================================
    # Borradores (recuperación ante apagón)
    # =========================================================================
    def save_draft(
        self,
        user_id: int,
        cart: list[CartItem],
        payment_method: str,
        amount_received: str = "",
        cash_session_id: int | None = None,
    ) -> None:
        """Guarda un borrador del carrito sin afectar inventario."""
        if not cart:
            self.clear_draft(user_id)
            return

        payload = json.dumps([item.to_dict() for item in cart], ensure_ascii=False)
        self.db.execute(
            """INSERT INTO pending_sale_drafts(
                   user_id, cash_session_id, cart_json,
                   payment_method, amount_received, updated_at
               ) VALUES(?,?,?,?,?,?)
               ON CONFLICT(user_id) DO UPDATE SET
                   cash_session_id = excluded.cash_session_id,
                   cart_json = excluded.cart_json,
                   payment_method = excluded.payment_method,
                   amount_received = excluded.amount_received,
                   updated_at = excluded.updated_at""",
            (
                user_id, cash_session_id, payload,
                payment_method, amount_received, self._now(),
            ),
        )

    def get_draft(self, user_id: int) -> dict | None:
        row = self.db.one(
            "SELECT * FROM pending_sale_drafts WHERE user_id = ?", (user_id,)
        )
        if not row:
            return None
        try:
            cart_data = json.loads(row["cart_json"] or "[]")
            cart = [CartItem.from_dict(d) for d in cart_data]
        except (json.JSONDecodeError, KeyError, TypeError):
            log.warning("Borrador corrupto para user_id=%s, descartando", user_id)
            self.clear_draft(user_id)
            return None
        return {
            "cart": cart,
            "payment_method": row["payment_method"],
            "amount_received": row["amount_received"],
            "cash_session_id": row["cash_session_id"],
            "updated_at": row["updated_at"],
        }

    def clear_draft(self, user_id: int) -> None:
        self.db.execute(
            "DELETE FROM pending_sale_drafts WHERE user_id = ?", (user_id,)
        )

    # =========================================================================
    # Registrar venta (operación principal)
    # =========================================================================
    def register_sale(
        self,
        *,
        user_id: int,
        cash_session_id: int,
        cart: list[CartItem],
        payment_method: str,
        amount_received: float | None = None,
        validate_only: bool = False,
    ) -> SaleResult:
        """Registra una venta completa de forma atómica.

        Pasos:
          1. Validar carrito y caja
          2. Validar stock disponible
          3. Calcular totales y cambio
          4. INSERT sales + sale_items + addons + allocations
          5. Consumir FIFO por cada ítem
          6. Registrar movimientos de inventario
          7. Actualizar cost_total de la venta
          8. Limpiar borrador

        Si validate_only=True, hace todo hasta el paso 3 y lanza sin escribir.
        """
        if not cart:
            raise CartEmptyError("El carrito está vacío.")

        if not cash_session_id:
            raise NoCashSessionError("Debe abrir caja antes de registrar ventas.")

        # -------- 1. Validar sesión de caja abierta
        sess = self.db.one(
            "SELECT * FROM cash_sessions WHERE id = ? AND status = 'OPEN'",
            (cash_session_id,),
        )
        if not sess:
            raise NoCashSessionError(
                "La jornada de caja no está abierta o no existe."
            )

        # -------- 2. Validar stock disponible (antes de escribir nada)
        self._validate_cart_stock(cart)

        # -------- 3. Calcular totales
        total = sum(item.subtotal for item in cart)
        change = 0.0
        if payment_method == "Efectivo":
            if amount_received is None:
                raise SaleError("Debe indicar el efectivo recibido.")
            if amount_received < total:
                raise InsufficientPaymentError(total, amount_received)
            change = amount_received - total
        else:
            amount_received = None

        if validate_only:
            return SaleResult(
                sale_id=0, total=total, cost_total=0,
                payment_method=payment_method,
                amount_received=amount_received,
                change_given=change,
                created_at=self._now(),
                items_count=len(cart),
            )

        # -------- 4-7. Transacción atómica
        with self.db.transaction():
            sale_id = self._insert_sale(
                total=total, payment_method=payment_method,
                amount_received=amount_received, change_given=change,
                user_id=user_id, cash_session_id=cash_session_id,
            )

            cost_total = 0.0
            for item in cart:
                item_cost = self._process_cart_item(sale_id, item, user_id)
                cost_total += item_cost

            self.db.conn.execute(
                "UPDATE sales SET cost_total = ? WHERE id = ?",
                (cost_total, sale_id),
            )

        # -------- 8. Limpiar borrador tras el COMMIT exitoso
        self.clear_draft(user_id)

        log.info(
            "Venta #%s registrada: total=%.2f costo=%.2f items=%s cajero=%s",
            sale_id, total, cost_total, len(cart), user_id,
        )

        return SaleResult(
            sale_id=sale_id,
            total=total,
            cost_total=cost_total,
            payment_method=payment_method,
            amount_received=amount_received,
            change_given=change,
            created_at=self._now(),
            items_count=len(cart),
        )

    # =========================================================================
    # Anular venta completa
    # =========================================================================
    def void_sale(
        self,
        *,
        sale_id: int,
        user_id: int,
        reason: str,
    ) -> None:
        """Anula una venta completa restaurando inventario al costo original."""
        sale = self.db.one("SELECT * FROM sales WHERE id = ?", (sale_id,))
        if not sale:
            raise SaleError(f"Venta {sale_id} no existe.")
        if sale["status"] == "VOIDED":
            raise SaleAlreadyVoidedError(f"La venta #{sale_id} ya fue anulada.")

        # Verificar que no existan devoluciones previas
        returns_count = int(
            self.db.scalar(
                "SELECT COUNT(*) FROM sale_returns WHERE sale_id = ?",
                (sale_id,), default=0,
            ) or 0
        )
        if returns_count > 0:
            raise SaleHasReturnsError(
                "La venta tiene devoluciones parciales. "
                "Devuelva los artículos restantes en lugar de anularla completa."
            )

        with self.db.transaction():
            # Restaurar inventario por cada ítem
            items = self.db.all(
                """SELECT si.*, p.product_type
                   FROM sale_items si
                   JOIN products p ON p.id = si.product_id
                   WHERE si.sale_id = ?""",
                (sale_id,),
            )

            for item in items:
                self._restore_sale_item(item, reason, user_id)

                # Adicionales con componente inventariable
                addons = self.db.all(
                    """SELECT * FROM sale_item_addons
                       WHERE sale_item_id = ?
                         AND component_product_id IS NOT NULL
                         AND component_qty > 0""",
                    (item["id"],),
                )
                for addon in addons:
                    comp_qty = float(addon["component_qty"] or 0)
                    comp_cost = float(addon["component_cost"] or 0)
                    if comp_qty <= 0:
                        continue
                    unit_cost = comp_cost / comp_qty
                    self.inventory.restore_stock(
                        product_id=int(addon["component_product_id"]),
                        qty=comp_qty,
                        unit_cost=unit_cost,
                        movement_type=MovementType.VOID_ADDON,
                        reference_type="SALE",
                        reference_id=sale_id,
                        note=f"{reason} · {addon['addon_name']}",
                        created_by=user_id,
                    )

            self.db.conn.execute(
                """UPDATE sales
                   SET status='VOIDED', voided_by=?, voided_at=?, void_reason=?
                   WHERE id = ?""",
                (user_id, self._now(), reason, sale_id),
            )

        log.info("Venta #%s anulada por user=%s: %s", sale_id, user_id, reason)

    # =========================================================================
    # Registrar devolución parcial
    # =========================================================================
    def register_return(
        self,
        *,
        sale_id: int,
        sale_item_id: int,
        qty_to_return: float,
        reason: str,
        user_id: int,
        cash_session_id: int | None = None,
        refund_method: str | None = None,
    ) -> ReturnResult:
        """Registra una devolución parcial de un ítem de venta."""
        if qty_to_return <= 0:
            raise SaleError("La cantidad a devolver debe ser mayor que cero.")

        sale = self.db.one("SELECT * FROM sales WHERE id = ?", (sale_id,))
        if not sale:
            raise SaleError(f"Venta {sale_id} no existe.")
        if sale["status"] != "COMPLETED":
            raise SaleError("Solo se pueden devolver artículos de ventas completadas.")

        item = self.db.one(
            """SELECT si.*, p.product_type, p.name AS product_name
               FROM sale_items si
               JOIN products p ON p.id = si.product_id
               WHERE si.id = ? AND si.sale_id = ?""",
            (sale_item_id, sale_id),
        )
        if not item:
            raise SaleError(f"Ítem {sale_item_id} no pertenece a la venta {sale_id}.")

        sold_qty = float(item["sale_qty"] if item["sale_qty"] is not None else item["qty"])
        already_returned = float(
            self.db.scalar(
                """SELECT COALESCE(SUM(sale_qty_returned), 0)
                   FROM sale_return_items WHERE sale_item_id = ?""",
                (sale_item_id,), default=0.0,
            ) or 0.0
        )
        available = sold_qty - already_returned
        if qty_to_return > available + 1e-9:
            raise ReturnExceedsSaleError(
                f"Solo quedan {available:.2f} unidades disponibles para devolver."
            )

        ratio = qty_to_return / sold_qty if sold_qty else 0.0
        inventory_qty = float(item["qty"] or 0) * ratio
        display_price = float(
            item["display_unit_price"] if item["display_unit_price"] is not None
            else item["unit_price"]
        )
        refund = qty_to_return * display_price

        # Costo FIFO original prorrateado
        main_cost_total = float(
            self.db.scalar(
                """SELECT COALESCE(SUM(qty * unit_cost), 0)
                   FROM sale_cost_allocations WHERE sale_item_id = ?""",
                (sale_item_id,), default=0.0,
            ) or 0.0
        )
        main_cost_returned = main_cost_total * ratio

        # Método de reembolso por defecto: el mismo de la venta
        if refund_method is None:
            refund_method = sale["payment_method"] or "Efectivo"

        with self.db.transaction():
            cur = self.db.conn.execute(
                """INSERT INTO sale_returns(
                       sale_id, cash_session_id, refund_method,
                       total_refund, reason, created_by, created_at
                   ) VALUES(?,?,?,?,?,?,?)""",
                (
                    sale_id, cash_session_id, refund_method,
                    refund, reason, user_id, self._now(),
                ),
            )
            return_id = int(cur.lastrowid)

            self.db.conn.execute(
                """INSERT INTO sale_return_items(
                       return_id, sale_item_id, product_id,
                       sale_qty_returned, inventory_qty_returned,
                       refund_amount, cost_amount
                   ) VALUES(?,?,?,?,?,?,?)""",
                (
                    return_id, sale_item_id, int(item["product_id"]),
                    qty_to_return, inventory_qty, refund, main_cost_returned,
                ),
            )

            # Restaurar producto principal
            if item["product_type"] != "SERVICE" and inventory_qty > 0:
                unit_cost = main_cost_returned / inventory_qty if inventory_qty else 0.0
                self.inventory.restore_stock(
                    product_id=int(item["product_id"]),
                    qty=inventory_qty,
                    unit_cost=unit_cost,
                    movement_type=MovementType.RETURN,
                    reference_type="RETURN",
                    reference_id=return_id,
                    note=reason,
                    created_by=user_id,
                )

            # Restaurar componentes de adicionales proporcionalmente
            addons = self.db.all(
                """SELECT * FROM sale_item_addons
                   WHERE sale_item_id = ?
                     AND component_product_id IS NOT NULL
                     AND component_qty > 0""",
                (sale_item_id,),
            )
            for addon in addons:
                comp_qty = float(addon["component_qty"] or 0) * ratio
                comp_cost = float(addon["component_cost"] or 0) * ratio
                if comp_qty <= 0:
                    continue
                unit_cost = comp_cost / comp_qty
                self.inventory.restore_stock(
                    product_id=int(addon["component_product_id"]),
                    qty=comp_qty,
                    unit_cost=unit_cost,
                    movement_type=MovementType.RETURN_ADDON,
                    reference_type="RETURN",
                    reference_id=return_id,
                    note=f"{reason} · {addon['addon_name']}",
                    created_by=user_id,
                )

        log.info(
            "Devolución #%s: venta=%s item=%s qty=%.2f reembolso=%.2f",
            return_id, sale_id, sale_item_id, qty_to_return, refund,
        )

        return ReturnResult(
            return_id=return_id,
            sale_id=sale_id,
            total_refund=refund,
            cost_restored=main_cost_returned,
            items_count=1,
        )

    # =========================================================================
    # Consultas
    # =========================================================================
    def get_sale(self, sale_id: int) -> dict | None:
        row = self.db.one(
            """SELECT s.*, u.full_name AS cashier_name
               FROM sales s
               LEFT JOIN users u ON u.id = s.created_by
               WHERE s.id = ?""",
            (sale_id,),
        )
        return dict(row) if row else None

    def get_sale_items(self, sale_id: int) -> list[dict]:
        return [
            dict(r) for r in self.db.all(
                """SELECT si.*, p.sku, p.name, p.unit
                   FROM sale_items si
                   JOIN products p ON p.id = si.product_id
                   WHERE si.sale_id = ?
                   ORDER BY si.id""",
                (sale_id,),
            )
        ]

    def get_sale_item_addons(self, sale_item_id: int) -> list[dict]:
        return [
            dict(r) for r in self.db.all(
                "SELECT * FROM sale_item_addons WHERE sale_item_id = ? ORDER BY id",
                (sale_item_id,),
            )
        ]

    # =========================================================================
    # Helpers internos
    # =========================================================================
    def _validate_cart_stock(self, cart: list[CartItem]) -> None:
        """Valida stock disponible para todos los ítems y adicionales."""
        # Agrupamos por producto para no validar dos veces el mismo
        needed: dict[int, float] = {}
        for item in cart:
            if item.product_type == "SERVICE":
                continue
            needed[item.product_id] = (
                needed.get(item.product_id, 0.0) + item.inventory_qty
            )

        if not needed:
            return

        stocks = self.inventory.current_stock_bulk(needed.keys())
        for pid, qty_needed in needed.items():
            available = stocks.get(pid, 0.0)
            if qty_needed > available + 1e-9:
                product = self.products.get(pid) or {}
                name = product.get("name", f"Producto {pid}")
                raise InsufficientStockError(pid, available, qty_needed)

    def _insert_sale(
        self,
        *,
        total: float,
        payment_method: str,
        amount_received: float | None,
        change_given: float,
        user_id: int,
        cash_session_id: int,
    ) -> int:
        cur = self.db.conn.execute(
            """INSERT INTO sales(
                   total, cost_total, payment_method, amount_received,
                   change_given, status, created_by, cash_session_id, created_at
               ) VALUES(?,?,?,?,?,?,?,?,?)""",
            (
                total, 0.0, payment_method, amount_received,
                change_given, "COMPLETED", user_id, cash_session_id, self._now(),
            ),
        )
        return int(cur.lastrowid)

    def _process_cart_item(
        self, sale_id: int, item: CartItem, user_id: int
    ) -> float:
        """Procesa un ítem: consume FIFO, inserta sale_item y adicionales.

        Devuelve el costo total del ítem (producto + adicionales).
        """
        # --- Consumir producto principal
        main_cost = 0.0
        allocations: list = []
        if item.product_type != "SERVICE" and item.inventory_qty > 0:
            consumption = self.inventory.consume_fifo(
                product_id=item.product_id,
                qty=item.inventory_qty,
                movement_type=MovementType.SALE,
                reference_type="SALE",
                reference_id=sale_id,
                note="Salida por venta",
                created_by=user_id,
            )
            main_cost = consumption.total_cost
            allocations = consumption.allocations

        # --- Precio base por unidad base (para auditoría)
        base_price = (
            item.unit_price / item.presentation_factor
            if item.presentation_factor else item.unit_price
        )

        # --- Insertar sale_item
        cur = self.db.conn.execute(
            """INSERT INTO sale_items(
                   sale_id, product_id, qty, sale_qty, unit_price,
                   display_unit_price, presentation_name, presentation_factor,
                   cost_total
               ) VALUES(?,?,?,?,?,?,?,?,?)""",
            (
                sale_id, item.product_id, item.inventory_qty, item.sale_qty,
                base_price, item.display_unit_price,
                item.presentation_name, item.presentation_factor,
                main_cost,
            ),
        )
        sale_item_id = int(cur.lastrowid)

        # --- Registrar asignaciones FIFO (auditoría)
        for alloc in allocations:
            self.db.conn.execute(
                """INSERT INTO sale_cost_allocations(
                       sale_item_id, lot_id, qty, unit_cost
                   ) VALUES(?,?,?,?)""",
                (sale_item_id, alloc.lot_id, alloc.qty, alloc.unit_cost),
            )

        # --- Procesar adicionales
        addon_cost = 0.0
        for addon in item.addons:
            comp_cost = 0.0
            comp_id = addon.component_product_id
            comp_need = float(addon.component_qty or 0) * item.sale_qty

            if comp_id and comp_need > 0:
                consumption = self.inventory.consume_fifo(
                    product_id=comp_id,
                    qty=comp_need,
                    movement_type=MovementType.SALE_ADDON,
                    reference_type="SALE",
                    reference_id=sale_id,
                    note=f"Adicional: {addon.name}",
                    created_by=user_id,
                )
                comp_cost = consumption.total_cost

            self.db.conn.execute(
                """INSERT INTO sale_item_addons(
                       sale_item_id, addon_name, extra_price,
                       component_product_id, component_qty, component_cost
                   ) VALUES(?,?,?,?,?,?)""",
                (
                    sale_item_id, addon.name, addon.extra_price,
                    comp_id, comp_need, comp_cost,
                ),
            )
            addon_cost += comp_cost

        item_total_cost = main_cost + addon_cost
        self.db.conn.execute(
            "UPDATE sale_items SET cost_total = ? WHERE id = ?",
            (item_total_cost, sale_item_id),
        )
        return item_total_cost

    def _restore_sale_item(
        self, item, reason: str, user_id: int
    ) -> None:
        """Restaura el producto principal de un sale_item al anular venta."""
        if item["product_type"] == "SERVICE":
            return
        inventory_qty = float(item["qty"] or 0)
        if inventory_qty <= 0:
            return

        # Costo original reconstruido desde las asignaciones FIFO
        allocations = self.db.all(
            "SELECT * FROM sale_cost_allocations WHERE sale_item_id = ?",
            (int(item["id"]),),
        )
        if allocations:
            # Reinsertar a los lotes originales
            for alloc in allocations:
                self.db.conn.execute(
                    """UPDATE inventory_lots
                       SET qty_remaining = qty_remaining + ?
                       WHERE id = ?""",
                    (float(alloc["qty"]), int(alloc["lot_id"])),
                )
            total_cost = sum(
                float(a["qty"]) * float(a["unit_cost"]) for a in allocations
            )
            unit_cost = total_cost / inventory_qty if inventory_qty else 0.0
            self.inventory._log_movement(
                product_id=int(item["product_id"]),
                movement_type=MovementType.VOID,
                qty=inventory_qty,
                unit_cost=unit_cost,
                reference_type="SALE",
                reference_id=int(item["sale_id"]),
                note=reason,
                created_by=user_id,
            )
        else:
            # Sin asignaciones: usar costo registrado del ítem
            total_cost = float(item["cost_total"] or 0)
            unit_cost = total_cost / inventory_qty if inventory_qty else 0.0
            self.inventory.restore_stock(
                product_id=int(item["product_id"]),
                qty=inventory_qty,
                unit_cost=unit_cost,
                movement_type=MovementType.VOID,
                reference_type="SALE",
                reference_id=int(item["sale_id"]),
                note=reason,
                created_by=user_id,
            )

    @staticmethod
    def _now() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")