"""Tests del CashService."""
from __future__ import annotations

import pytest

from vidpos.services.cash import (
    CashAlreadyClosedError,
    CashAlreadyOpenError,
    CashError,
    CashService,
    PendingExpensesError,
)
from vidpos.services.inventory import InventoryService
from vidpos.services.products import ProductService
from vidpos.services.sales import CartItem, SalesService


# =============================================================================
# Fixtures locales
# =============================================================================
@pytest.fixture
def services(db):
    inv = InventoryService(db)
    prod = ProductService(db)
    sales = SalesService(db, products=prod, inventory=inv)
    cash = CashService(db)
    return {"inv": inv, "prod": prod, "sales": sales, "cash": cash}


def _make_cart_item(product, *, sale_qty=1.0, factor=1.0,
                    inventory_qty=None, price=None) -> CartItem:
    if inventory_qty is None:
        inventory_qty = sale_qty * factor
    if price is None:
        price = float(product["sale_price"])
    return CartItem(
        product_id=int(product["id"]),
        sku=product["sku"],
        name=product["name"],
        product_type=product["product_type"],
        presentation_name=product["unit"] or "Unidad",
        presentation_factor=factor,
        sale_qty=sale_qty,
        inventory_qty=inventory_qty,
        unit_price=price,
    )


# =============================================================================
# Apertura
# =============================================================================
def test_abrir_caja_basica(services, admin_id):
    cash = services["cash"]
    sid = cash.open_session(user_id=admin_id, opening_amount=100.0)
    assert sid > 0

    session = cash.get_open_session(admin_id)
    assert session is not None
    assert session.id == sid
    assert session.opening_amount == 100.0
    assert session.status == "OPEN"


def test_no_abrir_dos_cajas_al_mismo_tiempo(services, admin_id):
    cash = services["cash"]
    cash.open_session(user_id=admin_id, opening_amount=50)
    with pytest.raises(CashAlreadyOpenError):
        cash.open_session(user_id=admin_id, opening_amount=80)


def test_no_abrir_con_fondo_negativo(services, admin_id):
    cash = services["cash"]
    with pytest.raises(CashError):
        cash.open_session(user_id=admin_id, opening_amount=-10)


# =============================================================================
# Efectivo esperado
# =============================================================================
def test_efectivo_esperado_solo_apertura(services, admin_id):
    cash = services["cash"]
    sid = cash.open_session(user_id=admin_id, opening_amount=100)

    summary = cash.get_summary(sid)
    assert summary.opening_amount == 100
    assert summary.sales_cash == 0
    assert summary.expected_cash == 100


def test_efectivo_esperado_con_ventas_efectivo(services, db, admin_id):
    inv, prod, sales, cash = (
        services["inv"], services["prod"], services["sales"], services["cash"]
    )
    sid = cash.open_session(user_id=admin_id, opening_amount=100)

    pid = prod.create(name="A", sale_price=10, created_by=admin_id)
    with db.transaction():
        inv.add_stock(pid, qty=10, unit_cost=4, created_by=admin_id)

    item = _make_cart_item(prod.get(pid), sale_qty=2, inventory_qty=2)
    sales.register_sale(
        user_id=admin_id, cash_session_id=sid,
        cart=[item], payment_method="Efectivo", amount_received=30,
    )

    summary = cash.get_summary(sid)
    assert summary.sales_cash == 20
    assert summary.expected_cash == 120


def test_efectivo_esperado_con_ventas_transferencia(services, db, admin_id):
    """Las transferencias no afectan el efectivo esperado."""
    inv, prod, sales, cash = (
        services["inv"], services["prod"], services["sales"], services["cash"]
    )
    sid = cash.open_session(user_id=admin_id, opening_amount=100)

    pid = prod.create(name="A", sale_price=10, created_by=admin_id)
    with db.transaction():
        inv.add_stock(pid, qty=10, unit_cost=4, created_by=admin_id)

    item = _make_cart_item(prod.get(pid))
    sales.register_sale(
        user_id=admin_id, cash_session_id=sid,
        cart=[item], payment_method="Transferencia",
    )

    summary = cash.get_summary(sid)
    assert summary.sales_transfer == 10
    assert summary.sales_cash == 0
    assert summary.expected_cash == 100  # No cambia


# =============================================================================
# Ingresos de caja
# =============================================================================
def test_registrar_ingreso_caja(services, admin_id):
    cash = services["cash"]
    sid = cash.open_session(user_id=admin_id, opening_amount=100)

    cash.register_inflow(
        session_id=sid, concept="Pago cuenta antigua",
        amount=25.0, user_id=admin_id,
    )

    summary = cash.get_summary(sid)
    assert summary.cash_inflows == 25
    assert summary.expected_cash == 125


