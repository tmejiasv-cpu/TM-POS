"""Tests del SalesService."""
from __future__ import annotations

import pytest

from vidpos.services.inventory import InventoryService
from vidpos.services.products import ProductService
from vidpos.services.sales import (
    AddonSelection,
    CartEmptyError,
    CartItem,
    InsufficientPaymentError,
    NoCashSessionError,
    ReturnExceedsSaleError,
    SaleAlreadyVoidedError,
    SaleError,
    SaleHasReturnsError,
    SalesService,
)


# =============================================================================
# Fixtures locales
# =============================================================================
@pytest.fixture
def cash_session(db, admin_id):
    """Abre una jornada de caja para los tests."""
    cur = db.execute(
        """INSERT INTO cash_sessions(user_id, opened_at, opening_amount, status)
           VALUES(?,?,?,?)""",
        (admin_id, "2026-01-01 08:00:00", 100.0, "OPEN"),
    )
    return int(cur.lastrowid)


@pytest.fixture
def services(db):
    inv = InventoryService(db)
    prod = ProductService(db)
    sales = SalesService(db, products=prod, inventory=inv)
    return {"inv": inv, "prod": prod, "sales": sales}


def _make_cart_item(product, *, sale_qty=1.0, factor=1.0,
                    inventory_qty=None, price=None, addons=None) -> CartItem:
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
        addons=addons or [],
    )


# =============================================================================
# Validaciones básicas
# =============================================================================
def test_carrito_vacio_falla(services, admin_id, cash_session):
    with pytest.raises(CartEmptyError):
        services["sales"].register_sale(
            user_id=admin_id, cash_session_id=cash_session,
            cart=[], payment_method="Efectivo", amount_received=0,
        )


def test_sin_sesion_caja_falla(services, admin_id, db):
    svc = services["sales"]
    with pytest.raises(NoCashSessionError):
        svc.register_sale(
            user_id=admin_id, cash_session_id=0,
            cart=[_make_cart_item({"id":1,"sku":"X","name":"X","product_type":"SERVICE","sale_price":1,"unit":"U"})],
            payment_method="Transferencia",
        )


def test_efectivo_insuficiente_falla(services, db, admin_id, cash_session):
    """Un pago en efectivo menor al total debe fallar con InsufficientPaymentError."""
    prod = services["prod"]
    # Usamos SERVICE para aislar la prueba de pago de la validación de stock
    pid = prod.create(
        name="Saldo", sale_price=10,
        product_type="SERVICE", created_by=admin_id,
    )
    item = _make_cart_item(prod.get(pid), inventory_qty=0)

    with pytest.raises(InsufficientPaymentError) as exc:
        services["sales"].register_sale(
            user_id=admin_id, cash_session_id=cash_session,
            cart=[item], payment_method="Efectivo", amount_received=5,
        )
    assert exc.value.missing == 5

# =============================================================================
# Venta básica
# =============================================================================
def test_venta_simple_efectivo(services, db, admin_id, cash_session):
    inv, prod, sales = services["inv"], services["prod"], services["sales"]
    pid = prod.create(name="Refresco", sale_price=2.5, created_by=admin_id)
    with db.transaction():
        inv.add_stock(pid, qty=10, unit_cost=1.0, created_by=admin_id)

    item = _make_cart_item(prod.get(pid), sale_qty=2, inventory_qty=2)
    result = sales.register_sale(
        user_id=admin_id, cash_session_id=cash_session,
        cart=[item], payment_method="Efectivo", amount_received=10.0,
    )

    assert result.sale_id > 0
    assert result.total == 5.0
    assert result.cost_total == 2.0
    assert result.change_given == 5.0

    # Stock descontado
    assert inv.current_stock(pid) == 8.0


def test_venta_transferencia_sin_cambio(services, db, admin_id, cash_session):
    inv, prod, sales = services["inv"], services["prod"], services["sales"]
    pid = prod.create(name="A", sale_price=5, created_by=admin_id)
    with db.transaction():
        inv.add_stock(pid, qty=5, unit_cost=2, created_by=admin_id)

    item = _make_cart_item(prod.get(pid))
    result = sales.register_sale(
        user_id=admin_id, cash_session_id=cash_session,
        cart=[item], payment_method="Transferencia",
    )
    assert result.amount_received is None
    assert result.change_given == 0.0


