"""Servicio de productos: catálogo, presentaciones y adicionales.

Reglas de negocio:
  - Cada producto tiene un SKU automático con formato PRTM{AA}{NNNN}.
  - Los productos tipo 'SERVICE' no manejan inventario.
  - Las presentaciones agrupan unidades base (factor > 1) o variantes
    de venta (factor = 1, ej. "Preparada" a distinto precio).
  - Los adicionales pueden sumar precio sin consumir inventario, o
    consumir otro producto del catálogo.
  - Un producto con historial no se elimina: se desactiva.
"""
from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime

from vidpos.core.database import Database

log = logging.getLogger(__name__)


# =============================================================================
# Excepciones
# =============================================================================
class ProductError(Exception):
    """Error de dominio del catálogo."""


class ProductNotFoundError(ProductError):
    """El producto no existe."""


class DuplicateError(ProductError):
    """Nombre, código o SKU ya existe."""


# =============================================================================
# Tipos
# =============================================================================
class ProductType:
    PRODUCT = "PRODUCT"
    SERVICE = "SERVICE"

    ALL = (PRODUCT, SERVICE)


# =============================================================================
# DTOs
# =============================================================================
@dataclass
class PresentationDTO:
    id: int | None
    product_id: int
    name: str
    factor: float
    sale_price: float
    barcode: str | None
    active: bool


@dataclass
class AddonDTO:
    id: int | None
    parent_product_id: int
    name: str
    extra_price: float
    component_product_id: int | None
    component_qty: float
    active: bool