def test_no_ingreso_sin_concepto(services, admin_id):
    cash = services["cash"]
    sid = cash.open_session(user_id=admin_id, opening_amount=100)
    with pytest.raises(CashError):
        cash.register_inflow(session_id=sid, concept="", amount=10, user_id=admin_id)


def test_no_ingreso_con_monto_negativo(services, admin_id):
    cash = services["cash"]
    sid = cash.open_session(user_id=admin_id, opening_amount=100)
    with pytest.raises(CashError):
        cash.register_inflow(session_id=sid, concept="X", amount=-5, user_id=admin_id)


# =============================================================================
# Gastos
# =============================================================================
def test_efectivo_esperado_resta_gastos_aprobados(services, db, admin_id):
    cash = services["cash"]
    sid = cash.open_session(user_id=admin_id, opening_amount=100)

    db.execute(
        """INSERT INTO expenses(
               cash_session_id, description, amount, requested_by,
               requested_at, status, approved_by, approved_at
           ) VALUES(?,?,?,?,?,?,?,?)""",
        (sid, "Compra bolsas", 15.0, admin_id, "2026-01-01 10:00:00",
         "APPROVED", admin_id, "2026-01-01 10:01:00"),
    )

    summary = cash.get_summary(sid)
    assert summary.approved_expenses == 15
    assert summary.expected_cash == 85


def test_gasto_pendiente_no_afecta_efectivo(services, db, admin_id):
    cash = services["cash"]
    sid = cash.open_session(user_id=admin_id, opening_amount=100)

    db.execute(
        """INSERT INTO expenses(
               cash_session_id, description, amount, requested_by,
               requested_at, status
           ) VALUES(?,?,?,?,?,?)""",
        (sid, "Gasto pendiente", 20.0, admin_id, "2026-01-01 10:00:00", "PENDING"),
    )

    summary = cash.get_summary(sid)
    assert summary.pending_expenses_count == 1
    assert summary.approved_expenses == 0
    assert summary.expected_cash == 100  # No afecta


# =============================================================================
# Cierre
# =============================================================================
def test_cierre_caja_cuadrada(services, admin_id):
    cash = services["cash"]
    sid = cash.open_session(user_id=admin_id, opening_amount=100)

    result = cash.close_session(
        session_id=sid, user_id=admin_id,
        denominations={"20.00": 5},  # 100
    )
    assert result.expected == 100
    assert result.counted == 100
    assert result.difference == 0
    assert result.status == "CUADRADA"


def test_cierre_con_sobrante(services, admin_id):
    cash = services["cash"]
    sid = cash.open_session(user_id=admin_id, opening_amount=100)

    result = cash.close_session(
        session_id=sid, user_id=admin_id,
        denominations={"20.00": 5, "5.00": 1},  # 105
    )
    assert result.counted == 105
    assert result.difference == 5
    assert result.status == "SOBRANTE"


def test_cierre_con_faltante(services, admin_id):
    cash = services["cash"]
    sid = cash.open_session(user_id=admin_id, opening_amount=100)

    result = cash.close_session(
        session_id=sid, user_id=admin_id,
        denominations={"20.00": 4, "5.00": 3},  # 95
    )
    assert result.counted == 95
    assert result.difference == -5
    assert result.status == "FALTANTE"


def test_no_cerrar_con_gastos_pendientes(services, db, admin_id):
    cash = services["cash"]
    sid = cash.open_session(user_id=admin_id, opening_amount=100)

    db.execute(
        """INSERT INTO expenses(
               cash_session_id, description, amount, requested_by,
               requested_at, status
           ) VALUES(?,?,?,?,?,?)""",
        (sid, "Pendiente", 10, admin_id, "2026-01-01 10:00:00", "PENDING"),
    )

    with pytest.raises(PendingExpensesError) as exc:
        cash.close_session(
            session_id=sid, user_id=admin_id,
            denominations={"20.00": 5},
        )
    assert exc.value.count == 1


def test_cerrar_permitiendo_pendientes(services, db, admin_id):
    """Con allow_pending=True, se puede cerrar con gastos pendientes."""
    cash = services["cash"]
    sid = cash.open_session(user_id=admin_id, opening_amount=100)

    db.execute(
        """INSERT INTO expenses(
               cash_session_id, description, amount, requested_by,
               requested_at, status
           ) VALUES(?,?,?,?,?,?)""",
        (sid, "Pendiente", 10, admin_id, "2026-01-01 10:00:00", "PENDING"),
    )

    result = cash.close_session(
        session_id=sid, user_id=admin_id,
        denominations={"20.00": 5},
        allow_pending=True,
    )
    assert result.status == "CUADRADA"