def test_venta_fifo_multiples_lotes(services, db, admin_id, cash_session):
    """Vender 15 con dos lotes de 10: 10 al costo 2 y 5 al costo 3."""
    inv, prod, sales = services["inv"], services["prod"], services["sales"]
    pid = prod.create(name="A", sale_price=4, created_by=admin_id)
    with db.transaction():
        inv.add_stock(pid, qty=10, unit_cost=2.0, created_by=admin_id)
    import time; time.sleep(0.01)
    with db.transaction():
        inv.add_stock(pid, qty=10, unit_cost=3.0, created_by=admin_id)

    item = _make_cart_item(prod.get(pid), sale_qty=15, inventory_qty=15)
    result = sales.register_sale(
        user_id=admin_id, cash_session_id=cash_session,
        cart=[item], payment_method="Transferencia",
    )

    assert result.total == 60.0
    assert result.cost_total == 10*2.0 + 5*3.0  # = 35


def test_venta_servicio_no_consume_inventario(services, db, admin_id, cash_session):
    inv, prod, sales = services["inv"], services["prod"], services["sales"]
    pid = prod.create(name="Saldo", sale_price=5, product_type="SERVICE", created_by=admin_id)

    item = _make_cart_item(prod.get(pid), sale_qty=1, inventory_qty=0)
    result = sales.register_sale(
        user_id=admin_id, cash_session_id=cash_session,
        cart=[item], payment_method="Efectivo", amount_received=5,
    )
    assert result.total == 5.0
    assert result.cost_total == 0.0


def test_venta_con_presentacion(services, db, admin_id, cash_session):
    """Bolsón x25 con precio 10, se vende 1 bolsón → descuenta 25 unidades base."""
    inv, prod, sales = services["inv"], services["prod"], services["sales"]
    pid = prod.create(name="Agua", sale_price=0.5, unit="Bolsa", created_by=admin_id)
    with db.transaction():
        inv.add_stock(pid, qty=100, unit_cost=0.3, created_by=admin_id)

    item = CartItem(
        product_id=pid, sku=prod.get(pid)["sku"], name="Agua",
        product_type="PRODUCT",
        presentation_name="Bolsón", presentation_factor=25,
        sale_qty=1, inventory_qty=25, unit_price=10.0,
    )
    result = sales.register_sale(
        user_id=admin_id, cash_session_id=cash_session,
        cart=[item], payment_method="Efectivo", amount_received=10,
    )
    assert result.total == 10.0
    assert inv.current_stock(pid) == 75.0


# =============================================================================
# Validación previa de stock
# =============================================================================
def test_venta_falla_sin_stock(services, db, admin_id, cash_session):
    inv, prod, sales = services["inv"], services["prod"], services["sales"]
    pid = prod.create(name="A", sale_price=1, created_by=admin_id)
    with db.transaction():
        inv.add_stock(pid, qty=3, unit_cost=1, created_by=admin_id)

    item = _make_cart_item(prod.get(pid), sale_qty=5, inventory_qty=5)
    with pytest.raises(Exception):  # InsufficientStockError
        sales.register_sale(
            user_id=admin_id, cash_session_id=cash_session,
            cart=[item], payment_method="Efectivo", amount_received=10,
        )

    # Nada debe haber cambiado
    assert inv.current_stock(pid) == 3.0


# =============================================================================
# Adicionales
# =============================================================================
def test_venta_con_adicional_sin_inventario(services, db, admin_id, cash_session):
    inv, prod, sales = services["inv"], services["prod"], services["sales"]
    pid = prod.create(name="Café", sale_price=1.0, created_by=admin_id)
    with db.transaction():
        inv.add_stock(pid, qty=10, unit_cost=0.3, created_by=admin_id)

    addon = AddonSelection(addon_id=1, name="Preparación", extra_price=0.25)
    item = _make_cart_item(prod.get(pid), addons=[addon])

    result = sales.register_sale(
        user_id=admin_id, cash_session_id=cash_session,
        cart=[item], payment_method="Efectivo", amount_received=2,
    )
    assert result.total == 1.25