# =============================================================================
# Servicio
# =============================================================================
class ProductService:
    """CRUD de productos, presentaciones y adicionales."""

    def __init__(self, db: Database) -> None:
        self.db = db

    # =========================================================================
    # SKU automático
    # =========================================================================
    def generate_sku(self) -> str:
        """Genera PRTM{AA}{NNNN} con correlativo por año.

        Ejemplo: PRTM260001 (año 2026, secuencia 1).
        """
        yy = datetime.now().strftime("%y")
        prefix = f"PRTM{yy}"
        # Obtenemos el mayor consecutivo existente para este prefijo
        rows = self.db.all(
            "SELECT sku FROM products WHERE sku LIKE ?",
            (prefix + "%",),
        )
        max_seq = 0
        for r in rows:
            tail = str(r["sku"])[len(prefix):]
            if tail.isdigit():
                max_seq = max(max_seq, int(tail))
        return f"{prefix}{max_seq + 1:04d}"

    # =========================================================================
    # Categorías
    # =========================================================================
    def ensure_category(self, name: str) -> None:
        """Crea la categoría si no existe. No hace nada si name está vacío."""
        name = (name or "").strip()
        if not name:
            return
        self.db.conn.execute(
            "INSERT OR IGNORE INTO categories(name, active, created_at) VALUES(?, 1, ?)",
            (name, self._now()),
        )

    def list_categories(self, only_active: bool = True) -> list[str]:
        sql = "SELECT name FROM categories"
        if only_active:
            sql += " WHERE active = 1"
        sql += " ORDER BY name COLLATE NOCASE"
        return [r["name"] for r in self.db.all(sql)]

    # =========================================================================
    # Productos — lectura
    # =========================================================================
    def get(self, product_id: int) -> dict | None:
        row = self.db.one("SELECT * FROM products WHERE id = ?", (product_id,))
        return dict(row) if row else None

    def get_by_sku(self, sku: str) -> dict | None:
        row = self.db.one("SELECT * FROM products WHERE sku = ?", (sku,))
        return dict(row) if row else None

    def get_by_barcode(self, barcode: str) -> dict | None:
        row = self.db.one("SELECT * FROM products WHERE barcode = ?", (barcode,))
        return dict(row) if row else None

    def list_products(
        self,
        *,
        search: str = "",
        category: str = "",
        product_type: str = "",
        only_active: bool = True,
        limit: int = 1000,
    ) -> list[dict]:
        """Búsqueda flexible por nombre, SKU, código de barras o categoría."""
        clauses = []
        params: list = []

        if only_active:
            clauses.append("active = 1")

        if search:
            term = f"%{search.strip()}%"
            clauses.append(
                "(name LIKE ? OR sku LIKE ? OR barcode LIKE ? OR category LIKE ?)"
            )
            params.extend([term, term, term, term])

        if category:
            clauses.append("category = ?")
            params.append(category)

        if product_type:
            clauses.append("product_type = ?")
            params.append(product_type)

        sql = "SELECT * FROM products"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY name COLLATE NOCASE LIMIT ?"
        params.append(limit)

        return [dict(r) for r in self.db.all(sql, tuple(params))]

    # =========================================================================
    # Productos — escritura
    # =========================================================================
    def create(
        self,
        *,
        name: str,
        sale_price: float,
        unit: str = "Unidad",
        category: str = "",
        barcode: str | None = None,
        min_stock: float = 0.0,
        product_type: str = ProductType.PRODUCT,
        created_by: int | None = None,
    ) -> int:
        """Crea un producto nuevo. Devuelve el id."""
        name = (name or "").strip()
        if not name:
            raise ProductError("El nombre es obligatorio.")
        if sale_price < 0:
            raise ProductError("El precio no puede ser negativo.")
        if min_stock < 0:
            raise ProductError("El stock mínimo no puede ser negativo.")
        if product_type not in ProductType.ALL:
            raise ProductError(f"Tipo de producto inválido: {product_type}")

        barcode = (barcode or "").strip() or None
        category = (category or "").strip()

        if barcode:
            existing = self.db.one(
                "SELECT id FROM products WHERE barcode = ?", (barcode,)
            )
            if existing:
                raise DuplicateError(f"El código de barras {barcode} ya está en uso.")

        self.ensure_category(category)

        # Reintento por si dos usuarios generan el mismo SKU a la vez
        for attempt in range(5):
            sku = self.generate_sku()
            try:
                cur = self.db.conn.execute(
                    """INSERT INTO products(
                           sku, barcode, name, category, unit, sale_price,
                           min_stock, product_type, active, created_by, created_at
                       ) VALUES(?,?,?,?,?,?,?,?,1,?,?)""",
                    (
                        sku, barcode, name, category, unit, sale_price,
                        min_stock, product_type, created_by, self._now(),
                    ),
                )
                return int(cur.lastrowid)
            except sqlite3.IntegrityError as e:
                if "sku" in str(e) and attempt < 4:
                    log.warning("SKU colisión, reintentando (%s)", attempt + 1)
                    continue
                raise DuplicateError(str(e)) from e

        raise ProductError("No se pudo generar un SKU único tras varios intentos.")

    def update(
        self,
        product_id: int,
        *,
        name: str,
        sale_price: float,
        unit: str = "Unidad",
        category: str = "",
        barcode: str | None = None,
        min_stock: float = 0.0,
        product_type: str = ProductType.PRODUCT,
    ) -> None:
        """Actualiza un producto existente. No modifica inventario."""
        product = self.get(product_id)
        if not product:
            raise ProductNotFoundError(f"Producto {product_id} no existe.")

        name = (name or "").strip()
        if not name:
            raise ProductError("El nombre es obligatorio.")
        if sale_price < 0 or min_stock < 0:
            raise ProductError("Precio y stock mínimo deben ser >= 0.")
        if product_type not in ProductType.ALL:
            raise ProductError(f"Tipo de producto inválido: {product_type}")

        barcode = (barcode or "").strip() or None
        category = (category or "").strip()

        if barcode:
            dup = self.db.one(
                "SELECT id FROM products WHERE barcode = ? AND id <> ?",
                (barcode, product_id),
            )
            if dup:
                raise DuplicateError(f"El código de barras {barcode} ya está en uso.")

        self.ensure_category(category)

        self.db.execute(
            """UPDATE products
               SET name=?, barcode=?, category=?, unit=?, sale_price=?,
                   min_stock=?, product_type=?, updated_at=?
               WHERE id=?""",
            (
                name, barcode, category, unit, sale_price,
                min_stock, product_type, self._now(), product_id,
            ),
        )

    def deactivate(self, product_id: int) -> None:
        """Marca un producto como inactivo. No borra historial."""
        self.db.execute(
            "UPDATE products SET active = 0, updated_at = ? WHERE id = ?",
            (self._now(), product_id),
        )

    def activate(self, product_id: int) -> None:
        self.db.execute(
            "UPDATE products SET active = 1, updated_at = ? WHERE id = ?",
            (self._now(), product_id),
        )

    def has_history(self, product_id: int) -> bool:
        """¿El producto participa en ventas, compras o movimientos?"""
        checks = [
            "SELECT 1 FROM sale_items WHERE product_id = ? LIMIT 1",
            "SELECT 1 FROM purchase_items WHERE product_id = ? LIMIT 1",
            "SELECT 1 FROM inventory_movements WHERE product_id = ? LIMIT 1",
            "SELECT 1 FROM inventory_lots WHERE product_id = ? LIMIT 1",
        ]
        for sql in checks:
            if self.db.one(sql, (product_id,)):
                return True
        return False

    def delete_if_no_history(self, product_id: int) -> bool:
        """Elimina físicamente si no hay historial. Devuelve True si borró."""
        if self.has_history(product_id):
            return False
        with self.db.transaction():
            self.db.conn.execute(
                "DELETE FROM product_presentations WHERE product_id = ?", (product_id,)
            )
            self.db.conn.execute(
                "DELETE FROM product_addons WHERE parent_product_id = ?", (product_id,)
            )
            self.db.conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
        return True

    # =========================================================================
    # Presentaciones
    # =========================================================================
    def list_presentations(
        self, product_id: int, only_active: bool = True
    ) -> list[dict]:
        sql = "SELECT * FROM product_presentations WHERE product_id = ?"
        if only_active:
            sql += " AND active = 1"
        sql += " ORDER BY factor, name"
        return [dict(r) for r in self.db.all(sql, (product_id,))]

    def add_presentation(
        self,
        product_id: int,
        *,
        name: str,
        factor: float,
        sale_price: float,
        barcode: str | None = None,
        created_by: int | None = None,
    ) -> int:
        """Crea una presentación. Si existe una desactivada con el mismo
        nombre, la reactiva."""
        name = (name or "").strip()
        if not name:
            raise ProductError("El nombre de la presentación es obligatorio.")
        if factor <= 0:
            raise ProductError("El factor debe ser mayor que cero.")
        if sale_price < 0:
            raise ProductError("El precio no puede ser negativo.")

        barcode = (barcode or "").strip() or None

        # ¿Existe ya una presentación con ese nombre (activa o no)?
        existing = self.db.one(
            """SELECT * FROM product_presentations
               WHERE product_id = ? AND lower(trim(name)) = lower(trim(?))""",
            (product_id, name),
        )
        if existing:
            if existing["active"]:
                raise DuplicateError(
                    f"Ya existe una presentación llamada '{name}' para este producto."
                )
            # Reactivar la existente
            self.db.execute(
                """UPDATE product_presentations
                   SET name=?, factor=?, sale_price=?, barcode=?, active=1
                   WHERE id=?""",
                (name, factor, sale_price, barcode, existing["id"]),
            )
            return int(existing["id"])

        if barcode:
            dup = self.db.one(
                "SELECT id FROM product_presentations WHERE barcode = ?", (barcode,)
            )
            if dup:
                raise DuplicateError(f"El código de barras {barcode} ya está en uso.")

        cur = self.db.conn.execute(
            """INSERT INTO product_presentations(
                   product_id, name, factor, sale_price, barcode,
                   active, created_by, created_at
               ) VALUES(?,?,?,?,?,1,?,?)""",
            (product_id, name, factor, sale_price, barcode, created_by, self._now()),
        )
        return int(cur.lastrowid)

    def update_presentation(
        self,
        presentation_id: int,
        *,
        name: str,
        factor: float,
        sale_price: float,
        barcode: str | None = None,
    ) -> None:
        if factor <= 0:
            raise ProductError("El factor debe ser mayor que cero.")
        if sale_price < 0:
            raise ProductError("El precio no puede ser negativo.")

        barcode = (barcode or "").strip() or None
        if barcode:
            dup = self.db.one(
                "SELECT id FROM product_presentations WHERE barcode = ? AND id <> ?",
                (barcode, presentation_id),
            )
            if dup:
                raise DuplicateError(f"El código de barras {barcode} ya está en uso.")

        self.db.execute(
            """UPDATE product_presentations
               SET name=?, factor=?, sale_price=?, barcode=?
               WHERE id=?""",
            (name, factor, sale_price, barcode, presentation_id),
        )

    def deactivate_presentation(self, presentation_id: int) -> None:
        self.db.execute(
            "UPDATE product_presentations SET active = 0 WHERE id = ?",
            (presentation_id,),
        )

    def get_presentation_by_barcode(self, barcode: str) -> dict | None:
        row = self.db.one(
            """SELECT pp.*, p.name AS product_name, p.sku, p.unit,
                      p.sale_price AS base_sale_price, p.product_type
               FROM product_presentations pp
               JOIN products p ON p.id = pp.product_id
               WHERE pp.barcode = ? AND pp.active = 1 AND p.active = 1""",
            (barcode,),
        )
        return dict(row) if row else None

    # =========================================================================
    # Adicionales
    # =========================================================================
    def list_addons(self, product_id: int, only_active: bool = True) -> list[dict]:
        sql = """SELECT a.*, p.name AS component_name, p.sku AS component_sku
                 FROM product_addons a
                 LEFT JOIN products p ON p.id = a.component_product_id
                 WHERE a.parent_product_id = ?"""
        if only_active:
            sql += " AND a.active = 1"
        sql += " ORDER BY a.name COLLATE NOCASE"
        return [dict(r) for r in self.db.all(sql, (product_id,))]

    def add_addon(
        self,
        parent_product_id: int,
        *,
        name: str,
        extra_price: float = 0.0,
        component_product_id: int | None = None,
        component_qty: float = 0.0,
        created_by: int | None = None,
    ) -> int:
        """Crea un adicional. Si consume inventario, debe indicar
        component_product_id y component_qty > 0."""
        name = (name or "").strip()
        if not name:
            raise ProductError("El nombre del adicional es obligatorio.")
        if extra_price < 0:
            raise ProductError("El precio adicional no puede ser negativo.")
        if component_qty < 0:
            raise ProductError("La cantidad de componente no puede ser negativa.")

        # Si consume componente, se exige producto y cantidad > 0
        if component_product_id:
            if component_qty <= 0:
                raise ProductError(
                    "Si el adicional consume un producto, indique una cantidad mayor que cero."
                )
        else:
            component_qty = 0.0

        cur = self.db.conn.execute(
            """INSERT INTO product_addons(
                   parent_product_id, name, extra_price,
                   component_product_id, component_qty,
                   active, created_by, created_at
               ) VALUES(?,?,?,?,?,1,?,?)""",
            (
                parent_product_id, name, extra_price,
                component_product_id, component_qty,
                created_by, self._now(),
            ),
        )
        return int(cur.lastrowid)

    def update_addon(
        self,
        addon_id: int,
        *,
        name: str,
        extra_price: float,
        component_product_id: int | None = None,
        component_qty: float = 0.0,
    ) -> None:
        if extra_price < 0 or component_qty < 0:
            raise ProductError("Precio y cantidad deben ser >= 0.")
        if component_product_id and component_qty <= 0:
            raise ProductError(
                "Si el adicional consume un producto, la cantidad debe ser > 0."
            )
        if not component_product_id:
            component_qty = 0.0

        self.db.execute(
            """UPDATE product_addons
               SET name=?, extra_price=?, component_product_id=?, component_qty=?
               WHERE id=?""",
            (name, extra_price, component_product_id, component_qty, addon_id),
        )

    def deactivate_addon(self, addon_id: int) -> None:
        self.db.execute(
            "UPDATE product_addons SET active = 0 WHERE id = ?", (addon_id,)
        )

    # =========================================================================
    # Resolución de códigos de barras (POS)
    # =========================================================================
    def resolve_barcode(self, code: str) -> dict | None:
        """Resuelve un código escaneado.

        Devuelve un dict con:
          - kind: 'product' | 'presentation'
          - product: fila del producto
          - presentation: fila de presentación (o None)
          - effective_name, effective_price, effective_factor, effective_barcode
        """
        code = (code or "").strip()
        if not code:
            return None

        # 1) Presentación por barcode
        pres = self.get_presentation_by_barcode(code)
        if pres:
            product = self.get(int(pres["product_id"]))
            return {
                "kind": "presentation",
                "product": product,
                "presentation": pres,
                "effective_name": pres["name"],
                "effective_price": float(pres["sale_price"]),
                "effective_factor": float(pres["factor"]),
                "effective_barcode": pres["barcode"],
            }

        # 2) Producto por barcode o SKU
        product = self.get_by_barcode(code) or self.get_by_sku(code)
        if product and product.get("active"):
            return {
                "kind": "product",
                "product": product,
                "presentation": None,
                "effective_name": product["unit"] or "Unidad",
                "effective_price": float(product["sale_price"]),
                "effective_factor": 1.0,
                "effective_barcode": product["barcode"],
            }

        return None

    # =========================================================================
    # Helpers
    # =========================================================================
    @staticmethod
    def _now() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")