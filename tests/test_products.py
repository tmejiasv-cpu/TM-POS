"""Tests del ProductService."""
from __future__ import annotations

import pytest

from vidpos.services.products import (
    DuplicateError,
    ProductError,
    ProductNotFoundError,
    ProductService,
    ProductType,
)


# =============================================================================
# SKU
# =============================================================================
def test_genera_sku_con_formato_correcto(db):
    svc = ProductService(db)
    sku = svc.generate_sku()
    assert sku.startswith("PRTM")
    assert len(sku) == 10
    assert sku[4:].isdigit()


def test_sku_incrementa_correlativo(db, admin_id):
    svc = ProductService(db)
    pid1 = svc.create(name="A", sale_price=1, created_by=admin_id)
    pid2 = svc.create(name="B", sale_price=1, created_by=admin_id)
    sku1 = svc.get(pid1)["sku"]
    sku2 = svc.get(pid2)["sku"]
    assert int(sku2[4:]) == int(sku1[4:]) + 1


# =============================================================================
# Crear
# =============================================================================
def test_crear_producto_basico(db, admin_id):
    svc = ProductService(db)
    pid = svc.create(name="Refresco", sale_price=1.25, created_by=admin_id)
    p = svc.get(pid)
    assert p is not None
    assert p["name"] == "Refresco"
    assert p["sale_price"] == 1.25
    assert p["product_type"] == ProductType.PRODUCT
    assert p["active"] == 1


def test_crear_producto_rechaza_nombre_vacio(db):
    svc = ProductService(db)
    with pytest.raises(ProductError):
        svc.create(name="  ", sale_price=1)


def test_crear_producto_rechaza_precio_negativo(db):
    svc = ProductService(db)
    with pytest.raises(ProductError):
        svc.create(name="A", sale_price=-1)


def test_crear_producto_barcode_duplicado(db, admin_id):
    svc = ProductService(db)
    svc.create(name="A", sale_price=1, barcode="123456", created_by=admin_id)
    with pytest.raises(DuplicateError):
        svc.create(name="B", sale_price=1, barcode="123456", created_by=admin_id)


def test_crear_categoria_al_vuelo(db, admin_id):
    svc = ProductService(db)
    svc.create(name="A", sale_price=1, category="Bebidas", created_by=admin_id)
    assert "Bebidas" in svc.list_categories()


# =============================================================================
# Actualizar / desactivar
# =============================================================================
def test_actualizar_producto(db, admin_id):
    svc = ProductService(db)
    pid = svc.create(name="A", sale_price=1, created_by=admin_id)
    svc.update(pid, name="A modificado", sale_price=2.5)
    p = svc.get(pid)
    assert p["name"] == "A modificado"
    assert p["sale_price"] == 2.5


def test_desactivar_producto(db, admin_id):
    svc = ProductService(db)
    pid = svc.create(name="A", sale_price=1, created_by=admin_id)
    svc.deactivate(pid)
    assert svc.get(pid)["active"] == 0
    # No aparece en listados activos
    assert all(p["id"] != pid for p in svc.list_products())


def test_no_elimina_producto_con_historial(db, admin_id):
    svc = ProductService(db)
    pid = svc.create(name="A", sale_price=1, created_by=admin_id)
    # Simulamos historial con un movimiento de inventario
    db.execute(
        """INSERT INTO inventory_movements(product_id, movement_type, qty, created_at)
           VALUES(?,?,?,?)""",
        (pid, "COMPRA", 10, "2026-01-01 00:00:00"),
    )
    assert svc.has_history(pid) is True
    assert svc.delete_if_no_history(pid) is False
    assert svc.get(pid) is not None


def test_elimina_producto_sin_historial(db, admin_id):
    svc = ProductService(db)
    pid = svc.create(name="A", sale_price=1, created_by=admin_id)
    assert svc.delete_if_no_history(pid) is True
    assert svc.get(pid) is None


# =============================================================================
# Presentaciones
# =============================================================================
def test_agregar_presentacion(db, admin_id):
    svc = ProductService(db)
    pid = svc.create(name="Agua", sale_price=0.5, unit="Bolsa", created_by=admin_id)
    pres_id = svc.add_presentation(
        pid, name="Bolsón", factor=25, sale_price=10.0, created_by=admin_id
    )
    assert pres_id > 0
    pres = svc.list_presentations(pid)
    assert len(pres) == 1
    assert pres[0]["name"] == "Bolsón"
    assert pres[0]["factor"] == 25
    assert pres[0]["sale_price"] == 10.0


def test_presentacion_duplicada_activa_falla(db, admin_id):
    svc = ProductService(db)
    pid = svc.create(name="Agua", sale_price=0.5, created_by=admin_id)
    svc.add_presentation(pid, name="Bolsón", factor=25, sale_price=10, created_by=admin_id)
    with pytest.raises(DuplicateError):
        svc.add_presentation(pid, name="Bolsón", factor=25, sale_price=10, created_by=admin_id)