def test_venta_con_adicional_que_consume_inventario(
    services, db, admin_id, cash_session
):
    inv, prod, sales = services["inv"], services["prod"], services["sales"]
    pid = prod.create(name="Café", sale_price=1.0, created_by=admin_id)
    comp_id = prod.create(name="Cremora", sale_price=0.1, created_by=admin_id)
    with db.transaction():
        inv.add_stock(pid, qty=10, unit_cost=0.3, created_by=admin_id)
        inv.add_stock(comp_id, qty=10, unit_cost=0.05, created_by=admin_id)

    addon = AddonSelection(
        addon_id=None, name="Cremora", extra_price=0.1,
        component_product_id=comp_id, component_qty=1,
    )
    item = _make_cart_item(prod.get(pid), addons=[addon])
    result = sales.register_sale(
        user_id=admin_id, cash_session_id=cash_session,
        cart=[item], payment_method="Efectivo", amount_received=2,
    )

    assert result.total == 1.10
    assert inv.current_stock(comp_id) == 9.0


# =============================================================================
# Borradores
# =============================================================================
def test_guardar_y_recuperar_borrador(services, db, admin_id):
    inv, prod, sales = services["inv"], services["prod"], services["sales"]
    pid = prod.create(name="A", sale_price=2, created_by=admin_id)

    cart = [_make_cart_item(prod.get(pid), sale_qty=3, inventory_qty=3)]
    sales.save_draft(admin_id, cart, "Efectivo", "10")

    draft = sales.get_draft(admin_id)
    assert draft is not None
    assert len(draft["cart"]) == 1
    assert draft["cart"][0].sale_qty == 3
    assert draft["payment_method"] == "Efectivo"


def test_venta_limpia_borrador(services, db, admin_id, cash_session):
    inv, prod, sales = services["inv"], services["prod"], services["sales"]
    pid = prod.create(name="A", sale_price=2, created_by=admin_id)
    with db.transaction():
        inv.add_stock(pid, qty=5, unit_cost=1, created_by=admin_id)

    item = _make_cart_item(prod.get(pid))
    sales.save_draft(admin_id, [item], "Efectivo", "10")
    assert sales.get_draft(admin_id) is not None

    sales.register_sale(
        user_id=admin_id, cash_session_id=cash_session,
        cart=[item], payment_method="Efectivo", amount_received=10,
    )
    # El borrador debe haberse limpiado
    assert sales.get_draft(admin_id) is None


# =============================================================================
# Anulación
# =============================================================================
def test_anular_venta_restaura_inventario(services, db, admin_id, cash_session):
    inv, prod, sales = services["inv"], services["prod"], services["sales"]
    pid = prod.create(name="A", sale_price=5, created_by=admin_id)
    with db.transaction():
        inv.add_stock(pid, qty=10, unit_cost=2, created_by=admin_id)

    item = _make_cart_item(prod.get(pid), sale_qty=3, inventory_qty=3)
    result = sales.register_sale(
        user_id=admin_id, cash_session_id=cash_session,
        cart=[item], payment_method="Efectivo", amount_received=20,
    )
    assert inv.current_stock(pid) == 7.0

    sales.void_sale(sale_id=result.sale_id, user_id=admin_id, reason="Error de cobro")
    assert inv.current_stock(pid) == 10.0

    sale = sales.get_sale(result.sale_id)
    assert sale["status"] == "VOIDED"
    assert sale["void_reason"] == "Error de cobro"


def test_no_se_puede_anular_dos_veces(services, db, admin_id, cash_session):
    inv, prod, sales = services["inv"], services["prod"], services["sales"]
    pid = prod.create(name="A", sale_price=5, created_by=admin_id)
    with db.transaction():
        inv.add_stock(pid, qty=5, unit_cost=2, created_by=admin_id)

    item = _make_cart_item(prod.get(pid))
    result = sales.register_sale(
        user_id=admin_id, cash_session_id=cash_session,
        cart=[item], payment_method="Efectivo", amount_received=5,
    )
    sales.void_sale(sale_id=result.sale_id, user_id=admin_id, reason="X")

    with pytest.raises(SaleAlreadyVoidedError):
        sales.void_sale(sale_id=result.sale_id, user_id=admin_id, reason="Y")