def test_no_cerrar_dos_veces(services, admin_id):
    cash = services["cash"]
    sid = cash.open_session(user_id=admin_id, opening_amount=100)
    cash.close_session(
        session_id=sid, user_id=admin_id,
        denominations={"20.00": 5},
    )
    with pytest.raises(CashAlreadyClosedError):
        cash.close_session(
            session_id=sid, user_id=admin_id,
            denominations={"20.00": 5},
        )


# =============================================================================
# Denominaciones
# =============================================================================
def test_denominaciones_invalidas_falla(services, admin_id):
    cash = services["cash"]
    sid = cash.open_session(user_id=admin_id, opening_amount=100)

    with pytest.raises(CashError):
        cash.close_session(
            session_id=sid, user_id=admin_id,
            denominations={"abc": 5},
        )

    with pytest.raises(CashError):
        cash.close_session(
            session_id=sid, user_id=admin_id,
            denominations={"20.00": -3},
        )


def test_denominaciones_se_guardan_como_json(services, db, admin_id):
    cash = services["cash"]
    sid = cash.open_session(user_id=admin_id, opening_amount=100)

    cash.close_session(
        session_id=sid, user_id=admin_id,
        denominations={"20.00": 3, "10.00": 2, "5.00": 4},  # 100
    )

    row = db.one("SELECT denominations_json FROM cash_sessions WHERE id = ?", (sid,))
    import json
    data = json.loads(row["denominations_json"])
    assert data["20.00"] == 3
    assert data["10.00"] == 2
    assert data["5.00"] == 4


# =============================================================================
# Historial
# =============================================================================
def test_listar_cortes_cerrados(services, admin_id):
    cash = services["cash"]

    sid1 = cash.open_session(user_id=admin_id, opening_amount=100)
    cash.close_session(session_id=sid1, user_id=admin_id,
                       denominations={"20.00": 5})

    # No se puede abrir otra sin cerrar la anterior
    # (ya está cerrada) → sí podemos
    sid2 = cash.open_session(user_id=admin_id, opening_amount=50)
    cash.close_session(session_id=sid2, user_id=admin_id,
                       denominations={"20.00": 2, "10.00": 1})

    closed = cash.list_closed_sessions()
    assert len(closed) == 2
    assert closed[0].id == sid2  # Más reciente primero
    assert closed[1].id == sid1


# =============================================================================
# Integración con ventas + devoluciones
# =============================================================================
def test_flujo_completo_apertura_venta_cierre(services, db, admin_id):
    """Flujo real: abrir caja → vender → devolver parcial → cerrar."""
    inv, prod, sales, cash = (
        services["inv"], services["prod"], services["sales"], services["cash"]
    )

    # 1. Abrir caja con $100
    sid = cash.open_session(user_id=admin_id, opening_amount=100)

    # 2. Vender producto en efectivo
    pid = prod.create(name="A", sale_price=10, created_by=admin_id)
    with db.transaction():
        inv.add_stock(pid, qty=10, unit_cost=4, created_by=admin_id)

    item = _make_cart_item(prod.get(pid), sale_qty=3, inventory_qty=3)
    sale_result = sales.register_sale(
        user_id=admin_id, cash_session_id=sid,
        cart=[item], payment_method="Efectivo", amount_received=30,
    )

    # Verificar efectivo esperado = 100 + 30 = 130
    assert cash.get_summary(sid).expected_cash == 130

    # 3. Devolver 1 unidad en efectivo
    sale_items = sales.get_sale_items(sale_result.sale_id)
    sales.register_return(
        sale_id=sale_result.sale_id,
        sale_item_id=int(sale_items[0]["id"]),
        qty_to_return=1,
        reason="Cliente devuelve 1",
        user_id=admin_id,
        cash_session_id=sid,
        refund_method="Efectivo",
    )

    # Efectivo esperado = 100 + 30 - 10 = 120
    assert cash.get_summary(sid).expected_cash == 120

    # 4. Cerrar con conteo exacto
    result = cash.close_session(
        session_id=sid, user_id=admin_id,
        denominations={"20.00": 6},  # 120
    )
    assert result.counted == 120
    assert result.expected == 120
    assert result.status == "CUADRADA"