"""Servicio de inventario: productos, lotes y movimientos FIFO.

Este módulo es el corazón del control de existencias de vidPOS.
Toda modificación de inventario pasa por aquí para garantizar:

  - Consistencia transaccional (o se aplica todo, o nada).
  - Costo real por lotes (FIFO/PEPS).
  - Auditoría completa en inventory_movements.
  - Validaciones de stock antes de consumir.

Reglas de negocio:
  - Los productos tipo 'SERVICE' no manejan inventario.
  - Un producto puede tener varios lotes, cada uno con su costo.
  - Al vender se consume primero el lote más antiguo (created_at, id).
  - Las devoluciones reinsertan inventario como un lote nuevo.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from vidpos.core.database import Database

log = logging.getLogger(__name__)


# =============================================================================
# Excepciones específicas del dominio
# =============================================================================
class InventoryError(Exception):
    """Error genérico de inventario."""


class InsufficientStockError(InventoryError):
    """No hay existencias suficientes para completar la operación."""

    def __init__(self, product_id: int, available: float, requested: float):
        self.product_id = product_id
        self.available = available
        self.requested = requested
        super().__init__(
            f"Inventario insuficiente para producto {product_id}: "
            f"disponible {available:.2f}, solicitado {requested:.2f}"
        )


class ProductNotFoundError(InventoryError):
    """El producto no existe o está inactivo."""


# =============================================================================
# Tipos de movimiento de inventario (constantes)
# =============================================================================
class MovementType:
    PURCHASE = "COMPRA"
    SALE = "VENTA"
    SALE_ADDON = "VENTA_ADICIONAL"
    RETURN = "DEVOLUCION_CLIENTE"
    RETURN_ADDON = "DEVOLUCION_ADICIONAL"
    VOID = "ANULACION_VENTA"
    VOID_ADDON = "ANULACION_ADICIONAL"
    MANUAL_POSITIVE = "AJUSTE_POSITIVO"
    MANUAL_NEGATIVE = "AJUSTE_NEGATIVO"
    COURTESY = "CORTESIA"
    LOSS = "MERMA"
    INTERNAL_USE = "USO_INTERNO"


# =============================================================================
# Resultado de consumo FIFO
# =============================================================================
@dataclass
class FIFOAllocation:
    """Una porción consumida de un lote específico."""
    lot_id: int
    qty: float
    unit_cost: float

    @property
    def subtotal(self) -> float:
        return self.qty * self.unit_cost


@dataclass
class FIFOConsumption:
    """Resultado completo de consumir stock por FIFO."""
    product_id: int
    qty: float
    total_cost: float
    allocations: list[FIFOAllocation]

    @property
    def average_cost(self) -> float:
        return self.total_cost / self.qty if self.qty else 0.0


# =============================================================================
# Servicio
# =============================================================================
class InventoryService:
    """Servicio de inventario con FIFO real por lotes."""

    def __init__(self, db: Database) -> None:
        self.db = db

    # =========================================================================
    # Consultas
    # =========================================================================
    def current_stock(self, product_id: int) -> float:
        """Existencia actual sumando todos los lotes con saldo."""
        row = self.db.one(
            """SELECT COALESCE(SUM(qty_remaining), 0) AS stock
               FROM inventory_lots
               WHERE product_id = ?""",
            (product_id,),
        )
        return float(row["stock"]) if row else 0.0

    def current_stock_bulk(self, product_ids: Iterable[int]) -> dict[int, float]:
        """Existencia actual de varios productos de una sola consulta.

        Útil para cargar catálogos sin N+1 queries.
        """
        ids = list(product_ids)
        if not ids:
            return {}
        placeholders = ",".join("?" * len(ids))
        rows = self.db.all(
            f"""SELECT product_id, COALESCE(SUM(qty_remaining), 0) AS stock
                FROM inventory_lots
                WHERE product_id IN ({placeholders})
                GROUP BY product_id""",
            ids,
        )
        result = {pid: 0.0 for pid in ids}
        for r in rows:
            result[int(r["product_id"])] = float(r["stock"])
        return result

    def inventory_value(self, product_id: int | None = None) -> float:
        """Valor del inventario a costo FIFO.

        Si product_id es None, devuelve el valor total de la tienda.
        """
        if product_id is None:
            row = self.db.one(
                """SELECT COALESCE(SUM(qty_remaining * unit_cost), 0) AS value
                   FROM inventory_lots
                   WHERE qty_remaining > 0"""
            )
        else:
            row = self.db.one(
                """SELECT COALESCE(SUM(qty_remaining * unit_cost), 0) AS value
                   FROM inventory_lots
                   WHERE product_id = ? AND qty_remaining > 0""",
                (product_id,),
            )
        return float(row["value"]) if row else 0.0

    def get_product(self, product_id: int) -> dict | None:
        """Devuelve el producto o None si no existe/está inactivo."""
        row = self.db.one(
            "SELECT * FROM products WHERE id = ? AND active = 1",
            (product_id,),
        )
        return dict(row) if row else None

    # =========================================================================
    # Entradas de inventario (compras y ajustes positivos)
    # =========================================================================
    def add_stock(
        self,
        product_id: int,
        qty: float,
        unit_cost: float,
        *,
        movement_type: str = MovementType.MANUAL_POSITIVE,
        reference_type: str = "",
        reference_id: int | None = None,
        note: str = "",
        created_by: int | None = None,
        purchase_item_id: int | None = None,
    ) -> int:
        """Registra entrada de stock creando un lote nuevo.

        Devuelve el id del lote creado.
        Requiere que la operación esté dentro de una transacción abierta
        si el llamador ya inició una (por ejemplo, al registrar una compra).
        """
        if qty <= 0:
            raise InventoryError(f"La cantidad debe ser positiva, recibido: {qty}")
        if unit_cost < 0:
            raise InventoryError(f"El costo no puede ser negativo: {unit_cost}")

        product = self.db.one(
            "SELECT product_type, active FROM products WHERE id = ?",
            (product_id,),
        )
        if not product or not product["active"]:
            raise ProductNotFoundError(f"Producto {product_id} no existe o está inactivo")
        if product["product_type"] == "SERVICE":
            raise InventoryError("Los servicios no manejan inventario")

        cur = self.db.conn.execute(
            """INSERT INTO inventory_lots(
                   product_id, purchase_item_id, qty_received, qty_remaining,
                   unit_cost, created_at
               ) VALUES(?,?,?,?,?,?)""",
            (product_id, purchase_item_id, qty, qty, unit_cost, self._now()),
        )
        lot_id = int(cur.lastrowid)

        self._log_movement(
            product_id=product_id,
            movement_type=movement_type,
            qty=qty,
            unit_cost=unit_cost,
            reference_type=reference_type,
            reference_id=reference_id,
            note=note,
            created_by=created_by,
        )

        log.info(
            "Entrada stock: producto=%s qty=%s costo=%s lote=%s tipo=%s",
            product_id, qty, unit_cost, lot_id, movement_type,
        )
        return lot_id

    # =========================================================================
    # Consumo FIFO (ventas, mermas, uso interno, etc.)
    # =========================================================================
    def consume_fifo(
        self,
        product_id: int,
        qty: float,
        *,
        movement_type: str = MovementType.SALE,
        reference_type: str = "",
        reference_id: int | None = None,
        note: str = "",
        created_by: int | None = None,
    ) -> FIFOConsumption:
        """Consume stock por FIFO (lote más antiguo primero).

        Devuelve las asignaciones por lote y el costo total real.
        Lanza InsufficientStockError si no hay suficiente.
        """
        if qty <= 0:
            raise InventoryError(f"La cantidad debe ser positiva, recibido: {qty}")

        product = self.db.one(
            "SELECT product_type, active FROM products WHERE id = ?",
            (product_id,),
        )
        if not product or not product["active"]:
            raise ProductNotFoundError(f"Producto {product_id} no existe o está inactivo")
        if product["product_type"] == "SERVICE":
            raise InventoryError("Los servicios no consumen inventario")

        lots = self.db.all(
            """SELECT id, qty_remaining, unit_cost
               FROM inventory_lots
               WHERE product_id = ? AND qty_remaining > 0
               ORDER BY created_at ASC, id ASC""",
            (product_id,),
        )

        available = sum(float(l["qty_remaining"]) for l in lots)
        if available + 1e-9 < qty:
            raise InsufficientStockError(product_id, available, qty)

        remaining = float(qty)
        total_cost = 0.0
        allocations: list[FIFOAllocation] = []

        for lot in lots:
            if remaining <= 1e-9:
                break
            lot_qty = float(lot["qty_remaining"])
            take = min(lot_qty, remaining)
            unit_cost = float(lot["unit_cost"])
            cost = take * unit_cost

            self.db.conn.execute(
                "UPDATE inventory_lots SET qty_remaining = qty_remaining - ? WHERE id = ?",
                (take, lot["id"]),
            )

            allocations.append(FIFOAllocation(
                lot_id=int(lot["id"]),
                qty=take,
                unit_cost=unit_cost,
            ))
            total_cost += cost
            remaining -= take

        self._log_movement(
            product_id=product_id,
            movement_type=movement_type,
            qty=-qty,
            unit_cost=total_cost / qty if qty else 0.0,
            reference_type=reference_type,
            reference_id=reference_id,
            note=note,
            created_by=created_by,
        )

        log.info(
            "Salida stock FIFO: producto=%s qty=%s costo_total=%.4f lotes=%s",
            product_id, qty, total_cost, len(allocations),
        )

        return FIFOConsumption(
            product_id=product_id,
            qty=qty,
            total_cost=total_cost,
            allocations=allocations,
        )

    # =========================================================================
    # Restaurar stock (devoluciones, anulaciones)
    # =========================================================================
    def restore_stock(
        self,
        product_id: int,
        qty: float,
        unit_cost: float,
        *,
        movement_type: str = MovementType.RETURN,
        reference_type: str = "",
        reference_id: int | None = None,
        note: str = "",
        created_by: int | None = None,
    ) -> int:
        """Restaura stock creando un lote nuevo al costo indicado.

        Se usa para devoluciones y anulaciones. El lote nuevo aparece
        con la fecha actual, por lo que irá al final de la cola FIFO.
        """
        if qty <= 0:
            raise InventoryError(f"La cantidad debe ser positiva, recibido: {qty}")
        if unit_cost < 0:
            raise InventoryError(f"El costo no puede ser negativo: {unit_cost}")

        product = self.db.one(
            "SELECT product_type FROM products WHERE id = ?",
            (product_id,),
        )
        if not product:
            raise ProductNotFoundError(f"Producto {product_id} no existe")
        if product["product_type"] == "SERVICE":
            raise InventoryError("Los servicios no manejan inventario")

        cur = self.db.conn.execute(
            """INSERT INTO inventory_lots(
                   product_id, purchase_item_id, qty_received, qty_remaining,
                   unit_cost, created_at
               ) VALUES(?, NULL, ?, ?, ?, ?)""",
            (product_id, qty, qty, unit_cost, self._now()),
        )
        lot_id = int(cur.lastrowid)

        self._log_movement(
            product_id=product_id,
            movement_type=movement_type,
            qty=qty,
            unit_cost=unit_cost,
            reference_type=reference_type,
            reference_id=reference_id,
            note=note,
            created_by=created_by,
        )

        log.info(
            "Restauración stock: producto=%s qty=%s costo=%s lote=%s tipo=%s",
            product_id, qty, unit_cost, lot_id, movement_type,
        )
        return lot_id

    # =========================================================================
    # Historial de movimientos
    # =========================================================================
    def get_movements(
        self,
        product_id: int,
        limit: int = 500,
    ) -> list[dict]:
        """Historial completo de movimientos de un producto."""
        rows = self.db.all(
            """SELECT m.*, u.full_name AS user_name
               FROM inventory_movements m
               LEFT JOIN users u ON u.id = m.created_by
               WHERE m.product_id = ?
               ORDER BY m.id DESC
               LIMIT ?""",
            (product_id, limit),
        )
        return [dict(r) for r in rows]

    # =========================================================================
    # Helpers internos
    # =========================================================================
    def _log_movement(
        self,
        *,
        product_id: int,
        movement_type: str,
        qty: float,
        unit_cost: float | None,
        reference_type: str,
        reference_id: int | None,
        note: str,
        created_by: int | None,
    ) -> int:
        """Inserta una fila en inventory_movements y devuelve su id."""
        cur = self.db.conn.execute(
            """INSERT INTO inventory_movements(
                   product_id, movement_type, qty, unit_cost,
                   reference_type, reference_id, note, created_by, created_at
               ) VALUES(?,?,?,?,?,?,?,?,?)""",
            (
                product_id, movement_type, qty, unit_cost,
                reference_type, reference_id, note,
                created_by, self._now(),
            ),
        )
        return int(cur.lastrowid)

    @staticmethod
    def _now() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")