def test_no_anular_si_tiene_devoluciones(services, db, admin_id, cash_session):
    inv, prod, sales = services["inv"], services["prod"], services["sales"]
    pid = prod.create(name="A", sale_price=5, created_by=admin_id)
    with db.transaction():
        inv.add_stock(pid, qty=10, unit_cost=2, created_by=admin_id)

    item = _make_cart_item(prod.get(pid), sale_qty=3, inventory_qty=3)
    result = sales.register_sale(
        user_id=admin_id, cash_session_id=cash_session,
        cart=[item], payment_method="Efectivo", amount_received=20,
    )

    sale_items = sales.get_sale_items(result.sale_id)
    sales.register_return(
        sale_id=result.sale_id, sale_item_id=int(sale_items[0]["id"]),
        qty_to_return=1, reason="Cliente devuelve 1",
        user_id=admin_id, cash_session_id=cash_session,
    )

    with pytest.raises(SaleHasReturnsError):
        sales.void_sale(sale_id=result.sale_id, user_id=admin_id, reason="Ya no")


# =============================================================================
# Devoluciones parciales
# =============================================================================
def test_devolucion_parcial_restaura_stock(services, db, admin_id, cash_session):
    inv, prod, sales = services["inv"], services["prod"], services["sales"]
    pid = prod.create(name="A", sale_price=5, created_by=admin_id)
    with db.transaction():
        inv.add_stock(pid, qty=10, unit_cost=2, created_by=admin_id)

    item = _make_cart_item(prod.get(pid), sale_qty=4, inventory_qty=4)
    result = sales.register_sale(
        user_id=admin_id, cash_session_id=cash_session,
        cart=[item], payment_method="Efectivo", amount_received=25,
    )
    assert inv.current_stock(pid) == 6.0

    sale_items = sales.get_sale_items(result.sale_id)
    ret = sales.register_return(
        sale_id=result.sale_id,
        sale_item_id=int(sale_items[0]["id"]),
        qty_to_return=2,
        reason="Cliente devuelve 2",
        user_id=admin_id,
        cash_session_id=cash_session,
    )
    assert ret.total_refund == 10.0  # 2 x $5
    assert inv.current_stock(pid) == 8.0


def test_no_devolver_mas_de_lo_vendido(services, db, admin_id, cash_session):
    inv, prod, sales = services["inv"], services["prod"], services["sales"]
    pid = prod.create(name="A", sale_price=5, created_by=admin_id)
    with db.transaction():
        inv.add_stock(pid, qty=10, unit_cost=2, created_by=admin_id)

    item = _make_cart_item(prod.get(pid), sale_qty=2, inventory_qty=2)
    result = sales.register_sale(
        user_id=admin_id, cash_session_id=cash_session,
        cart=[item], payment_method="Efectivo", amount_received=10,
    )

    sale_items = sales.get_sale_items(result.sale_id)
    with pytest.raises(ReturnExceedsSaleError):
        sales.register_return(
            sale_id=result.sale_id,
            sale_item_id=int(sale_items[0]["id"]),
            qty_to_return=3,
            reason="Intento inválido",
            user_id=admin_id,
            cash_session_id=cash_session,
        )


def test_devolucion_dos_veces_hasta_el_limite(services, db, admin_id, cash_session):
    inv, prod, sales = services["inv"], services["prod"], services["sales"]
    pid = prod.create(name="A", sale_price=5, created_by=admin_id)
    with db.transaction():
        inv.add_stock(pid, qty=10, unit_cost=2, created_by=admin_id)

    item = _make_cart_item(prod.get(pid), sale_qty=3, inventory_qty=3)
    result = sales.register_sale(
        user_id=admin_id, cash_session_id=cash_session,
        cart=[item], payment_method="Efectivo", amount_received=15,
    )
    sale_items = sales.get_sale_items(result.sale_id)
    item_id = int(sale_items[0]["id"])

    # Primera: 1 unidad
    sales.register_return(
        sale_id=result.sale_id, sale_item_id=item_id,
        qty_to_return=1, reason="X",
        user_id=admin_id, cash_session_id=cash_session,
    )
    # Segunda: 2 unidades (completa)
    sales.register_return(
        sale_id=result.sale_id, sale_item_id=item_id,
        qty_to_return=2, reason="Y",
        user_id=admin_id, cash_session_id=cash_session,
    )
    # Tercera: 1 unidad más → debe fallar
    with pytest.raises(ReturnExceedsSaleError):
        sales.register_return(
            sale_id=result.sale_id, sale_item_id=item_id,
            qty_to_return=1, reason="Z",
            user_id=admin_id, cash_session_id=cash_session,
        )