def test_presentacion_desactivada_se_reactiva(db, admin_id):
    svc = ProductService(db)
    pid = svc.create(name="Agua", sale_price=0.5, created_by=admin_id)
    pres_id = svc.add_presentation(pid, name="Bolsón", factor=25, sale_price=10, created_by=admin_id)
    svc.deactivate_presentation(pres_id)

    # Volver a crearla con el mismo nombre reactiva la existente
    pres_id2 = svc.add_presentation(pid, name="Bolsón", factor=25, sale_price=12, created_by=admin_id)
    assert pres_id2 == pres_id
    pres = svc.list_presentations(pid)
    assert pres[0]["sale_price"] == 12  # Actualizada
    assert pres[0]["active"] == 1


def test_presentacion_barcode_duplicado(db, admin_id):
    svc = ProductService(db)
    pid = svc.create(name="A", sale_price=1, created_by=admin_id)
    svc.add_presentation(pid, name="P1", factor=2, sale_price=2, barcode="999", created_by=admin_id)
    with pytest.raises(DuplicateError):
        svc.add_presentation(pid, name="P2", factor=3, sale_price=3, barcode="999", created_by=admin_id)


# =============================================================================
# Adicionales
# =============================================================================
def test_agregar_adicional_sin_componente(db, admin_id):
    svc = ProductService(db)
    pid = svc.create(name="Café", sale_price=1, created_by=admin_id)
    addon_id = svc.add_addon(pid, name="Preparación", extra_price=0.25, created_by=admin_id)
    addons = svc.list_addons(pid)
    assert len(addons) == 1
    assert addons[0]["name"] == "Preparación"
    assert addons[0]["extra_price"] == 0.25
    assert addons[0]["component_product_id"] is None


def test_agregar_adicional_con_componente(db, admin_id):
    svc = ProductService(db)
    pid = svc.create(name="Café", sale_price=1, created_by=admin_id)
    cremora_id = svc.create(name="Cremora", sale_price=0.1, created_by=admin_id)

    addon_id = svc.add_addon(
        pid, name="Cremora", extra_price=0.1,
        component_product_id=cremora_id, component_qty=1,
        created_by=admin_id,
    )
    addons = svc.list_addons(pid)
    assert addons[0]["component_product_id"] == cremora_id
    assert addons[0]["component_qty"] == 1


def test_adicional_con_componente_exige_cantidad(db, admin_id):
    svc = ProductService(db)
    pid = svc.create(name="Café", sale_price=1, created_by=admin_id)
    comp_id = svc.create(name="Cremora", sale_price=0.1, created_by=admin_id)
    with pytest.raises(ProductError):
        svc.add_addon(
            pid, name="Cremora", extra_price=0.1,
            component_product_id=comp_id, component_qty=0,
            created_by=admin_id,
        )


# =============================================================================
# resolve_barcode
# =============================================================================
def test_resolve_barcode_producto(db, admin_id):
    svc = ProductService(db)
    svc.create(name="Refresco", sale_price=1, barcode="123", created_by=admin_id)
    res = svc.resolve_barcode("123")
    assert res is not None
    assert res["kind"] == "product"
    assert res["effective_price"] == 1.0
    assert res["effective_factor"] == 1.0


def test_resolve_barcode_presentacion(db, admin_id):
    svc = ProductService(db)
    pid = svc.create(name="Agua", sale_price=0.5, unit="Bolsa", created_by=admin_id)
    svc.add_presentation(pid, name="Bolsón", factor=25, sale_price=10.0, barcode="P999", created_by=admin_id)

    res = svc.resolve_barcode("P999")
    assert res is not None
    assert res["kind"] == "presentation"
    assert res["effective_price"] == 10.0
    assert res["effective_factor"] == 25.0


def test_resolve_barcode_por_sku(db, admin_id):
    svc = ProductService(db)
    pid = svc.create(name="A", sale_price=1, created_by=admin_id)
    sku = svc.get(pid)["sku"]
    res = svc.resolve_barcode(sku)
    assert res is not None
    assert res["product"]["id"] == pid


def test_resolve_barcode_inexistente(db):
    svc = ProductService(db)
    assert svc.resolve_barcode("no-existe") is None


# =============================================================================
# Búsqueda
# =============================================================================
def test_buscar_por_nombre(db, admin_id):
    svc = ProductService(db)
    svc.create(name="Coca Cola", sale_price=1, created_by=admin_id)
    svc.create(name="Pepsi", sale_price=1, created_by=admin_id)
    svc.create(name="Fanta", sale_price=1, created_by=admin_id)

    results = svc.list_products(search="cola")
    names = [p["name"] for p in results]
    assert "Coca Cola" in names
    assert "Pepsi" not in names


def test_buscar_por_categoria(db, admin_id):
    svc = ProductService(db)
    svc.create(name="A", sale_price=1, category="Bebidas", created_by=admin_id)
    svc.create(name="B", sale_price=1, category="Snacks", created_by=admin_id)

    results = svc.list_products(category="Bebidas")
    assert len(results) == 1
    assert results[0]["name"] == "A"