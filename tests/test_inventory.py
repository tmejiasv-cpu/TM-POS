"""Tests del InventoryService: FIFO, lotes, validaciones."""
from __future__ import annotations

import pytest

from vidpos.services.inventory import (
    InsufficientStockError,
    InventoryError,
    InventoryService,
    MovementType,
    ProductNotFoundError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _create_product(db, admin_id, *, sku="P001", name="Test",
                    product_type="PRODUCT", price=10.0) -> int:
    cur = db.execute(
        """INSERT INTO products(
               sku, name, sale_price, product_type, created_by, created_at
           ) VALUES(?,?,?,?,?,?)""",
        (sku, name, price, product_type, admin_id, "2026-01-01 00:00:00"),
    )
    return int(cur.lastrowid)


# ---------------------------------------------------------------------------
# Stock inicial
# ---------------------------------------------------------------------------
def test_producto_nuevo_sin_stock(db, admin_id):
    pid = _create_product(db, admin_id)
    svc = InventoryService(db)
    assert svc.current_stock(pid) == 0.0
    assert svc.inventory_value(pid) == 0.0


# ---------------------------------------------------------------------------
# add_stock
# ---------------------------------------------------------------------------
def test_add_stock_crea_lote(db, admin_id):
    pid = _create_product(db, admin_id)
    svc = InventoryService(db)

    with db.transaction():
        lot_id = svc.add_stock(pid, qty=10, unit_cost=2.50, created_by=admin_id)

    assert lot_id > 0
    assert svc.current_stock(pid) == 10.0
    assert svc.inventory_value(pid) == 25.0


def test_add_stock_rechaza_cantidad_negativa(db, admin_id):
    pid = _create_product(db, admin_id)
    svc = InventoryService(db)
    with pytest.raises(InventoryError):
        with db.transaction():
            svc.add_stock(pid, qty=-5, unit_cost=1.0, created_by=admin_id)


def test_add_stock_rechaza_servicio(db, admin_id):
    pid = _create_product(db, admin_id, product_type="SERVICE")
    svc = InventoryService(db)
    with pytest.raises(InventoryError, match="servicios"):
        with db.transaction():
            svc.add_stock(pid, qty=1, unit_cost=1.0, created_by=admin_id)


# ---------------------------------------------------------------------------
# consume_fifo — el test más importante
# ---------------------------------------------------------------------------
def test_fifo_consume_lote_mas_antiguo_primero(db, admin_id):
    """Escenario clásico: dos lotes con costos distintos, vender parcial."""
    pid = _create_product(db, admin_id)
    svc = InventoryService(db)

    with db.transaction():
        svc.add_stock(pid, qty=10, unit_cost=2.00, created_by=admin_id)

    # Pausa mínima para asegurar distinto created_at
    import time; time.sleep(0.01)

    with db.transaction():
        svc.add_stock(pid, qty=10, unit_cost=3.00, created_by=admin_id)

    # Consumimos 15 unidades: deben salir 10 del primero ($2) y 5 del segundo ($3)
    with db.transaction():
        result = svc.consume_fifo(pid, qty=15, created_by=admin_id)

    assert result.qty == 15
    assert result.total_cost == 10 * 2.00 + 5 * 3.00   # = 35.0
    assert len(result.allocations) == 2
    assert result.allocations[0].qty == 10
    assert result.allocations[0].unit_cost == 2.00
    assert result.allocations[1].qty == 5
    assert result.allocations[1].unit_cost == 3.00

    # Quedan 5 unidades del segundo lote a costo 3
    assert svc.current_stock(pid) == 5.0
    assert svc.inventory_value(pid) == 15.0


def test_fifo_agota_lote_exacto(db, admin_id):
    pid = _create_product(db, admin_id)
    svc = InventoryService(db)

    with db.transaction():
        svc.add_stock(pid, qty=5, unit_cost=1.00, created_by=admin_id)

    with db.transaction():
        result = svc.consume_fifo(pid, qty=5, created_by=admin_id)

    assert result.total_cost == 5.0
    assert svc.current_stock(pid) == 0.0


def test_fifo_falla_si_no_hay_suficiente(db, admin_id):
    pid = _create_product(db, admin_id)
    svc = InventoryService(db)

    with db.transaction():
        svc.add_stock(pid, qty=3, unit_cost=1.00, created_by=admin_id)

    with pytest.raises(InsufficientStockError) as exc:
        with db.transaction():
            svc.consume_fifo(pid, qty=5, created_by=admin_id)

    assert exc.value.available == 3.0
    assert exc.value.requested == 5.0

    # El stock no debe haber cambiado (rollback de la transacción)
    assert svc.current_stock(pid) == 3.0


def test_fifo_rollback_no_deja_lotes_parcialmente_consumidos(db, admin_id):
    """Si falla un consume_fifo a mitad, la transacción debe revertir todo."""
    pid = _create_product(db, admin_id)
    svc = InventoryService(db)

    with db.transaction():
        svc.add_stock(pid, qty=10, unit_cost=2.00, created_by=admin_id)

    # Intentar consumir 20 (falla) → el lote NO debe quedar afectado
    with pytest.raises(InsufficientStockError):
        with db.transaction():
            svc.consume_fifo(pid, qty=20, created_by=admin_id)

    assert svc.current_stock(pid) == 10.0
    assert svc.inventory_value(pid) == 20.0


# ---------------------------------------------------------------------------
# restore_stock
# ---------------------------------------------------------------------------
def test_restore_stock_crea_lote_nuevo(db, admin_id):
    pid = _create_product(db, admin_id)
    svc = InventoryService(db)

    with db.transaction():
        svc.add_stock(pid, qty=10, unit_cost=2.00, created_by=admin_id)

    with db.transaction():
        svc.consume_fifo(pid, qty=10, created_by=admin_id)

    assert svc.current_stock(pid) == 0.0

    with db.transaction():
        svc.restore_stock(pid, qty=3, unit_cost=2.00, created_by=admin_id)

    assert svc.current_stock(pid) == 3.0


# ---------------------------------------------------------------------------
# Movimientos (auditoría)
# ---------------------------------------------------------------------------
def test_cada_operacion_queda_auditada(db, admin_id):
    pid = _create_product(db, admin_id)
    svc = InventoryService(db)

    with db.transaction():
        svc.add_stock(pid, qty=10, unit_cost=2.00,
                      movement_type=MovementType.PURCHASE,
                      created_by=admin_id)

    with db.transaction():
        svc.consume_fifo(pid, qty=3,
                         movement_type=MovementType.SALE,
                         created_by=admin_id)

    movements = svc.get_movements(pid)
    assert len(movements) == 2
    # El más reciente primero
    assert movements[0]["movement_type"] == MovementType.SALE
    assert movements[0]["qty"] == -3
    assert movements[1]["movement_type"] == MovementType.PURCHASE
    assert movements[1]["qty"] == 10


# ---------------------------------------------------------------------------
# bulk queries
# ---------------------------------------------------------------------------
def test_current_stock_bulk(db, admin_id):
    pid1 = _create_product(db, admin_id, sku="A1", name="A")
    pid2 = _create_product(db, admin_id, sku="A2", name="B")
    pid3 = _create_product(db, admin_id, sku="A3", name="C")

    svc = InventoryService(db)
    with db.transaction():
        svc.add_stock(pid1, qty=5, unit_cost=1, created_by=admin_id)
        svc.add_stock(pid2, qty=7, unit_cost=1, created_by=admin_id)

    stocks = svc.current_stock_bulk([pid1, pid2, pid3])
    assert stocks[pid1] == 5.0
    assert stocks[pid2] == 7.0
    assert stocks[pid3] == 0.0