"""Esquema actual de la base de datos de vidPOS.

IMPORTANTE: este archivo define el estado ACTUAL del esquema.
Las migraciones incrementales están en migrations.py.
"""
from __future__ import annotations

# Versión del esquema. Incrementar al añadir migraciones nuevas.
SCHEMA_VERSION = 1


# ---------------------------------------------------------------------------
# DDL inicial (versión 1)
# ---------------------------------------------------------------------------
INITIAL_SCHEMA = """
-- ============================================================
-- USUARIOS Y SESIONES
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name       TEXT    NOT NULL,
    username        TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    password_hash   TEXT    NOT NULL,
    role            TEXT    NOT NULL CHECK(role IN ('admin','employee')),
    schedule_type   TEXT    NOT NULL DEFAULT '',
    active          INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
    must_change_password INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT    NOT NULL,
    updated_at      TEXT    NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS user_sessions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    login_at        TEXT    NOT NULL,
    logout_at       TEXT,
    logout_type     TEXT    NOT NULL DEFAULT '',
    ip_or_host      TEXT    NOT NULL DEFAULT '',
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_user_sessions_user    ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_login   ON user_sessions(login_at);

-- ============================================================
-- CATÁLOGO
-- ============================================================
CREATE TABLE IF NOT EXISTS categories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    active      INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    sku             TEXT    NOT NULL UNIQUE,
    barcode         TEXT    UNIQUE,
    name            TEXT    NOT NULL,
    category        TEXT    NOT NULL DEFAULT '',
    unit            TEXT    NOT NULL DEFAULT 'Unidad',
    sale_price      REAL    NOT NULL DEFAULT 0 CHECK(sale_price >= 0),
    min_stock       REAL    NOT NULL DEFAULT 0 CHECK(min_stock >= 0),
    product_type    TEXT    NOT NULL DEFAULT 'PRODUCT'
                            CHECK(product_type IN ('PRODUCT','SERVICE')),
    active          INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
    created_by      INTEGER,
    created_at      TEXT    NOT NULL,
    updated_at      TEXT    NOT NULL DEFAULT '',
    FOREIGN KEY(created_by) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_products_name     ON products(name);
CREATE INDEX IF NOT EXISTS idx_products_barcode  ON products(barcode);
CREATE INDEX IF NOT EXISTS idx_products_active   ON products(active);

CREATE TABLE IF NOT EXISTS product_presentations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id      INTEGER NOT NULL,
    name            TEXT    NOT NULL,
    factor          REAL    NOT NULL DEFAULT 1 CHECK(factor > 0),
    sale_price      REAL    NOT NULL DEFAULT 0 CHECK(sale_price >= 0),
    barcode         TEXT    UNIQUE,
    active          INTEGER NOT NULL DEFAULT 1,
    created_by      INTEGER,
    created_at      TEXT    NOT NULL,
    FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE,
    FOREIGN KEY(created_by) REFERENCES users(id),
    UNIQUE(product_id, name)
);

CREATE INDEX IF NOT EXISTS idx_presentations_product ON product_presentations(product_id);

CREATE TABLE IF NOT EXISTS product_addons (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_product_id       INTEGER NOT NULL,
    name                    TEXT    NOT NULL,
    extra_price             REAL    NOT NULL DEFAULT 0 CHECK(extra_price >= 0),
    component_product_id    INTEGER,
    component_qty           REAL    NOT NULL DEFAULT 0 CHECK(component_qty >= 0),
    active                  INTEGER NOT NULL DEFAULT 1,
    created_by              INTEGER,
    created_at              TEXT    NOT NULL,
    FOREIGN KEY(parent_product_id) REFERENCES products(id) ON DELETE CASCADE,
    FOREIGN KEY(component_product_id) REFERENCES products(id),
    FOREIGN KEY(created_by) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_addons_parent ON product_addons(parent_product_id);

-- ============================================================
-- COMPRAS / INVENTARIO
-- ============================================================
CREATE TABLE IF NOT EXISTS purchases (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier        TEXT    NOT NULL DEFAULT '',
    document_no     TEXT    NOT NULL DEFAULT '',
    total           REAL    NOT NULL DEFAULT 0,
    note            TEXT    NOT NULL DEFAULT '',
    created_by      INTEGER NOT NULL,
    created_at      TEXT    NOT NULL,
    FOREIGN KEY(created_by) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_purchases_created ON purchases(created_at);

CREATE TABLE IF NOT EXISTS purchase_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    purchase_id     INTEGER NOT NULL,
    product_id      INTEGER NOT NULL,
    qty             REAL    NOT NULL CHECK(qty > 0),
    unit_cost       REAL    NOT NULL CHECK(unit_cost >= 0),
    presentation_name TEXT  NOT NULL DEFAULT '',
    presentation_factor REAL NOT NULL DEFAULT 1,
    purchase_qty    REAL    NOT NULL DEFAULT 0,
    FOREIGN KEY(purchase_id) REFERENCES purchases(id) ON DELETE CASCADE,
    FOREIGN KEY(product_id) REFERENCES products(id)
);

CREATE INDEX IF NOT EXISTS idx_purchase_items_purchase ON purchase_items(purchase_id);
CREATE INDEX IF NOT EXISTS idx_purchase_items_product  ON purchase_items(product_id);

CREATE TABLE IF NOT EXISTS inventory_lots (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id          INTEGER NOT NULL,
    purchase_item_id    INTEGER,
    qty_received        REAL    NOT NULL CHECK(qty_received >= 0),
    qty_remaining       REAL    NOT NULL CHECK(qty_remaining >= 0),
    unit_cost           REAL    NOT NULL CHECK(unit_cost >= 0),
    created_at          TEXT    NOT NULL,
    FOREIGN KEY(product_id) REFERENCES products(id),
    FOREIGN KEY(purchase_item_id) REFERENCES purchase_items(id)
);

CREATE INDEX IF NOT EXISTS idx_lots_product_remaining
    ON inventory_lots(product_id, qty_remaining);
CREATE INDEX IF NOT EXISTS idx_lots_created ON inventory_lots(created_at);

CREATE TABLE IF NOT EXISTS inventory_movements (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id      INTEGER NOT NULL,
    movement_type   TEXT    NOT NULL,
    qty             REAL    NOT NULL,
    unit_cost       REAL,
    reference_type  TEXT    NOT NULL DEFAULT '',
    reference_id    INTEGER,
    note            TEXT    NOT NULL DEFAULT '',
    created_by      INTEGER,
    created_at      TEXT    NOT NULL,
    FOREIGN KEY(product_id) REFERENCES products(id),
    FOREIGN KEY(created_by) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_movements_product ON inventory_movements(product_id);
CREATE INDEX IF NOT EXISTS idx_movements_created ON inventory_movements(created_at);
CREATE INDEX IF NOT EXISTS idx_movements_type    ON inventory_movements(movement_type);

-- ============================================================
-- VENTAS
-- ============================================================
CREATE TABLE IF NOT EXISTS sales (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    total               REAL    NOT NULL CHECK(total >= 0),
    cost_total          REAL    NOT NULL DEFAULT 0,
    payment_method      TEXT    NOT NULL DEFAULT 'Efectivo',
    amount_received     REAL,
    change_given        REAL,
    status              TEXT    NOT NULL DEFAULT 'COMPLETED'
                                CHECK(status IN ('COMPLETED','VOIDED')),
    voided_by           INTEGER,
    voided_at           TEXT,
    void_reason         TEXT    NOT NULL DEFAULT '',
    created_by          INTEGER NOT NULL,
    cash_session_id     INTEGER,
    created_at          TEXT    NOT NULL,
    FOREIGN KEY(created_by) REFERENCES users(id),
    FOREIGN KEY(cash_session_id) REFERENCES cash_sessions(id),
    FOREIGN KEY(voided_by) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_sales_created       ON sales(created_at);
CREATE INDEX IF NOT EXISTS idx_sales_status        ON sales(status);
CREATE INDEX IF NOT EXISTS idx_sales_session       ON sales(cash_session_id);
CREATE INDEX IF NOT EXISTS idx_sales_user          ON sales(created_by);

CREATE TABLE IF NOT EXISTS sale_items (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id                 INTEGER NOT NULL,
    product_id              INTEGER NOT NULL,
    qty                     REAL    NOT NULL,
    sale_qty                REAL,
    unit_price              REAL    NOT NULL,
    display_unit_price      REAL,
    presentation_name       TEXT    NOT NULL DEFAULT '',
    presentation_factor     REAL    NOT NULL DEFAULT 1,
    cost_total              REAL    NOT NULL DEFAULT 0,
    FOREIGN KEY(sale_id) REFERENCES sales(id) ON DELETE CASCADE,
    FOREIGN KEY(product_id) REFERENCES products(id)
);

CREATE INDEX IF NOT EXISTS idx_sale_items_sale    ON sale_items(sale_id);
CREATE INDEX IF NOT EXISTS idx_sale_items_product ON sale_items(product_id);

CREATE TABLE IF NOT EXISTS sale_item_addons (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_item_id            INTEGER NOT NULL,
    addon_name              TEXT    NOT NULL,
    extra_price             REAL    NOT NULL DEFAULT 0,
    component_product_id    INTEGER,
    component_qty           REAL    NOT NULL DEFAULT 0,
    component_cost          REAL    NOT NULL DEFAULT 0,
    FOREIGN KEY(sale_item_id) REFERENCES sale_items(id) ON DELETE CASCADE,
    FOREIGN KEY(component_product_id) REFERENCES products(id)
);

CREATE INDEX IF NOT EXISTS idx_sale_addons_item ON sale_item_addons(sale_item_id);

CREATE TABLE IF NOT EXISTS sale_cost_allocations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_item_id    INTEGER NOT NULL,
    lot_id          INTEGER NOT NULL,
    qty             REAL    NOT NULL CHECK(qty > 0),
    unit_cost       REAL    NOT NULL CHECK(unit_cost >= 0),
    FOREIGN KEY(sale_item_id) REFERENCES sale_items(id) ON DELETE CASCADE,
    FOREIGN KEY(lot_id) REFERENCES inventory_lots(id)
);

CREATE INDEX IF NOT EXISTS idx_allocations_item ON sale_cost_allocations(sale_item_id);
CREATE INDEX IF NOT EXISTS idx_allocations_lot  ON sale_cost_allocations(lot_id);

-- ============================================================
-- CAJA
-- ============================================================
CREATE TABLE IF NOT EXISTS cash_sessions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER NOT NULL,
    opened_at           TEXT    NOT NULL,
    closed_at           TEXT,
    opening_amount      REAL    NOT NULL CHECK(opening_amount >= 0),
    counted_amount      REAL,
    expected_amount     REAL,
    difference          REAL,
    denominations_json  TEXT    NOT NULL DEFAULT '',
    note                TEXT    NOT NULL DEFAULT '',
    status              TEXT    NOT NULL DEFAULT 'OPEN'
                                CHECK(status IN ('OPEN','CLOSED')),
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_cash_user    ON cash_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_cash_status  ON cash_sessions(status);
CREATE INDEX IF NOT EXISTS idx_cash_opened  ON cash_sessions(opened_at);

CREATE TABLE IF NOT EXISTS cash_inflows (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    cash_session_id INTEGER NOT NULL,
    concept         TEXT    NOT NULL,
    amount          REAL    NOT NULL CHECK(amount > 0),
    note            TEXT    NOT NULL DEFAULT '',
    created_by      INTEGER NOT NULL,
    created_at      TEXT    NOT NULL,
    FOREIGN KEY(cash_session_id) REFERENCES cash_sessions(id),
    FOREIGN KEY(created_by) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_inflows_session ON cash_inflows(cash_session_id);

-- ============================================================
-- GASTOS
-- ============================================================
CREATE TABLE IF NOT EXISTS expenses (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    cash_session_id     INTEGER,
    description         TEXT    NOT NULL,
    amount              REAL    NOT NULL CHECK(amount > 0),
    category            TEXT    NOT NULL DEFAULT '',
    requested_by        INTEGER NOT NULL,
    requested_at        TEXT    NOT NULL,
    status              TEXT    NOT NULL DEFAULT 'PENDING'
                                CHECK(status IN ('PENDING','APPROVED','REJECTED')),
    approved_by         INTEGER,
    approved_at         TEXT,
    note                TEXT    NOT NULL DEFAULT '',
    FOREIGN KEY(cash_session_id) REFERENCES cash_sessions(id),
    FOREIGN KEY(requested_by) REFERENCES users(id),
    FOREIGN KEY(approved_by) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_expenses_session  ON expenses(cash_session_id);
CREATE INDEX IF NOT EXISTS idx_expenses_status   ON expenses(status);
CREATE INDEX IF NOT EXISTS idx_expenses_created  ON expenses(requested_at);

-- ============================================================
-- DEVOLUCIONES
-- ============================================================
CREATE TABLE IF NOT EXISTS sale_returns (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id         INTEGER NOT NULL,
    cash_session_id INTEGER,
    refund_method   TEXT    NOT NULL DEFAULT 'Efectivo',
    total_refund    REAL    NOT NULL DEFAULT 0,
    reason          TEXT    NOT NULL DEFAULT '',
    created_by      INTEGER NOT NULL,
    created_at      TEXT    NOT NULL,
    FOREIGN KEY(sale_id) REFERENCES sales(id),
    FOREIGN KEY(cash_session_id) REFERENCES cash_sessions(id),
    FOREIGN KEY(created_by) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_returns_sale    ON sale_returns(sale_id);
CREATE INDEX IF NOT EXISTS idx_returns_created ON sale_returns(created_at);

CREATE TABLE IF NOT EXISTS sale_return_items (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    return_id               INTEGER NOT NULL,
    sale_item_id            INTEGER NOT NULL,
    product_id              INTEGER NOT NULL,
    sale_qty_returned       REAL    NOT NULL DEFAULT 0,
    inventory_qty_returned  REAL    NOT NULL DEFAULT 0,
    refund_amount           REAL    NOT NULL DEFAULT 0,
    cost_amount             REAL    NOT NULL DEFAULT 0,
    FOREIGN KEY(return_id) REFERENCES sale_returns(id) ON DELETE CASCADE,
    FOREIGN KEY(sale_item_id) REFERENCES sale_items(id),
    FOREIGN KEY(product_id) REFERENCES products(id)
);

CREATE INDEX IF NOT EXISTS idx_return_items_return ON sale_return_items(return_id);

-- ============================================================
-- BORRADORES DE VENTA
-- ============================================================
CREATE TABLE IF NOT EXISTS pending_sale_drafts (
    user_id             INTEGER PRIMARY KEY,
    cash_session_id     INTEGER,
    cart_json           TEXT    NOT NULL DEFAULT '[]',
    payment_method      TEXT    NOT NULL DEFAULT 'Efectivo',
    amount_received     TEXT    NOT NULL DEFAULT '',
    updated_at          TEXT    NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(cash_session_id) REFERENCES cash_sessions(id)
);
"""