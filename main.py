
import os
import html
import webbrowser
import base64
import json
import sqlite3
import hashlib
import hmac
import secrets
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from pathlib import Path
import sys

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None

# En desarrollo, APP_DIR es la carpeta de main.py.
# En el ejecutable, APP_DIR es la carpeta donde está el .exe.
if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent
    RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))
else:
    APP_DIR = Path(__file__).resolve().parent
    RESOURCE_DIR = APP_DIR

DB_PATH = APP_DIR / "tienda_mejia.db"
LOGO_PATH = RESOURCE_DIR / "assets" / "logo_tienda_mejia.jpg"

COLORS = {
    "green": "#69B238",
    "red": "#E7342A",
    "yellow": "#F6C40E",
    "dark": "#222222",
    "light": "#F6F7F8",
    "white": "#FFFFFF",
    "gray": "#6B7280",
    "blue": "#2563EB",
}

def now_iso():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def hash_password(password: str):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000)
    return f"{salt}${digest.hex()}"

def verify_password(password: str, stored: str):
    try:
        salt, digest_hex = stored.split("$", 1)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000).hex()
        return hmac.compare_digest(digest, digest_hex)
    except Exception:
        return False

class DB:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        # Mayor resistencia ante cierres inesperados o cortes de energía.
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.execute("PRAGMA synchronous = FULL")
        self.conn.execute("PRAGMA busy_timeout = 5000")
        self.create_schema()
        self.seed_admin()

    def create_schema(self):
        self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin','employee')),
            schedule_type TEXT DEFAULT '',
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS user_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            login_at TEXT NOT NULL,
            logout_at TEXT,
            logout_type TEXT DEFAULT '',
            FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku TEXT NOT NULL UNIQUE,
            barcode TEXT UNIQUE,
            name TEXT NOT NULL,
            category TEXT DEFAULT '',
            unit TEXT DEFAULT 'Unidad',
            sale_price REAL NOT NULL DEFAULT 0,
            min_stock REAL NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            created_by INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY(created_by) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier TEXT DEFAULT '',
            document_no TEXT DEFAULT '',
            total REAL NOT NULL DEFAULT 0,
            created_by INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(created_by) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS purchase_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            purchase_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            qty REAL NOT NULL,
            unit_cost REAL NOT NULL,
            FOREIGN KEY(purchase_id) REFERENCES purchases(id),
            FOREIGN KEY(product_id) REFERENCES products(id)
        );

        CREATE TABLE IF NOT EXISTS inventory_lots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            purchase_item_id INTEGER,
            qty_received REAL NOT NULL,
            qty_remaining REAL NOT NULL,
            unit_cost REAL NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(product_id) REFERENCES products(id),
            FOREIGN KEY(purchase_item_id) REFERENCES purchase_items(id)
        );

        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            total REAL NOT NULL,
            cost_total REAL NOT NULL DEFAULT 0,
            payment_method TEXT NOT NULL DEFAULT 'Efectivo',
            created_by INTEGER NOT NULL,
            cash_session_id INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY(created_by) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS sale_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            qty REAL NOT NULL,
            unit_price REAL NOT NULL,
            cost_total REAL NOT NULL,
            FOREIGN KEY(sale_id) REFERENCES sales(id),
            FOREIGN KEY(product_id) REFERENCES products(id)
        );

        CREATE TABLE IF NOT EXISTS cash_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            opened_at TEXT NOT NULL,
            opening_amount REAL NOT NULL,
            closed_at TEXT,
            counted_amount REAL,
            expected_amount REAL,
            difference REAL,
            status TEXT NOT NULL DEFAULT 'OPEN' CHECK(status IN ('OPEN','CLOSED')),
            FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS cash_inflows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cash_session_id INTEGER NOT NULL,
            concept TEXT NOT NULL,
            amount REAL NOT NULL,
            note TEXT DEFAULT '',
            created_by INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(cash_session_id) REFERENCES cash_sessions(id),
            FOREIGN KEY(created_by) REFERENCES users(id)
        );

        CREATE INDEX IF NOT EXISTS idx_cash_inflows_session
        ON cash_inflows(cash_session_id);


        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE COLLATE NOCASE,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );



        CREATE TABLE IF NOT EXISTS product_addons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_product_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            extra_price REAL NOT NULL DEFAULT 0,
            component_product_id INTEGER,
            component_qty REAL NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            created_by INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY(parent_product_id) REFERENCES products(id),
            FOREIGN KEY(component_product_id) REFERENCES products(id),
            FOREIGN KEY(created_by) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS sale_item_addons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_item_id INTEGER NOT NULL,
            addon_name TEXT NOT NULL,
            extra_price REAL NOT NULL DEFAULT 0,
            component_product_id INTEGER,
            component_qty REAL NOT NULL DEFAULT 0,
            component_cost REAL NOT NULL DEFAULT 0,
            FOREIGN KEY(sale_item_id) REFERENCES sale_items(id),
            FOREIGN KEY(component_product_id) REFERENCES products(id)
        );

        CREATE TABLE IF NOT EXISTS product_presentations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            factor REAL NOT NULL DEFAULT 1,
            sale_price REAL NOT NULL DEFAULT 0,
            barcode TEXT UNIQUE,
            active INTEGER NOT NULL DEFAULT 1,
            created_by INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY(product_id) REFERENCES products(id),
            FOREIGN KEY(created_by) REFERENCES users(id),
            UNIQUE(product_id,name)
        );

        CREATE TABLE IF NOT EXISTS inventory_movements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            movement_type TEXT NOT NULL,
            qty REAL NOT NULL,
            unit_cost REAL,
            reference_type TEXT DEFAULT '',
            reference_id INTEGER,
            note TEXT DEFAULT '',
            created_by INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY(product_id) REFERENCES products(id),
            FOREIGN KEY(created_by) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS sale_cost_allocations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_item_id INTEGER NOT NULL,
            lot_id INTEGER NOT NULL,
            qty REAL NOT NULL,
            unit_cost REAL NOT NULL,
            FOREIGN KEY(sale_item_id) REFERENCES sale_items(id),
            FOREIGN KEY(lot_id) REFERENCES inventory_lots(id)
        );

        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cash_session_id INTEGER,
            description TEXT NOT NULL,
            amount REAL NOT NULL,
            requested_by INTEGER NOT NULL,
            requested_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING' CHECK(status IN ('PENDING','APPROVED','REJECTED')),
            approved_by INTEGER,
            approved_at TEXT,
            note TEXT DEFAULT '',
            FOREIGN KEY(cash_session_id) REFERENCES cash_sessions(id),
            FOREIGN KEY(requested_by) REFERENCES users(id),
            FOREIGN KEY(approved_by) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS pending_sale_drafts (
            user_id INTEGER PRIMARY KEY,
            cash_session_id INTEGER,
            cart_json TEXT NOT NULL DEFAULT '[]',
            payment_method TEXT NOT NULL DEFAULT 'Efectivo',
            amount_received TEXT DEFAULT '',
            updated_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(cash_session_id) REFERENCES cash_sessions(id)
        );

        CREATE TABLE IF NOT EXISTS sale_returns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER NOT NULL,
            cash_session_id INTEGER,
            refund_method TEXT NOT NULL DEFAULT 'Efectivo',
            total_refund REAL NOT NULL DEFAULT 0,
            reason TEXT NOT NULL DEFAULT '',
            created_by INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(sale_id) REFERENCES sales(id),
            FOREIGN KEY(cash_session_id) REFERENCES cash_sessions(id),
            FOREIGN KEY(created_by) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS sale_return_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            return_id INTEGER NOT NULL,
            sale_item_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            sale_qty_returned REAL NOT NULL DEFAULT 0,
            inventory_qty_returned REAL NOT NULL DEFAULT 0,
            refund_amount REAL NOT NULL DEFAULT 0,
            cost_amount REAL NOT NULL DEFAULT 0,
            FOREIGN KEY(return_id) REFERENCES sale_returns(id),
            FOREIGN KEY(sale_item_id) REFERENCES sale_items(id),
            FOREIGN KEY(product_id) REFERENCES products(id)
        );
        """)
        # Migraciones seguras para versiones nuevas sin perder la base existente.
        cash_cols = {r["name"] for r in self.conn.execute("PRAGMA table_info(cash_sessions)").fetchall()}
        if "denominations_json" not in cash_cols:
            self.conn.execute("ALTER TABLE cash_sessions ADD COLUMN denominations_json TEXT DEFAULT ''")
        sale_cols = {r["name"] for r in self.conn.execute("PRAGMA table_info(sales)").fetchall()}
        if "amount_received" not in sale_cols:
            self.conn.execute("ALTER TABLE sales ADD COLUMN amount_received REAL")
        if "change_given" not in sale_cols:
            self.conn.execute("ALTER TABLE sales ADD COLUMN change_given REAL")
        if "status" not in sale_cols:
            self.conn.execute("ALTER TABLE sales ADD COLUMN status TEXT NOT NULL DEFAULT 'COMPLETED'")
        if "voided_by" not in sale_cols:
            self.conn.execute("ALTER TABLE sales ADD COLUMN voided_by INTEGER")
        if "voided_at" not in sale_cols:
            self.conn.execute("ALTER TABLE sales ADD COLUMN voided_at TEXT")
        if "void_reason" not in sale_cols:
            self.conn.execute("ALTER TABLE sales ADD COLUMN void_reason TEXT DEFAULT ''")
        product_cols = {r["name"] for r in self.conn.execute("PRAGMA table_info(products)").fetchall()}
        if "product_type" not in product_cols:
            self.conn.execute("ALTER TABLE products ADD COLUMN product_type TEXT NOT NULL DEFAULT 'PRODUCT'")
        item_cols = {r["name"] for r in self.conn.execute("PRAGMA table_info(sale_items)").fetchall()}
        if "sale_qty" not in item_cols:
            self.conn.execute("ALTER TABLE sale_items ADD COLUMN sale_qty REAL")
        if "presentation_name" not in item_cols:
            self.conn.execute("ALTER TABLE sale_items ADD COLUMN presentation_name TEXT DEFAULT ''")
        if "presentation_factor" not in item_cols:
            self.conn.execute("ALTER TABLE sale_items ADD COLUMN presentation_factor REAL DEFAULT 1")
        if "display_unit_price" not in item_cols:
            self.conn.execute("ALTER TABLE sale_items ADD COLUMN display_unit_price REAL")
        self.conn.commit()

    def seed_admin(self):
        cur = self.conn.execute("SELECT COUNT(*) c FROM users")
        if cur.fetchone()["c"] == 0:
            self.conn.execute(
                "INSERT INTO users(full_name,username,password_hash,role,schedule_type,created_at) VALUES(?,?,?,?,?,?)",
                ("Gerente General", "admin", hash_password("admin123"), "admin", "Gerencia", now_iso())
            )
            self.conn.commit()

    def one(self, sql, params=()):
        return self.conn.execute(sql, params).fetchone()

    def all(self, sql, params=()):
        return self.conn.execute(sql, params).fetchall()

    def execute(self, sql, params=()):
        cur = self.conn.execute(sql, params)
        self.conn.commit()
        return cur

    def authenticate(self, username, password):
        row = self.one("SELECT * FROM users WHERE username=? AND active=1", (username,))
        if row and verify_password(password, row["password_hash"]):
            return row
        return None

    def current_stock(self, product_id):
        row = self.one("SELECT COALESCE(SUM(qty_remaining),0) stock FROM inventory_lots WHERE product_id=?", (product_id,))
        return float(row["stock"] or 0)

    def generate_sku(self):
        yy = datetime.now().strftime("%y")
        prefix = f"PRTM{yy}"
        rows = self.all("SELECT sku FROM products WHERE sku LIKE ?", (prefix + "%",))
        max_seq = 0
        for r in rows:
            sku = str(r["sku"] or "")
            if sku.startswith(prefix):
                tail = sku[len(prefix):]
                if tail.isdigit():
                    max_seq = max(max_seq, int(tail))
        return f"{prefix}{max_seq + 1:04d}"

    def ensure_category(self, name):
        name = (name or "").strip()
        if not name:
            return
        self.conn.execute(
            "INSERT OR IGNORE INTO categories(name,active,created_at) VALUES(?,1,?)",
            (name, now_iso())
        )

    def log_inventory(self, product_id, movement_type, qty, unit_cost=None,
                      reference_type="", reference_id=None, note="", created_by=None):
        self.conn.execute(
            """INSERT INTO inventory_movements(
                product_id,movement_type,qty,unit_cost,reference_type,reference_id,note,created_by,created_at
            ) VALUES(?,?,?,?,?,?,?,?,?)""",
            (product_id,movement_type,qty,unit_cost,reference_type,reference_id,note,created_by,now_iso())
        )

    def consume_fifo(self, product_id, qty):
        remaining = float(qty)
        cost = 0.0
        allocations = []
        lots = self.all("""
            SELECT * FROM inventory_lots
            WHERE product_id=? AND qty_remaining > 0
            ORDER BY created_at, id
        """, (product_id,))
        if sum(float(x["qty_remaining"]) for x in lots) + 1e-9 < remaining:
            raise ValueError("Inventario insuficiente.")
        for lot in lots:
            if remaining <= 0:
                break
            available = float(lot["qty_remaining"])
            take = min(available, remaining)
            unit_cost = float(lot["unit_cost"])
            cost += take * unit_cost
            self.conn.execute(
                "UPDATE inventory_lots SET qty_remaining = qty_remaining - ? WHERE id=?",
                (take, lot["id"])
            )
            allocations.append({"lot_id": lot["id"], "qty": take, "unit_cost": unit_cost})
            remaining -= take
        return cost, allocations

class TiendaMejiaApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Tienda Mejía POS")
        self.geometry("1280x760")
        self.minsize(1024, 640)
        try:
            self.state("zoomed")
        except Exception:
            pass
        self.configure(bg=COLORS["light"])
        self.db = DB()
        self.user = None
        self.cash_session = None
        self.current_login_id = None
        self.cart = []
        self.logo_img = None
        self._configure_styles()
        self.bind_class("Button", "<Return>", lambda e: e.widget.invoke(), add="+")
        try:
            self.bind_class("TButton", "<Return>", lambda e: e.widget.invoke(), add="+")
        except Exception:
            pass
        self.protocol("WM_DELETE_WINDOW", self.close_application)
        self.show_login()

    def _configure_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Treeview", rowheight=28, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
        style.configure("TNotebook.Tab", padding=(14, 8), font=("Segoe UI", 10, "bold"))

    def clear(self):
        for w in self.winfo_children():
            w.destroy()

    def header(self, parent):
        bar = tk.Frame(parent, bg=COLORS["white"], height=82, highlightthickness=1, highlightbackground="#E5E7EB")
        bar.pack(fill="x")
        bar.pack_propagate(False)

        if Image and LOGO_PATH.exists():
            img = Image.open(LOGO_PATH)
            img.thumbnail((150, 64))
            self.logo_img = ImageTk.PhotoImage(img)
            tk.Label(bar, image=self.logo_img, bg=COLORS["white"]).pack(side="left", padx=18)

        tk.Label(bar, text="Sistema de Gestión de Tienda", font=("Segoe UI", 18, "bold"),
                 bg=COLORS["white"], fg=COLORS["dark"]).pack(side="left", padx=10)

        right = tk.Frame(bar, bg=COLORS["white"])
        right.pack(side="right", padx=18)
        tk.Label(right, text=f"{self.user['full_name']} · {'Gerente' if self.user['role']=='admin' else 'Empleado'}",
                 bg=COLORS["white"], fg=COLORS["gray"], font=("Segoe UI", 10)).pack(anchor="e")
        tk.Button(right, text="Cerrar sesión", command=self.logout, bg=COLORS["red"], fg="white",
                  relief="flat", padx=14, pady=5).pack(anchor="e", pady=(4,0))

    def register_login(self):
        if not self.user:
            return
        cur=self.db.execute(
            "INSERT INTO user_sessions(user_id,login_at) VALUES(?,?)",
            (self.user["id"],now_iso())
        )
        self.current_login_id=cur.lastrowid

    def register_logout(self, logout_type="CERRAR SESION"):
        if self.current_login_id:
            try:
                self.db.execute(
                    """UPDATE user_sessions
                       SET logout_at=?,logout_type=?
                       WHERE id=? AND logout_at IS NULL""",
                    (now_iso(),logout_type,self.current_login_id)
                )
            except Exception:
                pass
        self.current_login_id=None

    def logout(self):
        self.register_logout("CERRAR SESION")
        self.show_login()

    def close_application(self):
        if self.user:
            self.register_logout("CIERRE APLICACION")
        try:
            self.db.conn.commit()
            self.db.conn.close()
        except Exception:
            pass
        self.destroy()

    def show_login(self):
        self.user = None
        self.cash_session = None
        self.clear()

        outer = tk.Frame(self, bg=COLORS["light"])
        outer.pack(fill="both", expand=True)

        card = tk.Frame(outer, bg=COLORS["white"], bd=0, highlightthickness=1, highlightbackground="#E5E7EB")
        card.place(relx=.5, rely=.5, anchor="center", width=430, height=520)

        if Image and LOGO_PATH.exists():
            img = Image.open(LOGO_PATH)
            img.thumbnail((210, 110))
            self.logo_img = ImageTk.PhotoImage(img)
            tk.Label(card, image=self.logo_img, bg=COLORS["white"]).pack(pady=(32, 8))

        tk.Label(card, text="Ingreso al sistema", font=("Segoe UI", 20, "bold"),
                 bg=COLORS["white"], fg=COLORS["dark"]).pack(pady=(8, 24))

        frm = tk.Frame(card, bg=COLORS["white"])
        frm.pack(fill="x", padx=55)

        tk.Label(frm, text="Usuario", bg=COLORS["white"], anchor="w", font=("Segoe UI", 10, "bold")).pack(fill="x")
        e_user = tk.Entry(frm, font=("Segoe UI", 12), relief="solid", bd=1)
        e_user.pack(fill="x", pady=(6, 16), ipady=8)

        tk.Label(frm, text="Contraseña", bg=COLORS["white"], anchor="w", font=("Segoe UI", 10, "bold")).pack(fill="x")
        e_pass = tk.Entry(frm, font=("Segoe UI", 12), relief="solid", bd=1, show="•")
        e_pass.pack(fill="x", pady=(6, 22), ipady=8)

        def login():
            user = self.db.authenticate(e_user.get().strip(), e_pass.get())
            if not user:
                messagebox.showerror("Acceso", "Usuario o contraseña incorrectos.")
                return
            self.user = user
            self.cart = []
            self.register_login()
            self.load_cash_session()
            self.show_main()

        tk.Button(frm, text="INGRESAR", command=login, bg=COLORS["green"], fg="white",
                  font=("Segoe UI", 11, "bold"), relief="flat", pady=10).pack(fill="x")

        tk.Label(card, text="Primer acceso: admin / admin123\nCambie la contraseña después de ingresar.",
                 bg=COLORS["white"], fg=COLORS["gray"], font=("Segoe UI", 9), justify="center").pack(pady=22)
        e_user.focus()
        self.bind("<Return>", lambda e: login())

    def load_cash_session(self):
        row = self.db.one("SELECT * FROM cash_sessions WHERE user_id=? AND status='OPEN' ORDER BY id DESC LIMIT 1",
                          (self.user["id"],))
        self.cash_session = row

    def show_main(self):
        self.unbind("<Return>")
        self.clear()
        self.header(self)

        # Layout responsivo: menú lateral fijo + área de trabajo.
        shell = tk.Frame(self, bg=COLORS["light"])
        shell.pack(fill="both", expand=True)

        sidebar = tk.Frame(shell, bg=COLORS["dark"], width=205)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        content = tk.Frame(shell, bg=COLORS["light"])
        content.pack(side="left", fill="both", expand=True, padx=14, pady=12)

        # Todas las páginas se crean una vez y se muestran desde el menú lateral.
        self.tab_dashboard = tk.Frame(content, bg=COLORS["light"])
        self.tab_sales = tk.Frame(content, bg=COLORS["light"])
        self.tab_products = tk.Frame(content, bg=COLORS["light"])
        self.tab_purchases = tk.Frame(content, bg=COLORS["light"])
        self.tab_cash = tk.Frame(content, bg=COLORS["light"])
        self.tab_expenses = tk.Frame(content, bg=COLORS["light"])

        pages = {
            "Inicio": self.tab_dashboard,
            "Ventas": self.tab_sales,
            "Productos": self.tab_products,
            "Compras": self.tab_purchases,
            "Caja": self.tab_cash,
            "Gastos": self.tab_expenses,
        }

        if self.user["role"] == "admin":
            self.tab_users = tk.Frame(content, bg=COLORS["light"])
            self.tab_returns = tk.Frame(content, bg=COLORS["light"])
            self.tab_finances = tk.Frame(content, bg=COLORS["light"])
            self.tab_reports = tk.Frame(content, bg=COLORS["light"])
            pages["Empleados"] = self.tab_users
            pages["Devoluciones"] = self.tab_returns
            pages["Finanzas"] = self.tab_finances
            pages["Reportes"] = self.tab_reports

        self._nav_pages = pages
        self._nav_buttons = {}

        def show_page(name):
            # Actualizar módulos cuyo contenido depende de movimientos recientes.
            # Así Caja nunca muestra una fotografía antigua del turno.
            try:
                if name=="Caja":
                    self.load_cash_session()
                    self.build_cash()
                elif name=="Inicio":
                    self.build_dashboard()
                elif name=="Finanzas" and self.user["role"]=="admin":
                    self.build_finances()
                elif name=="Reportes" and self.user["role"]=="admin":
                    self.build_reports()
            except Exception as e:
                page_err=self._nav_pages.get(name)
                if page_err is not None:
                    for child in page_err.winfo_children():
                        child.destroy()
                    tk.Label(
                        page_err,text=f"No se pudo actualizar {name}.",
                        bg=COLORS["light"],fg=COLORS["red"],
                        font=("Segoe UI",15,"bold")
                    ).pack(anchor="w",pady=(25,5))
                    tk.Label(
                        page_err,text=str(e),bg=COLORS["light"],fg=COLORS["gray"],
                        font=("Segoe UI",9),wraplength=850,justify="left"
                    ).pack(anchor="w")

            for page in self._nav_pages.values():
                page.pack_forget()
            page = self._nav_pages[name]
            page.pack(fill="both", expand=True)
            for n,b in self._nav_buttons.items():
                b.configure(bg=COLORS["green"] if n == name else COLORS["dark"])

        tk.Label(sidebar, text="MENÚ", bg=COLORS["dark"], fg="white",
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=18, pady=(18,10))

        for name in pages:
            b = tk.Button(
                sidebar, text=name, anchor="w", command=lambda n=name: show_page(n),
                bg=COLORS["dark"], fg="white", activebackground=COLORS["green"],
                activeforeground="white", relief="flat", bd=0,
                font=("Segoe UI", 10, "bold"), padx=18, pady=10
            )
            b.pack(fill="x", padx=8, pady=2)
            self._nav_buttons[name] = b

        tk.Frame(sidebar, bg=COLORS["dark"]).pack(fill="both", expand=True)
        tk.Label(sidebar, text="Tienda Mejía POS", bg=COLORS["dark"], fg="#D1D5DB",
                 font=("Segoe UI", 8)).pack(pady=(0,14))

        # Construcción de módulos
        self.build_dashboard()
        show_page("Inicio")

        modules=[
            ("Ventas",self.build_sales),
            ("Productos",self.build_products),
            ("Compras",self.build_purchases),
            ("Caja",self.build_cash),
            ("Gastos",self.build_expenses),
        ]
        if self.user["role"] == "admin":
            modules.extend([
                ("Empleados",self.build_users),
                ("Devoluciones",self.build_returns),
                ("Finanzas",self.build_finances),
                ("Reportes",self.build_reports),
            ])

        for module_name,builder in modules:
            try:
                builder()
            except Exception as e:
                page=self._nav_pages.get(module_name)
                if page is not None:
                    for child in page.winfo_children():
                        child.destroy()
                    tk.Label(
                        page,text=f"No se pudo cargar {module_name}.",
                        bg=COLORS["light"],fg=COLORS["red"],
                        font=("Segoe UI",15,"bold")
                    ).pack(anchor="w",pady=(25,5))
                    tk.Label(
                        page,text=str(e),bg=COLORS["light"],fg=COLORS["gray"],
                        font=("Segoe UI",9),wraplength=850,justify="left"
                    ).pack(anchor="w")
    def card(self, parent, title, value, col):
        f = tk.Frame(parent, bg=COLORS["white"], highlightthickness=1, highlightbackground="#E5E7EB")
        f.grid(row=0, column=col, sticky="nsew", padx=7)
        tk.Label(f, text=title, bg=COLORS["white"], fg=COLORS["gray"], font=("Segoe UI", 10)).pack(anchor="w", padx=16, pady=(14,4))
        tk.Label(f, text=value, bg=COLORS["white"], fg=COLORS["dark"], font=("Segoe UI", 22, "bold")).pack(anchor="w", padx=16, pady=(0,14))


    def show_app_modal(
        self,title,message,modal_type="info",
        primary_text="ACEPTAR",secondary_text=None,detail=None
    ):
        result={"value":False}

        win=tk.Toplevel(self)
        win.title(title)
        win.configure(bg="white")
        win.transient(self)
        win.grab_set()
        win.resizable(True,True)

        # Tamaño base más amplio y adaptable.
        screen_w=win.winfo_screenwidth()
        screen_h=win.winfo_screenheight()

        modal_w=min(720,max(560,int(screen_w*0.48)))
        modal_h=min(620,max(360,int(screen_h*0.68)))

        win.geometry(f"{modal_w}x{modal_h}")
        win.minsize(520,340)

        type_cfg={
            "success":("✓",COLORS["green"]),
            "warning":("!",COLORS["yellow"]),
            "error":("×",COLORS["red"]),
            "question":("?",COLORS["blue"]),
            "info":("i",COLORS["blue"]),
        }
        icon,accent=type_cfg.get(modal_type,type_cfg["info"])

        # ---------------- Encabezado ----------------
        header=tk.Frame(win,bg=accent,height=72)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(
            header,text=icon,
            bg=accent,fg="white",
            font=("Segoe UI",22,"bold")
        ).pack(side="left",padx=(18,10))

        tk.Label(
            header,text=title,
            bg=accent,fg="white",
            font=("Segoe UI",14,"bold"),
            anchor="w",justify="left",
            wraplength=max(360,modal_w-100)
        ).pack(side="left",fill="x",expand=True,pady=10,padx=(0,18))

        # ---------------- Cuerpo desplazable ----------------
        body_outer=tk.Frame(win,bg="white")
        body_outer.pack(fill="both",expand=True)

        canvas=tk.Canvas(
            body_outer,bg="white",
            highlightthickness=0,borderwidth=0
        )
        scrollbar=ttk.Scrollbar(
            body_outer,orient="vertical",command=canvas.yview
        )
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left",fill="both",expand=True)
        scrollbar.pack(side="right",fill="y")

        body=tk.Frame(canvas,bg="white")
        body_window=canvas.create_window(
            (0,0),window=body,anchor="nw"
        )

        def _sync_scrollregion(event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfigure(body_window,width=canvas.winfo_width())

        body.bind("<Configure>",_sync_scrollregion)
        canvas.bind("<Configure>",_sync_scrollregion)

        # Scroll con rueda del mouse solo dentro del modal.
        def _on_mousewheel(event):
            try:
                delta=-1 if event.delta>0 else 1
                canvas.yview_scroll(delta,"units")
            except Exception:
                pass

        canvas.bind("<MouseWheel>",_on_mousewheel)
        body.bind("<MouseWheel>",_on_mousewheel)

        # Texto principal.
        tk.Label(
            body,text=message,
            bg="white",fg=COLORS["dark"],
            font=("Segoe UI",10),
            justify="left",anchor="w",
            wraplength=max(420,modal_w-70)
        ).pack(fill="x",padx=24,pady=(22,10))

        # Detalle completo, con mejor legibilidad.
        if detail:
            detail_frame=tk.Frame(
                body,bg="#F8FAFC",
                highlightthickness=1,
                highlightbackground="#D1D5DB"
            )
            detail_frame.pack(
                fill="x",padx=24,pady=(0,16)
            )

            detail_text=tk.Text(
                detail_frame,
                wrap="word",
                bg="#F8FAFC",
                fg=COLORS["dark"],
                font=("Consolas",9),
                relief="flat",
                borderwidth=0,
                padx=12,pady=10,
                height=10
            )
            detail_text.pack(fill="both",expand=True)

            detail_text.insert("1.0",str(detail))
            detail_text.configure(state="disabled")

            # Ajustar altura aproximada del bloque sin crecer indefinidamente.
            lines=max(
                len(str(detail).splitlines()),
                int(len(str(detail))/70)+1
            )
            detail_text.configure(height=min(max(lines,5),16))

            # Permitir scroll dentro del bloque de detalle.
            def _detail_scroll(event):
                try:
                    delta=-1 if event.delta>0 else 1
                    detail_text.yview_scroll(delta,"units")
                    return "break"
                except Exception:
                    return None

            detail_text.bind("<MouseWheel>",_detail_scroll)

        # Espacio inferior para que el último contenido nunca quede pegado
        # a la barra de botones.
        tk.Frame(body,bg="white",height=8).pack()

        # ---------------- Botones fijos ----------------
        footer=tk.Frame(win,bg="#F3F4F6")
        footer.pack(side="bottom",fill="x")

        button_box=tk.Frame(footer,bg="#F3F4F6")
        button_box.pack(side="right",padx=18,pady=12)

        def close_with(value):
            result["value"]=value
            try:
                win.grab_release()
            except Exception:
                pass
            win.destroy()

        if secondary_text:
            tk.Button(
                button_box,text=secondary_text,
                command=lambda:close_with(False),
                bg="#E5E7EB",fg=COLORS["dark"],
                font=("Segoe UI",9,"bold"),
                relief="flat",padx=16,pady=7
            ).pack(side="left",padx=(0,8))

        tk.Button(
            button_box,text=primary_text,
            command=lambda:close_with(True),
            bg=accent,fg="white",
            font=("Segoe UI",9,"bold"),
            relief="flat",padx=18,pady=7
        ).pack(side="left")

        # ---------------- Centrado ----------------
        win.update_idletasks()
        x=max(0,(screen_w-win.winfo_width())//2)
        y=max(0,(screen_h-win.winfo_height())//2)
        win.geometry(f"+{x}+{y}")

        # Atajos de teclado.
        win.bind("<Escape>",lambda e:close_with(False))
        win.bind("<Return>",lambda e:close_with(True))

        # Llevar al inicio por defecto.
        canvas.yview_moveto(0)

        self.wait_window(win)
        return result["value"]


    def build_dashboard(self):
        for w in self.tab_dashboard.winfo_children(): w.destroy()
        top = tk.Frame(self.tab_dashboard, bg=COLORS["light"])
        top.pack(fill="x", pady=8)
        for i in range(4): top.grid_columnconfigure(i, weight=1)

        today = datetime.now().strftime("%Y-%m-%d")
        s = self.db.one("SELECT COALESCE(SUM(total),0) v, COALESCE(SUM(cost_total),0) c FROM sales WHERE date(created_at)=? AND status='COMPLETED'", (today,))
        sales = float(s["v"] or 0); cost = float(s["c"] or 0)
        returned=self.db.one(
            "SELECT COALESCE(SUM(total_refund),0) r FROM sale_returns WHERE date(created_at)=?",
            (today,)
        )
        returned_total=float(returned["r"] or 0)
        sales_net=sales-returned_total
        pending = self.db.one("SELECT COUNT(*) c FROM expenses WHERE status='PENDING'")["c"]
        low = 0
        for p in self.db.all("SELECT id,min_stock FROM products WHERE active=1"):
            if self.db.current_stock(p["id"]) <= float(p["min_stock"]): low += 1

        self.card(top, "Ventas netas hoy", f"${sales_net:,.2f}", 0)
        self.card(top, "Devoluciones hoy", f"${returned_total:,.2f}", 1)
        self.card(top, "Gastos pendientes", str(pending), 2)
        self.card(top, "Stock bajo", str(low), 3)

        info = tk.Frame(self.tab_dashboard, bg=COLORS["white"], highlightthickness=1, highlightbackground="#E5E7EB")
        info.pack(fill="x", padx=7, pady=18)
        status = "Caja abierta" if self.cash_session else "Caja cerrada"
        txt = f"Usuario: {self.user['full_name']}   |   Estado: {status}"
        if self.cash_session:
            txt += f"   |   Fondo inicial: ${float(self.cash_session['opening_amount']):,.2f}"
        tk.Label(info, text=txt, bg=COLORS["white"], fg=COLORS["dark"], font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=18, pady=18)

    def build_products(self):
        for w in self.tab_products.winfo_children(): w.destroy()

        top = tk.Frame(self.tab_products, bg=COLORS["light"])
        top.pack(fill="x", pady=8)
        tk.Label(top, text="Productos", font=("Segoe UI", 18, "bold"), bg=COLORS["light"]).pack(side="left")
        tk.Button(top, text="+ Nuevo producto", bg=COLORS["green"], fg="white", relief="flat",
                  command=self.add_product).pack(side="right", padx=6)

        searchbar=tk.Frame(self.tab_products,bg=COLORS["light"]);searchbar.pack(fill="x",pady=(0,8))
        tk.Label(searchbar,text="Buscar por nombre:",bg=COLORS["light"],font=("Segoe UI",9,"bold")).pack(side="left")
        search_var=tk.StringVar()
        search=tk.Entry(searchbar,textvariable=search_var,font=("Segoe UI",11),width=35)
        search.pack(side="left",padx=8,ipady=4)

        cols = ("id","sku","barcode","name","type","category","price","sold","stock","min")
        tree = ttk.Treeview(self.tab_products, columns=cols, show="headings")
        heads = ["ID","Código","Código barras","Producto","Tipo","Categoría","Precio venta","Vendido","Existencia","Mínimo"]
        widths = [45,105,115,195,85,105,85,80,90,75]
        for c,h,w in zip(cols,heads,widths):
            tree.heading(c,text=h); tree.column(c, width=w)
        tree.pack(fill="both", expand=True, pady=8)

        def load_products(*_):
            for item in tree.get_children(): tree.delete(item)
            term=search_var.get().strip()
            if term:
                rows=self.db.all("SELECT * FROM products WHERE active=1 AND name LIKE ? ORDER BY name",("%"+term+"%",))
            else:
                rows=self.db.all("SELECT * FROM products WHERE active=1 ORDER BY name")
            for p in rows:
                # Vendido = cantidad efectivamente vendida.
                # Para productos inventariables usamos unidades base descontadas.
                # Para servicios usamos la cantidad de servicios vendidos.
                sold=self.db.one(
                    """SELECT COALESCE(SUM(
                           CASE
                             WHEN p2.product_type='SERVICE'
                             THEN COALESCE(si.sale_qty,1)
                             ELSE si.qty
                           END
                       ),0) AS total_sold
                       FROM sale_items si
                       JOIN sales s ON s.id=si.sale_id
                       JOIN products p2 ON p2.id=si.product_id
                       WHERE si.product_id=? AND s.status='COMPLETED'""",
                    (p["id"],)
                )
                sold_qty=float(sold["total_sold"] or 0) if sold else 0.0
                is_service=(p["product_type"]=="SERVICE")
                tree.insert("", "end", values=(
                    p["id"],p["sku"],p["barcode"] or "",p["name"],
                    "Servicio" if is_service else "Producto",
                    p["category"] or "",
                    f"${float(p['sale_price']):.2f}",
                    f"{sold_qty:.2f}",
                    "-" if is_service else f"{self.db.current_stock(p['id']):.2f}",
                    "-" if is_service else f"{float(p['min_stock']):.2f}"
                ))
        search_var.trace_add("write",load_products)
        load_products()

        actions=tk.Frame(self.tab_products,bg=COLORS["light"]);actions.pack(fill="x")
        def edit_selected():
            sel=tree.selection()
            if not sel:
                messagebox.showwarning("Productos","Seleccione un producto.")
                return
            product_id=int(tree.item(sel[0],"values")[0])
            self.product_form(product_id)
        tk.Button(
            actions,text="Modificar producto",command=edit_selected,
            bg=COLORS["blue"],fg="white",relief="flat",padx=16,pady=7
        ).pack(side="left",padx=5)
        def delete_selected():
            sel=tree.selection()
            if not sel:
                self.show_app_modal(
                    "Seleccione un producto",
                    "Debe seleccionar el producto que desea eliminar.",
                    modal_type="warning",
                    primary_text="ACEPTAR"
                )
                return

            product_id=int(tree.item(sel[0],"values")[0])
            product=self.db.one("SELECT * FROM products WHERE id=?",(product_id,))
            if not product:
                return

            # Verificar si el producto participa en el historial operativo.
            sales_count=int(self.db.one(
                "SELECT COUNT(*) c FROM sale_items WHERE product_id=?",(product_id,)
            )["c"])
            purchase_count=int(self.db.one(
                "SELECT COUNT(*) c FROM purchase_items WHERE product_id=?",(product_id,)
            )["c"])
            movement_count=int(self.db.one(
                "SELECT COUNT(*) c FROM inventory_movements WHERE product_id=?",(product_id,)
            )["c"])
            lot_count=int(self.db.one(
                "SELECT COUNT(*) c FROM inventory_lots WHERE product_id=?",(product_id,)
            )["c"])

            if sales_count or purchase_count or movement_count or lot_count:
                if not self.show_app_modal(
                    "Producto con historial",
                    f"{product['name']} ya forma parte del historial de la tienda.",
                    modal_type="warning",
                    primary_text="DESACTIVAR",
                    secondary_text="VOLVER",
                    detail=(
                        "Para proteger ventas, compras, inventario y reportes anteriores, "
                        "no se eliminará físicamente. Se marcará como inactivo y dejará "
                        "de aparecer para nuevas operaciones."
                    )
                ):
                    return
                try:
                    self.db.execute("UPDATE products SET active=0 WHERE id=?",(product_id,))
                    self.show_app_modal(
                        "Producto desactivado",
                        f"{product['name']} ya no aparecerá en las operaciones activas.",
                        modal_type="success",
                        primary_text="ACEPTAR"
                    )
                    self.build_products()
                    self.build_sales()
                except Exception as e:
                    self.show_app_modal(
                        "No se pudo desactivar",
                        str(e),
                        modal_type="error",
                        primary_text="ACEPTAR"
                    )
                return

            if not self.show_app_modal(
                "Eliminar producto",
                f"¿Desea eliminar definitivamente {product['name']}?",
                modal_type="question",
                primary_text="ELIMINAR",
                secondary_text="VOLVER",
                detail="Este producto no tiene historial de ventas, compras ni movimientos."
            ):
                return

            try:
                # Eliminar configuraciones dependientes sin historial.
                self.db.conn.execute("DELETE FROM product_presentations WHERE product_id=?",(product_id,))
                self.db.conn.execute("DELETE FROM product_addons WHERE product_id=?",(product_id,))
                self.db.conn.execute("DELETE FROM products WHERE id=?",(product_id,))
                self.db.conn.commit()
                self.show_app_modal(
                    "Producto eliminado",
                    f"{product['name']} fue eliminado correctamente.",
                    modal_type="success",
                    primary_text="ACEPTAR"
                )
                self.build_products()
                self.build_sales()
            except Exception as e:
                self.db.conn.rollback()
                self.show_app_modal(
                    "No se pudo eliminar",
                    str(e),
                    modal_type="error",
                    primary_text="ACEPTAR"
                )

        if self.user["role"]=="admin":
            tk.Button(
                actions,text="ELIMINAR PRODUCTO",command=delete_selected,
                bg=COLORS["red"],fg="white",font=("Segoe UI",9,"bold"),
                relief="flat",padx=16,pady=7
            ).pack(side="left",padx=5)

        def selected_product_id():
            sel=tree.selection()
            if not sel:
                messagebox.showwarning("Productos","Seleccione un producto.")
                return None
            return int(tree.item(sel[0],"values")[0])

        def manage_presentations():
            pid=selected_product_id()
            if pid:self.presentation_manager(pid)

        def inventory_move():
            pid=selected_product_id()
            if pid:self.inventory_movement_form(pid)

        tk.Button(
            actions,text="Presentaciones",command=manage_presentations,
            bg=COLORS["green"],fg="white",relief="flat",padx=16,pady=7
        ).pack(side="left",padx=5)

        def manage_addons():
            pid=selected_product_id()
            if pid:self.addon_manager(pid)

        tk.Button(
            actions,text="Adicionales",command=manage_addons,
            bg=COLORS["blue"],fg="white",relief="flat",padx=16,pady=7
        ).pack(side="left",padx=5)
        tk.Button(actions,text="Movimiento / Historial",command=inventory_move,bg=COLORS["yellow"],fg=COLORS["dark"],
                  relief="flat",padx=16,pady=7).pack(side="left",padx=5)
        if self.user["role"]!="admin":
            tk.Label(
                actions,
                text="Empleado: puede administrar productos; eliminar productos requiere Gerencia.",
                bg=COLORS["light"],fg=COLORS["gray"],font=("Segoe UI",8)
            ).pack(side="right",padx=8)

    def add_product(self):
        self.product_form()

    def product_form(self, product_id=None):
        existing=self.db.one("SELECT * FROM products WHERE id=?",(product_id,)) if product_id else None
        win = tk.Toplevel(self)
        win.title("Modificar producto" if existing else "Nuevo producto")
        win.geometry("520x680"); win.minsize(480,620)
        win.transient(self); win.grab_set()

        outer=tk.Frame(win,bg=COLORS["white"]);outer.pack(fill="both",expand=True)
        canvas=tk.Canvas(outer,bg=COLORS["white"],highlightthickness=0)
        scroll=ttk.Scrollbar(outer,orient="vertical",command=canvas.yview)
        box=tk.Frame(canvas,bg=COLORS["white"],padx=30,pady=22)
        box_id=canvas.create_window((0,0),window=box,anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left",fill="both",expand=True);scroll.pack(side="right",fill="y")
        canvas.bind("<Configure>",lambda e: canvas.itemconfigure(box_id,width=e.width))
        box.bind("<Configure>",lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        tk.Label(box,text="Modificar producto" if existing else "Registrar producto",
                 font=("Segoe UI",17,"bold"),bg=COLORS["white"]).pack(anchor="w",pady=(0,16))

        tk.Label(box,text="Tipo",bg=COLORS["white"],font=("Segoe UI",9,"bold")).pack(anchor="w")
        product_type=ttk.Combobox(box,state="readonly",values=["PRODUCT","SERVICE"],font=("Segoe UI",10))
        product_type.pack(fill="x",pady=(4,11))
        product_type.set(existing["product_type"] if existing and "product_type" in existing.keys() else "PRODUCT")
        tk.Label(box,text="PRODUCT = controla inventario · SERVICE = no maneja existencias",
                 bg=COLORS["white"],fg=COLORS["gray"],font=("Segoe UI",8)).pack(anchor="w",pady=(0,8))

        entries={}
        def label_entry(label,key,value="",readonly=False):
            tk.Label(box,text=label,bg=COLORS["white"],font=("Segoe UI",9,"bold")).pack(anchor="w")
            e=tk.Entry(box,font=("Segoe UI",11),relief="solid",bd=1)
            e.pack(fill="x",pady=(4,11),ipady=6);e.insert(0,value)
            if readonly:e.configure(state="readonly")
            entries[key]=e

        auto_sku = existing["sku"] if existing else self.db.generate_sku()
        label_entry("Código interno automático","sku",auto_sku,True)
        label_entry("Código de barras","barcode",(existing["barcode"] or "") if existing else "")
        label_entry("Nombre *","name",existing["name"] if existing else "")

        tk.Label(box,text="Categoría",bg=COLORS["white"],font=("Segoe UI",9,"bold")).pack(anchor="w")
        categories=[r["name"] for r in self.db.all("SELECT name FROM categories WHERE active=1 ORDER BY name")]
        category=ttk.Combobox(box,values=categories,state="normal",font=("Segoe UI",11))
        category.pack(fill="x",pady=(4,11))
        if existing: category.set(existing["category"] or "")
        tk.Label(box,text="Puede seleccionar una categoría existente o escribir una nueva.",
                 bg=COLORS["white"],fg=COLORS["gray"],font=("Segoe UI",8)).pack(anchor="w",pady=(0,9))

        label_entry("Unidad","unit",existing["unit"] if existing else "Unidad")
        label_entry("Precio de venta *","sale_price",str(existing["sale_price"]) if existing else "")
        label_entry("Stock mínimo","min_stock",str(existing["min_stock"]) if existing else "0")

        tk.Label(box,text="La existencia se modifica mediante compras/entradas, no desde este formulario.",
                 bg=COLORS["white"],fg=COLORS["gray"],font=("Segoe UI",9),
                 wraplength=430,justify="left").pack(anchor="w",pady=(0,12))

        def save():
            try:
                sku=existing["sku"] if existing else auto_sku
                name=entries["name"].get().strip()
                price=float(entries["sale_price"].get())
                minst=float(entries["min_stock"].get() or 0)
                barcode=entries["barcode"].get().strip() or None
                cat=category.get().strip()
                if not name or price < 0 or minst < 0: raise ValueError
                self.db.ensure_category(cat)
                ptype=product_type.get() or "PRODUCT"
                params=(sku,barcode,name,cat,entries["unit"].get().strip() or "Unidad",price,minst,ptype)
                if existing:
                    self.db.execute("""UPDATE products SET sku=?,barcode=?,name=?,category=?,unit=?,sale_price=?,min_stock=?,product_type=? WHERE id=?""",
                                    params+(existing["id"],))
                    messagebox.showinfo("Producto","Producto actualizado correctamente.")
                else:
                    self.db.execute("""INSERT INTO products(sku,barcode,name,category,unit,sale_price,min_stock,product_type,created_by,created_at)
                                       VALUES(?,?,?,?,?,?,?,?,?,?)""",params+(self.user["id"],now_iso()))
                    messagebox.showinfo("Producto",f"Producto registrado.\nCódigo asignado: {sku}")
                win.destroy();self.build_products();self.build_dashboard();self.build_sales()
            except sqlite3.IntegrityError:
                messagebox.showerror("Producto","El código de barras ya existe o ocurrió un conflicto con el código.")
            except Exception:
                messagebox.showerror("Producto","Revise los datos obligatorios y valores numéricos.")

        buttons=tk.Frame(box,bg=COLORS["white"]);buttons.pack(fill="x",pady=(10,18))
        tk.Button(buttons,text="GUARDAR CAMBIOS" if existing else "GUARDAR PRODUCTO",
                  command=save,bg=COLORS["green"],fg="white",font=("Segoe UI",10,"bold"),
                  relief="flat",pady=11).pack(side="left",fill="x",expand=True,padx=(0,6))
        tk.Button(buttons,text="Cancelar",command=win.destroy,bg="#E5E7EB",fg=COLORS["dark"],
                  relief="flat",pady=11).pack(side="left",fill="x",expand=True,padx=(6,0))


    def addon_manager(self, product_id):
        product=self.db.one("SELECT * FROM products WHERE id=?",(product_id,))
        if not product:return

        win=tk.Toplevel(self);win.title(f"Adicionales - {product['name']}")
        win.geometry("760x540");win.minsize(700,500);win.transient(self);win.grab_set()
        box=tk.Frame(win,padx=18,pady=16);box.pack(fill="both",expand=True)

        tk.Label(box,text=f"Adicionales de {product['name']}",font=("Segoe UI",16,"bold")).pack(anchor="w")
        tk.Label(box,text="Un adicional puede ser solo servicio o también consumir otro producto del inventario.",
                 fg=COLORS["gray"],font=("Segoe UI",9)).pack(anchor="w",pady=(2,12))

        cols=("id","name","price","component","qty")
        tree=ttk.Treeview(box,columns=cols,show="headings")
        for c,h,w in [("id","ID",45),("name","Adicional",220),("price","Precio extra",100),
                      ("component","Producto que consume",240),("qty","Cantidad",90)]:
            tree.heading(c,text=h);tree.column(c,width=w)
        tree.pack(fill="both",expand=True)

        def load():
            for x in tree.get_children():tree.delete(x)
            rows=self.db.all("""SELECT a.*,p.name component_name
                                FROM product_addons a
                                LEFT JOIN products p ON p.id=a.component_product_id
                                WHERE a.parent_product_id=? AND a.active=1 ORDER BY a.name""",(product_id,))
            for r in rows:
                tree.insert("","end",values=(r["id"],r["name"],f"${float(r['extra_price']):.2f}",
                                             r["component_name"] or "Solo servicio",
                                             f"{float(r['component_qty']):g}"))
        load()

        def form(edit_id=None):
            existing=self.db.one("SELECT * FROM product_addons WHERE id=?",(edit_id,)) if edit_id else None
            fw=tk.Toplevel(win);fw.title("Modificar adicional" if existing else "Nuevo adicional")
            fw.geometry("470x520");fw.transient(win);fw.grab_set()
            f=tk.Frame(fw,padx=22,pady=18);f.pack(fill="both",expand=True)

            tk.Label(f,text="Nombre *",font=("Segoe UI",9,"bold")).pack(anchor="w")
            name=tk.Entry(f,font=("Segoe UI",11));name.pack(fill="x",pady=(4,10),ipady=5)
            if existing:name.insert(0,existing["name"])

            tk.Label(f,text="Precio adicional *",font=("Segoe UI",9,"bold")).pack(anchor="w")
            extra=tk.Entry(f,font=("Segoe UI",11));extra.pack(fill="x",pady=(4,10),ipady=5)
            extra.insert(0,str(existing["extra_price"]) if existing else "0")

            inventory_products=self.db.all(
                "SELECT id,sku,name FROM products WHERE active=1 AND product_type='PRODUCT' ORDER BY name"
            )
            choices=["Solo servicio / no consume inventario"]+[f"{p['sku']} — {p['name']}" for p in inventory_products]

            tk.Label(f,text="Producto que consume",font=("Segoe UI",9,"bold")).pack(anchor="w")
            component=ttk.Combobox(f,state="readonly",values=choices)
            component.pack(fill="x",pady=(4,10));component.current(0)

            if existing and existing["component_product_id"]:
                for idx,p in enumerate(inventory_products,1):
                    if p["id"]==existing["component_product_id"]:
                        component.current(idx);break

            tk.Label(f,text="Cantidad que consume",font=("Segoe UI",9,"bold")).pack(anchor="w")
            component_qty=tk.Entry(f,font=("Segoe UI",11));component_qty.pack(fill="x",pady=(4,10),ipady=5)
            component_qty.insert(0,str(existing["component_qty"]) if existing else "0")

            tk.Label(f,text="Ejemplos:\nPreparación: precio 0.25, sin producto.\nCremora: precio 0.10, producto Cremora, cantidad 1.",
                     fg=COLORS["gray"],font=("Segoe UI",8),justify="left").pack(anchor="w",pady=(0,12))

            def save():
                try:
                    n=name.get().strip();price=float(extra.get());cq=float(component_qty.get() or 0)
                    if not n or price<0 or cq<0:raise ValueError
                    comp_id=None
                    idx=component.current()
                    if idx>0:
                        comp_id=inventory_products[idx-1]["id"]
                        if cq<=0:
                            messagebox.showwarning("Adicional","Si consume un producto, indique una cantidad mayor que cero.")
                            return
                    else:
                        cq=0
                    if existing:
                        self.db.execute("""UPDATE product_addons SET name=?,extra_price=?,component_product_id=?,component_qty=?
                                           WHERE id=?""",(n,price,comp_id,cq,existing["id"]))
                    else:
                        self.db.execute("""INSERT INTO product_addons(
                            parent_product_id,name,extra_price,component_product_id,component_qty,active,created_by,created_at
                        ) VALUES(?,?,?,?,?,1,?,?)""",(product_id,n,price,comp_id,cq,self.user["id"],now_iso()))
                    fw.destroy();load()
                except Exception:
                    messagebox.showerror("Adicional","Revise los datos del adicional.")

            tk.Button(f,text="GUARDAR",command=save,bg=COLORS["green"],fg="white",
                      relief="flat",pady=9).pack(fill="x",pady=8)

        actions=tk.Frame(box);actions.pack(fill="x",pady=10)
        def selected_id():
            sel=tree.selection()
            return int(tree.item(sel[0],"values")[0]) if sel else None
        tk.Button(actions,text="+ Nuevo",command=lambda:form(),bg=COLORS["green"],fg="white",
                  relief="flat",padx=14,pady=7).pack(side="left",padx=4)
        tk.Button(actions,text="Modificar",command=lambda:(form(selected_id()) if selected_id() else None),
                  bg=COLORS["blue"],fg="white",relief="flat",padx=14,pady=7).pack(side="left",padx=4)
        def delete():
            sid=selected_id()
            if sid and messagebox.askyesno("Adicional","¿Desactivar este adicional?"):
                self.db.execute("UPDATE product_addons SET active=0 WHERE id=?",(sid,));load()
        tk.Button(actions,text="Eliminar",command=delete,bg=COLORS["red"],fg="white",
                  relief="flat",padx=14,pady=7).pack(side="left",padx=4)

    def presentation_manager(self, product_id):
        product=self.db.one("SELECT * FROM products WHERE id=?",(product_id,))
        if not product:return

        win=tk.Toplevel(self); win.title(f"Presentaciones - {product['name']}")
        win.geometry("680x520"); win.minsize(620,470); win.transient(self); win.grab_set()
        box=tk.Frame(win,padx=18,pady=16); box.pack(fill="both",expand=True)

        tk.Label(box,text=f"Presentaciones de {product['name']}",
                 font=("Segoe UI",16,"bold")).pack(anchor="w")
        tk.Label(box,text=f"Unidad base: {product['unit']} · Precio base: ${float(product['sale_price']):.2f}",
                 fg=COLORS["gray"],font=("Segoe UI",9)).pack(anchor="w",pady=(2,12))

        cols=("id","name","factor","price","barcode")
        tree=ttk.Treeview(box,columns=cols,show="headings")
        for c,h,w in [("id","ID",45),("name","Presentación",220),("factor","Equivale a",100),
                      ("price","Precio",100),("barcode","Código barras",160)]:
            tree.heading(c,text=h);tree.column(c,width=w)
        tree.pack(fill="both",expand=True)

        def load():
            for x in tree.get_children():tree.delete(x)
            for r in self.db.all("""SELECT * FROM product_presentations
                                    WHERE product_id=? AND active=1 ORDER BY factor,name""",(product_id,)):
                tree.insert("","end",values=(r["id"],r["name"],f"{float(r['factor']):g}",
                                             f"${float(r['sale_price']):.2f}",r["barcode"] or ""))
        load()

        actions=tk.Frame(box);actions.pack(fill="x",pady=10)

        def form(edit_id=None):
            existing=self.db.one("SELECT * FROM product_presentations WHERE id=?",(edit_id,)) if edit_id else None
            fw=tk.Toplevel(win);fw.title("Modificar presentación" if existing else "Nueva presentación")
            fw.geometry("410x430");fw.transient(win);fw.grab_set()
            f=tk.Frame(fw,padx=22,pady=18);f.pack(fill="both",expand=True)

            def ent(label,value=""):
                tk.Label(f,text=label,font=("Segoe UI",9,"bold")).pack(anchor="w")
                e=tk.Entry(f,font=("Segoe UI",11));e.pack(fill="x",pady=(4,10),ipady=5);e.insert(0,value);return e

            name=ent("Nombre de presentación *",existing["name"] if existing else "")
            factor=ent(f"Cantidad de {product['unit']} que descuenta *",
                       str(existing["factor"]) if existing else "1")
            price=ent("Precio de venta de esta presentación *",
                      str(existing["sale_price"]) if existing else str(product["sale_price"]))
            barcode=ent("Código de barras opcional",existing["barcode"] or "" if existing else "")

            tk.Label(f,text="Ejemplos: Bolsón = 25 unidades; Preparada = 1 unidad.",
                     fg=COLORS["gray"],font=("Segoe UI",8),wraplength=350,justify="left").pack(anchor="w",pady=(0,12))

            def save():
                try:
                    n=name.get().strip(); fac=float(factor.get()); pr=float(price.get())
                    # El código de barras es realmente opcional. Vacío se guarda como NULL,
                    # permitiendo varias presentaciones sin código de barras.
                    bc=barcode.get().strip() or None
                    if not n or fac<=0 or pr<0:
                        raise ValueError

                    current_id=existing["id"] if existing else -1
                    duplicate_name=self.db.one(
                        """SELECT * FROM product_presentations
                           WHERE product_id=? AND lower(trim(name))=lower(trim(?)) AND id<>?""",
                        (product_id,n,current_id)
                    )
                    if duplicate_name:
                        if not existing and int(duplicate_name["active"] or 0)==0:
                            # Si ya existía pero estaba desactivada, la recuperamos.
                            self.db.execute(
                                """UPDATE product_presentations
                                   SET name=?,factor=?,sale_price=?,barcode=?,active=1
                                   WHERE id=?""",
                                (n,fac,pr,bc,duplicate_name["id"])
                            )
                            fw.destroy();load();return
                        messagebox.showerror(
                            "Presentación",
                            f"Ya existe una presentación llamada '{n}' para este producto."
                        )
                        return

                    if bc:
                        duplicate_barcode=self.db.one(
                            "SELECT id,name FROM product_presentations WHERE barcode=? AND id<>?",
                            (bc,current_id)
                        )
                        if duplicate_barcode:
                            messagebox.showerror(
                                "Presentación",
                                f"El código de barras {bc} ya está asignado a la presentación '{duplicate_barcode['name']}'."
                            )
                            return

                    if existing:
                        self.db.execute("""UPDATE product_presentations
                                           SET name=?,factor=?,sale_price=?,barcode=?
                                           WHERE id=?""",(n,fac,pr,bc,existing["id"]))
                    else:
                        self.db.execute("""INSERT INTO product_presentations(
                                            product_id,name,factor,sale_price,barcode,active,created_by,created_at)
                                           VALUES(?,?,?,?,?,1,?,?)""",
                                        (product_id,n,fac,pr,bc,self.user["id"],now_iso()))
                    fw.destroy();load()
                except sqlite3.IntegrityError as e:
                    messagebox.showerror("Presentación",f"No se pudo guardar la presentación.\n{e}")
                except Exception:
                    messagebox.showerror("Presentación","Revise nombre, equivalencia y precio.")

            tk.Button(f,text="GUARDAR",command=save,bg=COLORS["green"],fg="white",
                      relief="flat",pady=9).pack(fill="x",pady=8)

        def selected_id():
            sel=tree.selection()
            return int(tree.item(sel[0],"values")[0]) if sel else None

        def edit():
            sid=selected_id()
            if sid:form(sid)

        def delete():
            sid=selected_id()
            if not sid:return
            if messagebox.askyesno("Presentación","¿Desactivar esta presentación?"):
                self.db.execute("UPDATE product_presentations SET active=0 WHERE id=?",(sid,))
                load()

        tk.Button(actions,text="+ Nueva",command=lambda:form(),bg=COLORS["green"],fg="white",
                  relief="flat",padx=14,pady=7).pack(side="left",padx=4)
        tk.Button(actions,text="Modificar",command=edit,bg=COLORS["blue"],fg="white",
                  relief="flat",padx=14,pady=7).pack(side="left",padx=4)
        tk.Button(actions,text="Eliminar",command=delete,bg=COLORS["red"],fg="white",
                  relief="flat",padx=14,pady=7).pack(side="left",padx=4)

    def inventory_movement_form(self, product_id):
        product=self.db.one("SELECT * FROM products WHERE id=?",(product_id,))
        if not product:return
        if product["product_type"]=="SERVICE":
            messagebox.showinfo("Inventario","Los servicios no manejan inventario.")
            return

        win=tk.Toplevel(self)
        win.title("Movimiento / historial de inventario")
        win.geometry("940x650")
        win.minsize(820,560)
        win.transient(self)
        win.grab_set()

        box=tk.Frame(win,padx=18,pady=14)
        box.pack(fill="both",expand=True)

        tk.Label(box,text="Movimiento / historial de inventario",
                 font=("Segoe UI",16,"bold")).pack(anchor="w")
        tk.Label(box,text=product["name"],font=("Segoe UI",11,"bold"),
                 fg=COLORS["green"]).pack(anchor="w",pady=(3,2))

        stock_var=tk.StringVar()
        tk.Label(box,textvariable=stock_var,fg=COLORS["gray"]).pack(anchor="w",pady=(0,10))

        form=tk.LabelFrame(box,text="Registrar movimiento manual",padx=12,pady=10)
        form.pack(fill="x",pady=(0,12))

        row=tk.Frame(form)
        row.pack(fill="x")

        employee_types=["CORTESIA / REGALO","MERMA / DAÑO","USO INTERNO"]
        admin_types=employee_types+["AJUSTE POSITIVO","AJUSTE NEGATIVO"]

        tk.Label(row,text="Tipo",font=("Segoe UI",9,"bold")).grid(row=0,column=0,sticky="w")
        movement=ttk.Combobox(
            row,state="readonly",width=23,
            values=admin_types if self.user["role"]=="admin" else employee_types
        )
        movement.current(0)
        movement.grid(row=1,column=0,padx=(0,10),pady=(3,5),sticky="ew")

        tk.Label(row,text=f"Cantidad ({product['unit']})",font=("Segoe UI",9,"bold")).grid(
            row=0,column=1,sticky="w"
        )
        qty=tk.Entry(row,width=14,font=("Segoe UI",10))
        qty.grid(row=1,column=1,padx=(0,10),pady=(3,5),sticky="ew")

        tk.Label(row,text="Costo unit. (ajuste +)",font=("Segoe UI",9,"bold")).grid(
            row=0,column=2,sticky="w"
        )
        cost=tk.Entry(row,width=16,font=("Segoe UI",10))
        cost.grid(row=1,column=2,padx=(0,10),pady=(3,5),sticky="ew")

        tk.Label(row,text="Motivo / nota",font=("Segoe UI",9,"bold")).grid(
            row=0,column=3,sticky="w"
        )
        note=tk.Entry(row,font=("Segoe UI",10))
        note.grid(row=1,column=3,pady=(3,5),sticky="ew")
        row.grid_columnconfigure(3,weight=1)

        hist_box=tk.LabelFrame(box,text="Historial completo del producto",padx=8,pady=8)
        hist_box.pack(fill="both",expand=True)

        tk.Label(
            hist_box,
            text="Doble clic o Enter sobre un movimiento para ver el detalle completo.",
            fg=COLORS["gray"],font=("Segoe UI",8)
        ).pack(anchor="w",pady=(0,5))

        cols=("date","type","qty","cost","ref","user","note")
        hist=ttk.Treeview(hist_box,columns=cols,show="headings")
        for c,h,w in [
            ("date","Fecha / hora",145),
            ("type","Movimiento",145),
            ("qty","Cantidad",85),
            ("cost","Costo unit.",90),
            ("ref","Referencia",100),
            ("user","Usuario",130),
            ("note","Nota / motivo",240),
        ]:
            hist.heading(c,text=h)
            hist.column(c,width=w)
        scroll=ttk.Scrollbar(hist_box,orient="vertical",command=hist.yview)
        hist.configure(yscrollcommand=scroll.set)
        hist.pack(side="left",fill="both",expand=True)
        scroll.pack(side="right",fill="y")

        def load_history():
            for item in hist.get_children():
                hist.delete(item)
            stock_var.set(
                f"Existencia actual: {self.db.current_stock(product_id):.2f} {product['unit']}"
            )
            rows=self.db.all(
                """SELECT m.*,u.full_name
                   FROM inventory_movements m
                   LEFT JOIN users u ON u.id=m.created_by
                   WHERE m.product_id=?
                   ORDER BY m.id DESC""",
                (product_id,)
            )
            for m in rows:
                ref=f"{m['reference_type']} #{m['reference_id']}" if m["reference_id"] else (m["reference_type"] or "")
                unit_cost="" if m["unit_cost"] is None else f"${float(m['unit_cost']):.4f}"
                hist.insert(
                    "","end",
                    iid=str(m["id"]),
                    values=(
                        m["created_at"],
                        m["movement_type"],
                        f"{float(m['qty']):+.2f}",
                        unit_cost,
                        ref,
                        m["full_name"] or "",
                        m["note"] or ""
                    )
                )


        def open_movement_detail(event=None):
            sel=hist.selection()
            if not sel:
                return
            try:
                movement_id=int(sel[0])
            except Exception:
                return

            mov=self.db.one(
                """SELECT m.*,p.sku,p.barcode,p.name product_name,p.unit,
                          u.full_name
                   FROM inventory_movements m
                   JOIN products p ON p.id=m.product_id
                   LEFT JOIN users u ON u.id=m.created_by
                   WHERE m.id=?""",
                (movement_id,)
            )
            if not mov:
                return

            qty_value=float(mov["qty"] or 0)
            unit_cost=float(mov["unit_cost"] or 0)
            amount=abs(qty_value*unit_cost)
            direction="ENTRADA" if qty_value>0 else "SALIDA" if qty_value<0 else "SIN CAMBIO"

            ref_type=mov["reference_type"] or ""
            ref_id=mov["reference_id"]
            reference=f"{ref_type} #{ref_id}" if ref_type and ref_id is not None else (ref_type or "Sin referencia")

            related=[]

            if ref_type=="PURCHASE" and ref_id:
                pch=self.db.one(
                    """SELECT p.*,u.full_name registered_by
                       FROM purchases p
                       LEFT JOIN users u ON u.id=p.created_by
                       WHERE p.id=?""",(ref_id,)
                )
                if pch:
                    related += [
                        "","COMPRA RELACIONADA",
                        f"Proveedor: {pch['supplier'] or '-'}",
                        f"Documento: {pch['document_no'] or '-'}",
                        f"Total compra: ${float(pch['total'] or 0):.2f}",
                        f"Registrada por: {pch['registered_by'] or '-'}"
                    ]

            if ref_type in ("SALE","VENTA","VENTA_ADICIONAL") and ref_id:
                sale=self.db.one(
                    """SELECT s.*,u.full_name cashier
                       FROM sales s
                       LEFT JOIN users u ON u.id=s.created_by
                       WHERE s.id=?""",(ref_id,)
                )
                if sale:
                    related += [
                        "","VENTA RELACIONADA",
                        f"Venta: #{sale['id']}",
                        f"Pago: {sale['payment_method'] or '-'}",
                        f"Total: ${float(sale['total'] or 0):.2f}",
                        f"Cajero: {sale['cashier'] or '-'}",
                        f"Estado: {sale['status'] or '-'}"
                    ]

            if ref_type in ("RETURN","DEVOLUCION") and ref_id:
                ret=self.db.one(
                    """SELECT r.*,u.full_name created_name
                       FROM sale_returns r
                       LEFT JOIN users u ON u.id=r.created_by
                       WHERE r.id=?""",(ref_id,)
                )
                if ret:
                    related += [
                        "","DEVOLUCIÓN RELACIONADA",
                        f"Devolución: #{ret['id']}",
                        f"Venta original: #{ret['sale_id']}",
                        f"Reembolso: ${float(ret['total_refund'] or 0):.2f}",
                        f"Método: {ret['refund_method'] or '-'}",
                        f"Motivo: {ret['reason'] or '-'}",
                        f"Registrada por: {ret['created_name'] or '-'}"
                    ]

            lines=[
                f"Movimiento: #{mov['id']}",
                f"Fecha / hora: {mov['created_at']}",
                "",
                "PRODUCTO",
                f"Código interno: {mov['sku'] or '-'}",
                f"Código de barras: {mov['barcode'] or '-'}",
                f"Producto: {mov['product_name']}",
                f"Unidad base: {mov['unit'] or '-'}",
                "",
                "MOVIMIENTO",
                f"Tipo: {mov['movement_type']}",
                f"Dirección: {direction}",
                f"Cantidad: {qty_value:+.2f} {mov['unit'] or ''}",
                f"Costo unitario: ${unit_cost:.4f}",
                f"Valor del movimiento: ${amount:.2f}",
                f"Referencia: {reference}",
                f"Usuario: {mov['full_name'] or '-'}",
                f"Nota / motivo: {mov['note'] or '-'}",
            ] + related

            self.show_app_modal(
                "Detalle de movimiento de inventario",
                f"{mov['product_name']} · {direction}",
                modal_type="info",
                primary_text="CERRAR",
                detail="\n".join(lines)
            )


        def save():
            try:
                q=float(qty.get())
                if q<=0:
                    raise ValueError("La cantidad debe ser mayor que cero.")

                m=movement.get()
                note_text=note.get().strip()
                positive=(m=="AJUSTE POSITIVO")

                if positive:
                    c=float(cost.get() or 0)
                    if c<0:
                        raise ValueError("El costo no puede ser negativo.")
                    self.db.conn.execute(
                        """INSERT INTO inventory_lots(
                           product_id,purchase_item_id,qty_received,qty_remaining,unit_cost,created_at
                           ) VALUES(?,NULL,?,?,?,?)""",
                        (product_id,q,q,c,now_iso())
                    )
                    self.db.log_inventory(
                        product_id,"AJUSTE_POSITIVO",q,c,
                        "MANUAL",None,note_text,self.user["id"]
                    )
                else:
                    if self.db.current_stock(product_id)<q:
                        messagebox.showwarning(
                            "Inventario",
                            f"No hay existencia suficiente. Disponible: {self.db.current_stock(product_id):.2f} {product['unit']}"
                        )
                        return

                    ctotal,allocs=self.db.consume_fifo(product_id,q)
                    avg=ctotal/q if q else 0
                    code_type=(
                        "CORTESIA" if "CORTESIA" in m else
                        "MERMA" if "MERMA" in m else
                        "USO_INTERNO" if "USO" in m else
                        "AJUSTE_NEGATIVO"
                    )
                    self.db.log_inventory(
                        product_id,code_type,-q,avg,
                        "MANUAL",None,note_text,self.user["id"]
                    )

                self.db.conn.commit()
                qty.delete(0,"end")
                cost.delete(0,"end")
                note.delete(0,"end")
                load_history()
                self.build_products()
                self.build_dashboard()
                messagebox.showinfo("Inventario","Movimiento registrado correctamente.")

            except ValueError as e:
                self.db.conn.rollback()
                messagebox.showwarning("Inventario",str(e))
            except Exception as e:
                self.db.conn.rollback()
                messagebox.showerror("Inventario",f"No se pudo registrar el movimiento.\n{e}")

        buttons=tk.Frame(form)
        buttons.pack(fill="x",pady=(8,0))
        tk.Button(
            buttons,text="REGISTRAR MOVIMIENTO",command=save,
            bg=COLORS["green"],fg="white",relief="flat",padx=18,pady=8
        ).pack(side="left")
        tk.Button(
            buttons,text="ACTUALIZAR HISTORIAL",command=load_history,
            bg=COLORS["blue"],fg="white",relief="flat",padx=18,pady=8
        ).pack(side="left",padx=8)

        hist.bind("<Double-1>",open_movement_detail)
        hist.bind("<Return>",open_movement_detail)

        load_history()

    def build_purchases(self):
        for w in self.tab_purchases.winfo_children(): w.destroy()
        top=tk.Frame(self.tab_purchases,bg=COLORS["light"]);top.pack(fill="x",pady=8)
        tk.Label(top,text="Compras / Entradas de inventario",font=("Segoe UI",18,"bold"),bg=COLORS["light"]).pack(side="left")
        tk.Button(top,text="+ Registrar compra",command=self.add_purchase,bg=COLORS["green"],fg="white",relief="flat").pack(side="right")
        cols=("id","date","supplier","doc","total","user")
        tree=ttk.Treeview(self.tab_purchases,columns=cols,show="headings")
        for c,h,w in [("id","ID",60),("date","Fecha",155),("supplier","Proveedor",210),("doc","Documento",150),("total","Total",110),("user","Registró",180)]:
            tree.heading(c,text=h); tree.column(c,width=w)
        tree.pack(fill="both",expand=True,pady=8)
        def load_purchases():
            for item in tree.get_children():
                tree.delete(item)
            rows=self.db.all(
                """SELECT p.*,u.full_name
                   FROM purchases p
                   JOIN users u ON u.id=p.created_by
                   ORDER BY p.id DESC LIMIT 300"""
            )
            for r in rows:
                tree.insert(
                    "","end",
                    values=(
                        r["id"],r["created_at"],r["supplier"],r["document_no"],
                        f"${float(r['total']):.2f}",r["full_name"]
                    )
                )

        def open_purchase_detail(event=None):
            sel=tree.selection()
            if not sel:
                self.show_app_modal(
                    "Seleccione una compra",
                    "Seleccione la compra que desea consultar.",
                    modal_type="warning",
                    primary_text="ACEPTAR"
                )
                return

            purchase_id=int(tree.item(sel[0],"values")[0])
            purchase=self.db.one(
                """SELECT p.*,u.full_name
                   FROM purchases p
                   JOIN users u ON u.id=p.created_by
                   WHERE p.id=?""",
                (purchase_id,)
            )
            if not purchase:
                return

            items=self.db.all(
                """SELECT pi.*,pr.sku,pr.name,pr.unit,
                          (
                            SELECT im.note
                            FROM inventory_movements im
                            WHERE im.reference_type='PURCHASE'
                              AND im.reference_id=pi.purchase_id
                              AND im.product_id=pi.product_id
                              AND im.movement_type='COMPRA'
                            ORDER BY im.id DESC LIMIT 1
                          ) movement_note
                   FROM purchase_items pi
                   JOIN products pr ON pr.id=pi.product_id
                   WHERE pi.purchase_id=?
                   ORDER BY pi.id""",
                (purchase_id,)
            )

            rows=[]
            for item in items:
                qty=float(item["qty"] or 0)
                unit_cost=float(item["unit_cost"] or 0)
                rows.append((
                    item["sku"],
                    item["name"],
                    item["unit"] or "Unidad",
                    f"{qty:.2f}",
                    f"${unit_cost:.4f}",
                    f"${qty*unit_cost:.2f}",
                    item["movement_note"] or ""
                ))

            summary={
                "Compra":f"#{purchase_id}",
                "Fecha":purchase["created_at"],
                "Proveedor":purchase["supplier"] or "Sin especificar",
                "Documento":purchase["document_no"] or "Sin especificar",
                "Registró":purchase["full_name"],
                "Total":f"${float(purchase['total']):.2f}",
                "Productos":str(len(items)),
            }

            self.open_printable_report(
                f"Detalle de compra #{purchase_id}",
                ["Código","Producto","Unidad base","Cantidad","Costo unitario","Subtotal","Detalle de ingreso"],
                rows,
                summary
            )

        tree.bind("<Double-1>",open_purchase_detail)
        tree.bind("<Return>",open_purchase_detail)

        actions=tk.Frame(self.tab_purchases,bg=COLORS["light"])
        actions.pack(fill="x",pady=(0,5))

        tk.Button(
            actions,text="VER DETALLE / IMPRIMIR",
            command=open_purchase_detail,
            bg=COLORS["blue"],fg="white",
            font=("Segoe UI",9,"bold"),relief="flat",
            padx=15,pady=7
        ).pack(side="left",padx=5)

        tk.Button(
            actions,text="ACTUALIZAR",
            command=load_purchases,
            bg="#E5E7EB",fg=COLORS["dark"],
            font=("Segoe UI",9,"bold"),relief="flat",
            padx=15,pady=7
        ).pack(side="left",padx=5)

        tk.Label(
            actions,
            text="Doble clic o Enter = abrir detalle de compra",
            bg=COLORS["light"],fg=COLORS["gray"],font=("Segoe UI",9)
        ).pack(side="right",padx=8)

        load_purchases()

    def add_purchase(self):
        products=self.db.all("SELECT id,sku,name,unit FROM products WHERE active=1 AND product_type='PRODUCT' ORDER BY name")
        if not products:
            messagebox.showwarning("Compras","Primero registre al menos un producto.")
            return

        win=tk.Toplevel(self)
        win.title("Registrar compra")
        win.geometry("900x650")
        win.minsize(760,560)
        win.transient(self)
        win.grab_set()

        # Barra inferior fija: siempre visible incluso en pantallas de poca altura.
        purchase_fixed_footer=tk.Frame(win,bg=COLORS["white"],bd=1,relief="solid")
        purchase_fixed_footer.pack(side="bottom",fill="x",padx=0,pady=0)

        # Contenedor principal con tres zonas:
        # encabezado fijo, cuerpo expansible y pie fijo.
        root=tk.Frame(win,padx=18,pady=14)
        root.pack(fill="both",expand=True)

        # ---------- Encabezado fijo ----------
        header=tk.Frame(root)
        header.pack(fill="x")
        tk.Label(header,text="Nueva compra",font=("Segoe UI",17,"bold")).pack(anchor="w",pady=(0,12))

        meta=tk.Frame(header)
        meta.pack(fill="x")
        tk.Label(meta,text="Proveedor",font=("Segoe UI",9,"bold")).grid(row=0,column=0,sticky="w")
        supplier=tk.Entry(meta,font=("Segoe UI",10))
        supplier.grid(row=1,column=0,sticky="ew",padx=(0,15),ipady=4)
        tk.Label(meta,text="Documento / factura",font=("Segoe UI",9,"bold")).grid(row=0,column=1,sticky="w")
        doc=tk.Entry(meta,font=("Segoe UI",10))
        doc.grid(row=1,column=1,sticky="ew",ipady=4)
        meta.grid_columnconfigure(0,weight=2)
        meta.grid_columnconfigure(1,weight=1)

        add=tk.LabelFrame(header,text="Agregar producto",padx=10,pady=10)
        add.pack(fill="x",pady=(14,10))

        tk.Label(add,text="Buscar por nombre").grid(row=0,column=0,sticky="w")
        search_var=tk.StringVar()
        search=tk.Entry(add,textvariable=search_var,font=("Segoe UI",10))
        search.grid(row=1,column=0,sticky="ew",padx=(0,8),ipady=4)

        tk.Label(add,text="Producto").grid(row=0,column=1,sticky="w")
        current_products=list(products)
        combo=ttk.Combobox(
            add,state="readonly",
            values=[f"{p['sku']} — {p['name']}" for p in current_products]
        )
        combo.grid(row=1,column=1,sticky="ew",padx=8)
        if current_products:
            combo.current(0)

        tk.Label(add,text="Cantidad comprada").grid(row=0,column=2)
        qty=tk.Entry(add,width=10,font=("Segoe UI",10))
        qty.grid(row=1,column=2,padx=8,ipady=4)

        tk.Label(add,text="Costo por presentación").grid(row=0,column=3)
        cost=tk.Entry(add,width=14,font=("Segoe UI",10))
        cost.grid(row=1,column=3,padx=8,ipady=4)

        tk.Label(add,text="Presentación de compra").grid(row=2,column=0,sticky="w",pady=(8,0))
        purchase_presentation=ttk.Combobox(add,state="readonly")
        purchase_presentation.grid(row=3,column=0,columnspan=2,sticky="ew",padx=(0,8),pady=(2,0))
        current_purchase_presentations=[]

        conversion_var=tk.StringVar(value="")
        tk.Label(add,textvariable=conversion_var,fg=COLORS["gray"],font=("Segoe UI",9),
                 anchor="w",justify="left").grid(row=3,column=2,columnspan=3,sticky="w",padx=8,pady=(2,0))

        add.grid_columnconfigure(0,weight=1)
        add.grid_columnconfigure(1,weight=2)

        def load_purchase_presentations(event=None):
            nonlocal current_purchase_presentations
            if not current_products or combo.current()<0:
                current_purchase_presentations=[]
                purchase_presentation["values"]=[]
                purchase_presentation.set("")
                conversion_var.set("")
                return
            p=current_products[combo.current()]
            base={"id":None,"name":p["unit"] or "Unidad","factor":1.0}
            extras=[dict(r) for r in self.db.all(
                """SELECT id,name,factor FROM product_presentations
                   WHERE product_id=? AND active=1 ORDER BY factor,name""",
                (p["id"],)
            )]
            current_purchase_presentations=[base]+extras
            purchase_presentation["values"]=[
                f"{x['name']} · {float(x['factor']):g} {p['unit']}" for x in current_purchase_presentations
            ]
            purchase_presentation.current(0)
            update_purchase_conversion()

        def update_purchase_conversion(event=None):
            if not current_products or combo.current()<0 or not current_purchase_presentations:
                conversion_var.set("")
                return
            p=current_products[combo.current()]
            idx=purchase_presentation.current()
            if idx<0: idx=0
            pres=current_purchase_presentations[idx]
            try:q=float(qty.get() or 0)
            except:q=0
            try:c=float(cost.get() or 0)
            except:c=0
            factor=float(pres["factor"])
            base_qty=q*factor
            base_cost=(c/factor) if factor else 0
            conversion_var.set(
                f"Ingreso: {base_qty:g} {p['unit']} · Costo base: ${base_cost:.4f} por {p['unit']}"
                if q>0 else f"1 {pres['name']} = {factor:g} {p['unit']}"
            )

        combo.bind("<<ComboboxSelected>>",load_purchase_presentations)
        purchase_presentation.bind("<<ComboboxSelected>>",update_purchase_conversion)
        qty.bind("<KeyRelease>",update_purchase_conversion)
        cost.bind("<KeyRelease>",update_purchase_conversion)

        def filter_products(*_):
            nonlocal current_products
            term=search_var.get().strip().lower()
            current_products=[p for p in products if term in p["name"].lower()] if term else list(products)
            combo["values"]=[f"{p['sku']} — {p['name']}" for p in current_products]
            if current_products:
                combo.current(0)
                load_purchase_presentations()
            else:
                combo.set("")
                load_purchase_presentations()
        search_var.trace_add("write",filter_products)
        load_purchase_presentations()

        items=[]

        # ---------- Cuerpo expansible ----------
        body=tk.Frame(root)
        body.pack(fill="both",expand=True)

        cols=("sku","name","presentation","purchase_qty","base_qty","cost","sub")
        tree=ttk.Treeview(body,columns=cols,show="headings")
        for c,h,w in [
            ("sku","Código",105),("name","Producto",205),("presentation","Presentación",120),
            ("purchase_qty","Compra",75),("base_qty","Ingresa",85),("cost","Costo/pres.",95),("sub","Subtotal",100)
        ]:
            tree.heading(c,text=h)
            tree.column(c,width=w)

        vscroll=ttk.Scrollbar(body,orient="vertical",command=tree.yview)
        tree.configure(yscrollcommand=vscroll.set)
        tree.pack(side="left",fill="both",expand=True,pady=(6,8))
        vscroll.pack(side="right",fill="y",pady=(6,8))

        total_var=tk.StringVar(value="Total compra: $0.00")

        def refresh():
            for x in tree.get_children():
                tree.delete(x)
            total=0
            for item in items:
                sub=item["purchase_qty"]*item["purchase_cost"]
                total+=sub
                tree.insert(
                    "","end",
                    values=(
                        item["sku"],item["name"],item["presentation"],
                        f"{item['purchase_qty']:g}",f"{item['qty']:g}",
                        f"${item['purchase_cost']:.4f}",f"${sub:.2f}"
                    )
                )
            total_var.set(f"Total compra: ${total:.2f}")

        def add_item():
            try:
                if not current_products or combo.current() < 0:
                    raise ValueError
                p=current_products[combo.current()]
                purchase_q=float(qty.get())
                purchase_c=float(cost.get())
                if purchase_q <= 0 or purchase_c < 0:
                    raise ValueError
                idx=purchase_presentation.current()
                pres=current_purchase_presentations[idx] if 0<=idx<len(current_purchase_presentations) else {"name":p["unit"],"factor":1.0}
                factor=float(pres["factor"])
                base_qty=purchase_q*factor
                base_cost=purchase_c/factor
                items.append({
                    "product_id":p["id"],"sku":p["sku"],"name":p["name"],
                    "presentation":pres["name"],"factor":factor,
                    "purchase_qty":purchase_q,"purchase_cost":purchase_c,
                    "qty":base_qty,"cost":base_cost
                })
                qty.delete(0,"end")
                cost.delete(0,"end")
                refresh()
                update_purchase_conversion()
                qty.focus_set()
            except Exception:
                messagebox.showerror(
                    "Compra",
                    "Seleccione un producto e ingrese cantidad y costo válidos."
                )

        tk.Button(
            add,text="Agregar",command=add_item,
            bg=COLORS["green"],fg="white",relief="flat",
            padx=15,pady=5
        ).grid(row=1,column=4,padx=(10,0))

        # Permitir Enter desde cantidad/costo para agregar.
        qty.bind("<Return>",lambda e:add_item())
        cost.bind("<Return>",lambda e:add_item())

        # ---------- Pie fijo ----------
        footer=tk.Frame(root)
        footer.pack(fill="x",side="bottom")

        top_footer=tk.Frame(footer)
        top_footer.pack(fill="x",pady=(2,8))
        tk.Label(top_footer,textvariable=total_var,font=("Segoe UI",16,"bold")).pack(side="left")

        def remove_item():
            sel=tree.selection()
            if not sel:
                return
            idx=tree.index(sel[0])
            if 0 <= idx < len(items):
                items.pop(idx)
                refresh()

        tk.Button(
            top_footer,text="Quitar seleccionado",command=remove_item,
            relief="flat",bg="#E5E7EB",padx=12,pady=6
        ).pack(side="right")

        def save_purchase():
            if not items:
                messagebox.showwarning("Compra","Agregue al menos un producto.")
                return
            try:
                cur=self.db.conn.cursor()
                total=sum(x["purchase_qty"]*x["purchase_cost"] for x in items)
                cur.execute(
                    "INSERT INTO purchases(supplier,document_no,total,created_by,created_at) VALUES(?,?,?,?,?)",
                    (supplier.get().strip(),doc.get().strip(),total,self.user["id"],now_iso())
                )
                purchase_id=cur.lastrowid

                for x in items:
                    cur.execute(
                        "INSERT INTO purchase_items(purchase_id,product_id,qty,unit_cost) VALUES(?,?,?,?)",
                        (purchase_id,x["product_id"],x["qty"],x["cost"])
                    )
                    item_id=cur.lastrowid
                    cur.execute(
                        """INSERT INTO inventory_lots(
                            product_id,purchase_item_id,qty_received,qty_remaining,unit_cost,created_at
                        ) VALUES(?,?,?,?,?,?)""",
                        (x["product_id"],item_id,x["qty"],x["qty"],x["cost"],now_iso())
                    )
                    self.db.log_inventory(
                        x["product_id"],"COMPRA",x["qty"],x["cost"],
                        "PURCHASE",purchase_id,
                        f"Compra {doc.get().strip()} · {x['purchase_qty']:g} {x['presentation']} = {x['qty']:g} unidades base",
                        self.user["id"]
                    )

                self.db.conn.commit()
                messagebox.showinfo(
                    "Compra",
                    f"Compra registrada.\nProductos: {len(items)}\nTotal: ${total:.2f}"
                )
                win.destroy()
                self.build_purchases()
                self.build_products()
                self.build_dashboard()
            except Exception as e:
                self.db.conn.rollback()
                messagebox.showerror("Compra",f"No se pudo registrar la compra.\n{e}")

        # Botones reales de la compra dentro de la barra inferior fija.
        buttons=tk.Frame(purchase_fixed_footer,bg=COLORS["white"])
        buttons.pack(fill="x",padx=16,pady=12)

        tk.Button(
            buttons,text="CANCELAR",command=win.destroy,
            bg="#6B7280",fg="white",
            font=("Segoe UI",10,"bold"),
            relief="flat",padx=24,pady=10
        ).pack(side="left")

        tk.Button(
            buttons,text="GUARDAR COMPRA",command=save_purchase,
            bg=COLORS["green"],fg="white",font=("Segoe UI",10,"bold"),
            relief="flat",padx=28,pady=10
        ).pack(side="right")

        supplier.focus_set()

    def build_ticket_text(self, sale_id):
        sale=self.db.one("""SELECT s.*,u.full_name FROM sales s JOIN users u ON u.id=s.created_by WHERE s.id=?""",(sale_id,))
        if not sale:
            return ""
        items=self.db.all("""SELECT si.*,p.name,p.sku FROM sale_items si JOIN products p ON p.id=si.product_id WHERE si.sale_id=? ORDER BY si.id""",(sale_id,))
        width=42
        lines=["TIENDA MEJIA".center(width),"Donde siempre hay de todo".center(width),"="*width]
        lines += [f"Ticket: {sale_id}",f"Fecha: {sale['created_at']}",f"Cajero: {sale['full_name']}","-"*width]
        for item in items:
            qty=float(item["qty"]); price=float(item["unit_price"]); subtotal=qty*price
            lines.append(str(item["name"])[:width])
            lines.append(f"{qty:g} x ${price:.2f}".ljust(24)+f"${subtotal:.2f}".rjust(18))
        lines += ["-"*width,"TOTAL".ljust(24)+f"${float(sale['total']):.2f}".rjust(18),f"Pago: {sale['payment_method']}"]
        if sale["payment_method"]=="Efectivo":
            lines.append("Recibido".ljust(24)+f"${float(sale['amount_received'] or 0):.2f}".rjust(18))
            lines.append("Cambio".ljust(24)+f"${float(sale['change_given'] or 0):.2f}".rjust(18))
        lines += ["="*width,"Gracias por su compra".center(width),"Tienda Mejia".center(width),"",""]
        return "\n".join(lines)

    def print_ticket(self, sale_id):
        try:
            receipts_dir=APP_DIR / "tickets"
            receipts_dir.mkdir(exist_ok=True)
            ticket_path=receipts_dir / f"ticket_{sale_id}.txt"
            ticket_path.write_text(self.build_ticket_text(sale_id),encoding="utf-8")
            if os.name=="nt":
                os.startfile(str(ticket_path),"print")
                return True,str(ticket_path)
            return False,str(ticket_path)
        except Exception as e:
            return False,str(e)

    def _logo_data_uri(self):
        try:
            if LOGO_PATH.exists():
                raw=base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii")
                return f"data:image/jpeg;base64,{raw}"
        except Exception:
            pass
        return ""

    def build_ticket_html(self, sale_id, width_mm=80):
        sale=self.db.one("""SELECT s.*,u.full_name
                            FROM sales s JOIN users u ON u.id=s.created_by
                            WHERE s.id=?""",(sale_id,))
        if not sale:
            return ""
        items=self.db.all("""SELECT si.*,p.name,p.sku
                             FROM sale_items si JOIN products p ON p.id=si.product_id
                             WHERE si.sale_id=? ORDER BY si.id""",(sale_id,))
        logo=self._logo_data_uri()
        logo_html=f'<img class="logo" src="{logo}">' if logo else ""
        rows=""
        for item in items:
            qty=float(item["sale_qty"] if item["sale_qty"] is not None else item["qty"])
            price=float(item["display_unit_price"] if item["display_unit_price"] is not None else item["unit_price"])
            sub=qty*price
            pres=(item["presentation_name"] or "").strip()
            pres_html=f"<br><small>{html.escape(pres)}</small>" if pres else ""
            rows += f"""<tr><td>{html.escape(str(item["name"]))}{pres_html}<br><small>{html.escape(str(item["sku"]))}</small></td>
            <td class="num">{qty:g}</td><td class="num">${price:.2f}</td><td class="num">${sub:.2f}</td></tr>"""
            addon_rows=self.db.all("SELECT * FROM sale_item_addons WHERE sale_item_id=? ORDER BY id",(item["id"],))
            for ad in addon_rows:
                rows += f"""<tr><td>&nbsp;&nbsp;+ {html.escape(str(ad["addon_name"]))}</td>
                <td class="num"></td><td class="num">${float(ad["extra_price"]):.2f}</td><td class="num"></td></tr>"""
        received=""
        if sale["payment_method"]=="Efectivo":
            received=f"""<div class="line"><span>Recibido</span><strong>${float(sale["amount_received"] or 0):.2f}</strong></div>
            <div class="line"><span>Cambio</span><strong>${float(sale["change_given"] or 0):.2f}</strong></div>"""
        return f"""<!doctype html><html><head><meta charset="utf-8"><title>Ticket {sale_id}</title>
<style>
@page{{size:{width_mm}mm auto;margin:3mm}}
body{{font-family:Arial,sans-serif;width:{width_mm-8}mm;margin:0 auto;color:#111;font-size:11px}}
.logo{{display:block;max-width:42mm;max-height:18mm;margin:0 auto 4px}}
.center{{text-align:center}} h2{{margin:2px 0;font-size:16px}}
hr{{border:none;border-top:1px dashed #333;margin:6px 0}}
table{{width:100%;border-collapse:collapse}} td{{vertical-align:top;padding:3px 0}}
.num{{text-align:right;white-space:nowrap}} .line{{display:flex;justify-content:space-between;margin:3px 0}}
.total{{font-size:16px;font-weight:bold}} .no-print{{margin-top:10px;text-align:center}}
@media print{{.no-print{{display:none}}}}
</style></head><body>
{logo_html}<div class="center"><h2>TIENDA MEJÍA</h2><div>Donde siempre hay de todo</div></div><hr>
<div>Ticket: #{sale_id}</div><div>Fecha: {html.escape(str(sale["created_at"]))}</div>
<div>Cajero: {html.escape(str(sale["full_name"]))}</div><hr>
<table>{rows}</table><hr>
<div class="line total"><span>TOTAL</span><span>${float(sale["total"]):.2f}</span></div>
<div class="line"><span>Pago</span><span>{html.escape(str(sale["payment_method"]))}</span></div>
{received}<hr><div class="center">¡Gracias por su compra!</div><div class="center">Tienda Mejía</div>
<div class="no-print"><button onclick="window.print()">Imprimir ticket</button></div>
<script>setTimeout(()=>window.print(),400);</script></body></html>"""

    def print_ticket(self, sale_id, width_mm=80):
        try:
            folder=APP_DIR/"tickets"; folder.mkdir(exist_ok=True)
            path=folder/f"ticket_{sale_id}.html"
            path.write_text(self.build_ticket_html(sale_id,width_mm),encoding="utf-8")
            webbrowser.open(path.resolve().as_uri())
            return True,str(path)
        except Exception as e:
            return False,str(e)

    def open_printable_report(self,title,headers,rows,summary=None):
        try:
            folder=APP_DIR/"reportes"; folder.mkdir(exist_ok=True)
            stamp=datetime.now().strftime("%Y%m%d_%H%M%S")
            safe="".join(c if c.isalnum() else "_" for c in title).strip("_")
            path=folder/f"{safe}_{stamp}.html"
            logo=self._logo_data_uri()
            logo_html=f'<img src="{logo}" class="logo">' if logo else ""
            th="".join(f"<th>{html.escape(str(h))}</th>" for h in headers)
            tbody="".join("<tr>"+"".join(f"<td>{html.escape(str(v))}</td>" for v in row)+"</tr>" for row in rows)
            summary_html=""
            if summary:
                summary_html="<div class='summary'>"+"".join(
                    f"<div><strong>{html.escape(str(k))}:</strong> {html.escape(str(v))}</div>" for k,v in summary.items()
                )+"</div>"
            doc=f"""<!doctype html><html><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>
@page{{size:A4;margin:12mm}} body{{font-family:Arial,sans-serif;color:#222}}
.header{{display:flex;align-items:center;gap:18px;border-bottom:2px solid #69B238;padding-bottom:10px}}
.logo{{width:120px;max-height:70px;object-fit:contain}} h1{{margin:0;font-size:22px}}
.meta{{color:#666;margin-top:4px;font-size:12px}} .summary{{display:flex;flex-wrap:wrap;gap:20px;margin:14px 0;padding:10px;background:#f5f5f5}}
table{{width:100%;border-collapse:collapse;font-size:11px;margin-top:12px}} th{{background:#f0f0f0;text-align:left}}
th,td{{border:1px solid #bbb;padding:6px}} .actions{{margin:16px 0}} @media print{{.actions{{display:none}}}}
</style></head><body><div class="header">{logo_html}<div><h1>{html.escape(title)}</h1>
<div class="meta">Tienda Mejía · Generado: {datetime.now().strftime("%d/%m/%Y %I:%M %p")}</div></div></div>
{summary_html}<div class="actions"><button onclick="window.print()">Imprimir reporte</button></div>
<table><thead><tr>{th}</tr></thead><tbody>{tbody}</tbody></table></body></html>"""
            path.write_text(doc,encoding="utf-8")
            webbrowser.open(path.resolve().as_uri())
            return True,str(path)
        except Exception as e:
            messagebox.showerror("Reporte",f"No se pudo generar la vista imprimible.\n{e}")
            return False,str(e)

    def build_sales(self):
        for w in self.tab_sales.winfo_children():
            w.destroy()

        products=self.db.all("SELECT * FROM products WHERE active=1 ORDER BY name")
        by_barcode={str(p["barcode"]).strip():p for p in products if p["barcode"]}
        by_sku={str(p["sku"]).strip().lower():p for p in products}
        presentation_barcode={}
        for r in self.db.all("""SELECT pp.*,p.id product_id,p.sku,p.name,p.unit,p.sale_price,p.barcode product_barcode
                                FROM product_presentations pp JOIN products p ON p.id=pp.product_id
                                WHERE pp.active=1 AND pp.barcode IS NOT NULL AND pp.barcode<>''"""):
            presentation_barcode[str(r["barcode"]).strip()]=dict(r)

        # ---------- Encabezado ----------
        header=tk.Frame(self.tab_sales,bg=COLORS["light"])
        header.pack(fill="x",pady=(6,10))

        tk.Label(
            header,text="Punto de venta",
            font=("Segoe UI",20,"bold"),
            bg=COLORS["light"],fg=COLORS["dark"]
        ).pack(side="left")

        cash_text="CAJA ABIERTA" if self.cash_session else "CAJA CERRADA"
        cash_color=COLORS["green"] if self.cash_session else COLORS["red"]
        tk.Label(
            header,text=cash_text,
            bg=cash_color,fg="white",
            font=("Segoe UI",9,"bold"),
            padx=12,pady=5
        ).pack(side="right")

        # ---------- Barra superior de captura ----------
        capture=tk.Frame(
            self.tab_sales,bg=COLORS["white"],
            highlightthickness=1,highlightbackground="#D1D5DB"
        )
        capture.pack(fill="x",pady=(0,10))

        row1=tk.Frame(capture,bg=COLORS["white"])
        row1.pack(fill="x",padx=14,pady=(12,6))

        tk.Label(
            row1,text="Código / barras",
            bg=COLORS["white"],font=("Segoe UI",9,"bold")
        ).pack(side="left")

        barcode_entry=tk.Entry(row1,font=("Segoe UI",13),width=28)
        barcode_entry.pack(side="left",padx=(8,18),ipady=5)

        tk.Label(
            row1,text="Buscar producto",
            bg=COLORS["white"],font=("Segoe UI",9,"bold")
        ).pack(side="left")

        name_search_var=tk.StringVar()
        name_search=tk.Entry(
            row1,textvariable=name_search_var,
            font=("Segoe UI",11),width=28
        )
        name_search.pack(side="left",padx=8,ipady=5)

        row2=tk.Frame(capture,bg=COLORS["white"])
        row2.pack(fill="x",padx=14,pady=(4,12))

        tk.Label(
            row2,text="Producto",
            bg=COLORS["white"],font=("Segoe UI",9,"bold")
        ).pack(side="left")

        filtered_products=list(products)
        combo=ttk.Combobox(
            row2,state="readonly",width=48,
            values=[f"{p['sku']} — {p['name']}" for p in filtered_products]
        )
        combo.pack(side="left",padx=8)
        if filtered_products:
            combo.current(0)

        tk.Label(
            row2,text="Cantidad",
            bg=COLORS["white"],font=("Segoe UI",9,"bold")
        ).pack(side="left",padx=(12,4))

        qty=tk.Entry(row2,width=8,font=("Segoe UI",11))
        qty.insert(0,"1")
        qty.pack(side="left",padx=4,ipady=4)

        stock_var=tk.StringVar(value="Stock: -")
        tk.Label(
            row2,textvariable=stock_var,
            bg=COLORS["white"],fg=COLORS["gray"],
            font=("Segoe UI",9)
        ).pack(side="left",padx=8)

        tk.Label(
            row2,text="Presentación",
            bg=COLORS["white"],font=("Segoe UI",9,"bold")
        ).pack(side="left",padx=(6,3))

        presentation_combo=ttk.Combobox(
            row2,state="readonly",width=19
        )
        presentation_combo.pack(side="left",padx=4)
        current_presentations=[]

        add_btn=tk.Button(
            row2,text="AGREGAR",
            bg=COLORS["green"],fg="white",
            font=("Segoe UI",10,"bold"),
            relief="flat",padx=20,pady=7
        )
        add_btn.pack(side="right")

        addons_frame=tk.Frame(capture,bg=COLORS["white"])
        addons_frame.pack(fill="x",padx=12,pady=(0,10))
        tk.Label(addons_frame,text="Adicionales:",bg=COLORS["white"],
                 font=("Segoe UI",9,"bold")).pack(side="left")
        addon_vars=[]
        current_addons=[]

        def load_addons(product):
            nonlocal addon_vars,current_addons
            for w in addons_frame.winfo_children()[1:]:
                w.destroy()
            addon_vars=[]
            current_addons=[dict(r) for r in self.db.all(
                """SELECT * FROM product_addons
                   WHERE parent_product_id=? AND active=1 ORDER BY name""",(product["id"],))]
            for addon in current_addons:
                v=tk.BooleanVar(value=False);addon_vars.append(v)
                text=f"{addon['name']} (+${float(addon['extra_price']):.2f})"
                tk.Checkbutton(addons_frame,text=text,variable=v,bg=COLORS["white"],
                               activebackground=COLORS["white"],font=("Segoe UI",8)).pack(side="left",padx=6)

        def load_presentations(product):
            nonlocal current_presentations
            base={
                "id":None,
                "name":product["unit"] or "Unidad",
                "factor":1.0,
                "sale_price":float(product["sale_price"]),
                "barcode":product["barcode"] or ""
            }
            extras=[] if product["product_type"]=="SERVICE" else [
                dict(r) for r in self.db.all(
                    """SELECT id,name,factor,sale_price,barcode
                       FROM product_presentations
                       WHERE product_id=? AND active=1
                       ORDER BY factor,name""",
                    (product["id"],)
                )
            ]
            current_presentations=[base]+extras
            presentation_combo["values"]=[
                f"{x['name']} · {float(x['factor']):g} u · ${float(x['sale_price']):.2f}"
                for x in current_presentations
            ]
            presentation_combo.current(0)

        def update_stock_label(event=None):
            if not filtered_products or combo.current() < 0:
                stock_var.set("Stock: 0")
                presentation_combo["values"]=[]
                presentation_combo.set("")
                return
            p=filtered_products[combo.current()]
            if p["product_type"]=="SERVICE":
                stock_var.set("Servicio · sin inventario")
            else:
                stock_var.set(f"Stock: {self.db.current_stock(p['id']):.2f} {p['unit']}")
            load_presentations(p)
            load_addons(p)

        def filter_sale_products(*_):
            nonlocal filtered_products
            term=name_search_var.get().strip().lower()
            filtered_products=[
                p for p in products
                if term in p["name"].lower()
                or term in str(p["sku"]).lower()
                or term in str(p["category"] or "").lower()
            ] if term else list(products)

            combo["values"]=[
                f"{p['sku']} — {p['name']}" for p in filtered_products
            ]
            if filtered_products:
                combo.current(0)
                update_stock_label()
            else:
                combo.set("")
                stock_var.set("Stock: 0")
                presentation_combo["values"]=[]
                presentation_combo.set("")

        name_search_var.trace_add("write",filter_sale_products)
        combo.bind("<<ComboboxSelected>>",update_stock_label)
        update_stock_label()

        # ---------- Área principal: carrito + cobro ----------
        work=tk.Frame(self.tab_sales,bg=COLORS["light"])
        work.pack(fill="both",expand=True)

        # Carrito
        left=tk.Frame(work,bg=COLORS["white"],highlightthickness=1,highlightbackground="#D1D5DB")
        left.pack(side="left",fill="both",expand=True,padx=(0,10))

        cart_header=tk.Frame(left,bg=COLORS["white"])
        cart_header.pack(fill="x",padx=12,pady=(10,6))

        items_var=tk.StringVar(value="0 productos")
        tk.Label(
            cart_header,text="Detalle de venta",
            bg=COLORS["white"],font=("Segoe UI",12,"bold")
        ).pack(side="left")
        tk.Label(
            cart_header,textvariable=items_var,
            bg=COLORS["white"],fg=COLORS["gray"],font=("Segoe UI",9)
        ).pack(side="right")

        # Barra fija de acciones del carrito.
        # Se empaqueta antes de la tabla para asegurar que sea visible
        # incluso en resoluciones verticales pequeñas (ej. 1366x720).
        cart_actions=tk.Frame(left,bg=COLORS["white"])
        cart_actions.pack(fill="x",padx=10,pady=(0,7))

        table_frame=tk.Frame(left,bg=COLORS["white"])
        table_frame.pack(fill="both",expand=True,padx=10,pady=(0,6))

        cols=("sku","name","presentation","qty","price","sub")
        tree=ttk.Treeview(table_frame,columns=cols,show="headings")
        for c,h,w in [
            ("sku","Código",115),
            ("name","Producto",240),
            ("presentation","Presentación",140),
            ("qty","Cant.",75),
            ("price","Precio",85),
            ("sub","Subtotal",95),
        ]:
            tree.heading(c,text=h)
            tree.column(c,width=w)

        vscroll=ttk.Scrollbar(table_frame,orient="vertical",command=tree.yview)
        tree.configure(yscrollcommand=vscroll.set)
        tree.pack(side="left",fill="both",expand=True)
        vscroll.pack(side="right",fill="y")

        # Resumen / Cobro
        right=tk.Frame(
            work,bg=COLORS["white"],width=350,
            highlightthickness=1,highlightbackground="#D1D5DB"
        )
        right.pack(side="right",fill="y")
        right.pack_propagate(False)

        # =====================================================
        # ZONA 3 - PIE FIJO: siempre visible
        # =====================================================
        checkout_footer=tk.Frame(right,bg=COLORS["white"])
        checkout_footer.pack(side="bottom",fill="x",padx=12,pady=(3,6))

        print_var=tk.BooleanVar(value=True)
        tk.Checkbutton(
            checkout_footer,text="Imprimir ticket al cobrar",
            variable=print_var,bg=COLORS["white"],activebackground=COLORS["white"],
            font=("Segoe UI",8)
        ).pack(anchor="w",pady=(0,3))

        checkout_btn=tk.Button(
            checkout_footer,text="COBRAR  ·  F4",
            bg=COLORS["red"],fg="white",font=("Segoe UI",12,"bold"),
            relief="flat",pady=9
        )
        checkout_btn.pack(fill="x")
        tk.Label(
            checkout_footer,
            text="En efectivo: escriba el recibido y presione Enter",
            bg=COLORS["white"],fg=COLORS["gray"],font=("Segoe UI",7)
        ).pack(pady=(3,0))

        # =====================================================
        # ZONA 2 - COBRO FIJO: efectivo / botones / cambio
        # Se reserva su altura antes de crear el resumen superior.
        # =====================================================
        payment_zone=tk.Frame(right,bg=COLORS["white"],height=205)
        payment_zone.pack(side="bottom",fill="x")
        payment_zone.pack_propagate(False)

        # Deben existir antes de cualquier widget que las utilice.
        subtotal_var=tk.StringVar(value="$0.00")
        total_var=tk.StringVar(value="$0.00")

        cash_frame=tk.Frame(payment_zone,bg=COLORS["white"])

        totals_line=tk.Frame(cash_frame,bg="#F3F4F6")
        totals_line.pack(fill="x",padx=12,pady=(2,5))
        tk.Label(
            totals_line,text="TOTAL A COBRAR",bg="#F3F4F6",
            fg=COLORS["gray"],font=("Segoe UI",8,"bold")
        ).pack(side="left",padx=(10,5),pady=7)
        tk.Label(
            totals_line,textvariable=total_var,bg="#F3F4F6",
            fg=COLORS["dark"],font=("Segoe UI",19,"bold")
        ).pack(side="right",padx=(5,10),pady=3)

        tk.Label(
            cash_frame,text="EFECTIVO RECIBIDO",bg=COLORS["white"],
            fg=COLORS["dark"],font=("Segoe UI",9,"bold")
        ).pack(anchor="w",padx=14,pady=(2,2))

        received=tk.Entry(
            cash_frame,font=("Segoe UI",17,"bold"),justify="right",
            relief="solid",bd=1
        )
        received.pack(fill="x",padx=14,ipady=3)

        quick=tk.Frame(cash_frame,bg=COLORS["white"])
        quick.pack(fill="x",padx=12,pady=(4,2))

        def set_received(value):
            received.configure(state="normal")
            received.delete(0,"end")
            received.insert(0,f"{float(value):.2f}")
            received.icursor("end")
            calculate_change()
            save_pending_draft()
            received.focus_set()

        exact_btn=tk.Button(
            quick,text="PAGO EXACTO",relief="flat",
            bg="#E8F5E9",fg="#1B5E20",font=("Segoe UI",8,"bold"),
            command=lambda:set_received(current_total()),pady=3
        )
        exact_btn.pack(side="left",fill="x",expand=True,padx=2)

        for amount in [5,10,20,50]:
            tk.Button(
                quick,text=f"${amount}",relief="flat",
                bg="#F3F4F6",fg=COLORS["dark"],font=("Segoe UI",8,"bold"),
                command=lambda a=amount:set_received(a),pady=3
            ).pack(side="left",fill="x",expand=True,padx=2)

        cash_status_var=tk.StringVar(value="Ingrese el efectivo recibido")
        change_var=tk.StringVar(value="$0.00")

        status_card=tk.Frame(cash_frame,bg="#F3F4F6")
        status_card.pack(fill="x",padx=12,pady=(2,1))
        tk.Label(
            status_card,textvariable=cash_status_var,bg="#F3F4F6",
            fg=COLORS["gray"],font=("Segoe UI",7,"bold")
        ).pack(anchor="w",padx=9,pady=(4,0))
        change_label=tk.Label(
            status_card,textvariable=change_var,bg="#F3F4F6",
            fg=COLORS["green"],font=("Segoe UI",17,"bold")
        )
        change_label.pack(anchor="w",padx=9,pady=(0,4))

        noncash_frame=tk.Frame(payment_zone,bg="#EFF6FF")
        tk.Label(
            noncash_frame,
            text="PAGO NO EFECTIVO",
            bg="#EFF6FF",fg="#1D4ED8",
            font=("Segoe UI",9,"bold")
        ).pack(anchor="w",padx=12,pady=(18,3))
        tk.Label(
            noncash_frame,
            text="No necesita ingresar efectivo.\nPresione COBRAR para registrar la venta.",
            bg="#EFF6FF",fg="#1D4ED8",justify="left",
            font=("Segoe UI",9),padx=12,pady=8
        ).pack(anchor="w")

        # =====================================================
        # ZONA 1 - RESUMEN SUPERIOR: usa únicamente el espacio
        # restante y nunca puede tapar las zonas 2 y 3.
        # =====================================================
        summary=tk.Frame(right,bg=COLORS["white"])
        summary.pack(side="top",fill="both",expand=True)

        tk.Label(
            summary,text="COBRO",bg=COLORS["white"],fg=COLORS["dark"],
            font=("Segoe UI",11,"bold")
        ).pack(anchor="w",padx=14,pady=(7,1))
        tk.Label(
            summary,text="Confirme el total y registre cómo paga el cliente.",
            bg=COLORS["white"],fg=COLORS["gray"],font=("Segoe UI",7)
        ).pack(anchor="w",padx=14,pady=(0,4))

        total_card=tk.Frame(summary,bg="#F3F4F6")
        total_card.pack(fill="x",padx=12,pady=(0,5))
        tk.Label(
            total_card,text="RESUMEN DE LA VENTA",bg="#F3F4F6",fg=COLORS["gray"],
            font=("Segoe UI",8,"bold")
        ).pack(anchor="w",padx=10,pady=(5,5))

        tk.Label(
            summary,text="FORMA DE PAGO",bg=COLORS["white"],
            fg=COLORS["gray"],font=("Segoe UI",8,"bold")
        ).pack(anchor="w",padx=14,pady=(0,2))

        pay=tk.StringVar(value="Efectivo")
        payment_buttons={}
        payment_bar=tk.Frame(summary,bg=COLORS["white"])
        payment_bar.pack(fill="x",padx=12,pady=(0,3))

        def choose_payment(method):
            pay.set(method)
            update_payment_ui()
            calculate_change()
            save_pending_draft()

        for method,label in [
            ("Efectivo","EFECTIVO"),
            ("Transferencia","TRANSFER."),
            ("Otro","OTRO")
        ]:
            b=tk.Button(
                payment_bar,text=label,
                command=lambda m=method:choose_payment(m),
                relief="flat",font=("Segoe UI",8,"bold"),pady=5
            )
            b.pack(side="left",fill="x",expand=True,padx=2)
            payment_buttons[method]=b

        def update_payment_ui():
            method=pay.get()
            for m,b in payment_buttons.items():
                if m==method:
                    b.configure(bg="#2563EB",fg="white")
                else:
                    b.configure(bg="#E5E7EB",fg=COLORS["dark"])

            cash_frame.pack_forget()
            noncash_frame.pack_forget()

            if method=="Efectivo":
                cash_frame.pack(fill="both",expand=True)
                received.configure(state="normal")
            else:
                noncash_frame.pack(fill="both",expand=True,padx=12,pady=(2,4))

        update_payment_ui()

        def current_total():
            return sum(x["sale_qty"]*(x["price"] + sum(a["extra_price"] for a in x.get("addons",[]))) for x in self.cart)

        def delete_pending_draft():
            if not self.user:
                return
            self.db.execute("DELETE FROM pending_sale_drafts WHERE user_id=?",(self.user["id"],))

        def save_pending_draft():
            """Guarda el carrito sin afectar inventario ni convertirlo en venta."""
            if not self.user:
                return
            try:
                if not self.cart:
                    self.db.conn.execute(
                        "DELETE FROM pending_sale_drafts WHERE user_id=?",
                        (self.user["id"],)
                    )
                else:
                    self.db.conn.execute(
                        """INSERT INTO pending_sale_drafts(
                               user_id,cash_session_id,cart_json,payment_method,amount_received,updated_at
                           ) VALUES(?,?,?,?,?,?)
                           ON CONFLICT(user_id) DO UPDATE SET
                               cash_session_id=excluded.cash_session_id,
                               cart_json=excluded.cart_json,
                               payment_method=excluded.payment_method,
                               amount_received=excluded.amount_received,
                               updated_at=excluded.updated_at""",
                        (
                            self.user["id"],
                            self.cash_session["id"] if self.cash_session else None,
                            json.dumps(self.cart,ensure_ascii=False),
                            pay.get() or "Efectivo",
                            received.get(),
                            now_iso()
                        )
                    )
                self.db.conn.commit()
            except Exception:
                # El POS debe seguir operando aunque falle únicamente el respaldo del borrador.
                try:self.db.conn.rollback()
                except Exception:pass

        def recover_pending_draft():
            if not self.user:
                return False
            draft=self.db.one(
                "SELECT * FROM pending_sale_drafts WHERE user_id=?",
                (self.user["id"],)
            )
            if not draft:
                return False
            try:
                recovered=json.loads(draft["cart_json"] or "[]")
            except Exception:
                recovered=[]
            if not recovered:
                delete_pending_draft()
                return False

            total=sum(
                float(x.get("sale_qty",0))*(
                    float(x.get("price",0))+
                    sum(float(a.get("extra_price",0)) for a in x.get("addons",[]))
                )
                for x in recovered
            )
            answer=messagebox.askyesnocancel(
                "Venta pendiente recuperable",
                f"Se encontró una venta pendiente del usuario {self.user['full_name']}.\n\n"
                f"Última actualización: {draft['updated_at']}\n"
                f"Artículos: {len(recovered)}\n"
                f"Total aproximado: ${total:.2f}\n\n"
                "Sí = RECUPERAR\nNo = DESCARTAR\nCancelar = mantenerla guardada sin abrirla"
            )
            if answer is True:
                self.cart=recovered
                try:
                    pay.set(draft["payment_method"] or "Efectivo")
                    update_payment_ui()
                    received.configure(state="normal")
                    received.delete(0,"end")
                    received.insert(0,draft["amount_received"] or "")
                except Exception:
                    pass
                return True
            elif answer is False:
                self.cart=[]
                delete_pending_draft()
                return False
            else:
                self.cart=[]
                return False

        def calculate_change(event=None):
            total=current_total()
            if pay.get()!="Efectivo":
                change_var.set("$0.00")
                cash_status_var.set("Pago no efectivo")
                return
            try:
                raw=received.get().strip()
                rec=float(raw) if raw else 0.0
            except Exception:
                rec=0.0

            if not received.get().strip():
                cash_status_var.set("Ingrese el efectivo recibido")
                change_var.set("$0.00")
                change_label.configure(fg=COLORS["gray"])
            elif rec < total:
                missing=total-rec
                cash_status_var.set("FALTA PARA COMPLETAR EL PAGO")
                change_var.set(f"${missing:.2f}")
                change_label.configure(fg=COLORS["red"])
            else:
                change=rec-total
                cash_status_var.set("CAMBIO A ENTREGAR")
                change_var.set(f"${change:.2f}")
                change_label.configure(fg=COLORS["green"])

        def refresh_cart():
            for i in tree.get_children():
                tree.delete(i)
            total=0
            base_units=0
            for x in self.cart:
                addon_price=sum(a["extra_price"] for a in x.get("addons",[]))
                unit_total=x["price"]+addon_price
                sub=x["sale_qty"]*unit_total
                total+=sub
                base_units+=x["inventory_qty"]
                addon_text=", ".join(a["name"] for a in x.get("addons",[]))
                presentation_text=x["presentation"] + (f" + {addon_text}" if addon_text else "")
                tree.insert(
                    "","end",
                    values=(x["sku"],x["name"],presentation_text,
                            f"{x['sale_qty']:.2f}",
                            f"${unit_total:.2f}",f"${sub:.2f}")
                )
            subtotal_var.set(f"${total:.2f}")
            total_var.set(f"${total:.2f}")
            items_var.set(f"{base_units:.2f} unidades de inventario")
            calculate_change()
            save_pending_draft()

        def add_product_to_cart(p,q,presentation=None,addons=None):
            addons=addons or []
            pres=presentation or {
                "name":p["unit"] or "Unidad","factor":1.0,
                "sale_price":float(p["sale_price"])
            }
            factor=0.0 if p["product_type"]=="SERVICE" else float(pres["factor"])
            inventory_qty=0.0 if p["product_type"]=="SERVICE" else q*factor

            if q<=0:
                messagebox.showwarning("Venta","La cantidad debe ser mayor que cero.")
                return

            if p["product_type"]!="SERVICE":
                stock=self.db.current_stock(p["id"])
                in_cart=sum(x["inventory_qty"] for x in self.cart if x["product_id"]==p["id"])
                if inventory_qty+in_cart>stock:
                    messagebox.showwarning("Venta",f"Inventario disponible de {p['name']}: {stock:.2f} {p['unit']}")
                    return

            # Validate component stock used by add-ons.
            for addon in addons:
                comp_id=addon.get("component_product_id")
                comp_qty=float(addon.get("component_qty") or 0)*q
                if comp_id and comp_qty>0:
                    stock=self.db.current_stock(comp_id)
                    already=sum(
                        sum(float(a.get("component_qty") or 0)*x["sale_qty"]
                            for a in x.get("addons",[]) if a.get("component_product_id")==comp_id)
                        for x in self.cart
                    )
                    if already+comp_qty>stock:
                        comp=self.db.one("SELECT name FROM products WHERE id=?",(comp_id,))
                        messagebox.showwarning("Venta",f"No hay suficiente inventario de {comp['name']}. Disponible: {stock:.2f}")
                        return

            self.cart.append({
                "product_id":p["id"],"sku":p["sku"],"name":p["name"],
                "product_type":p["product_type"],
                "presentation":pres["name"],"factor":factor,
                "sale_qty":q,"inventory_qty":inventory_qty,
                "price":float(pres["sale_price"]),
                "addons":[dict(a) for a in addons]
            })
            refresh_cart()

        def add_selected(event=None):
            try:
                if not filtered_products or combo.current()<0:
                    messagebox.showwarning("Venta","Seleccione un producto.")
                    return
                p=filtered_products[combo.current()]
                try:
                    q=float(qty.get())
                except Exception:
                    messagebox.showwarning("Venta","Ingrese una cantidad válida.")
                    qty.focus_set()
                    return

                pres=None
                if current_presentations and presentation_combo.current()>=0:
                    pres=current_presentations[presentation_combo.current()]
                selected_addons=[
                    current_addons[i] for i,v in enumerate(addon_vars) if v.get()
                ]
                add_product_to_cart(p,q,pres,selected_addons)
                qty.delete(0,"end")
                qty.insert(0,"1")
                name_search_var.set("")
                barcode_entry.focus_set()
            except Exception as e:
                messagebox.showerror(
                    "Venta",
                    f"No se pudo agregar el producto.\n{e}"
                )

        add_btn.configure(command=add_selected)

        def scan_code(event=None):
            code_value=barcode_entry.get().strip()
            if not code_value:
                return

            pres_row=presentation_barcode.get(code_value)
            pres=None
            if pres_row:
                p=self.db.one(
                    "SELECT * FROM products WHERE id=?",
                    (pres_row["product_id"],)
                )
                pres={
                    "name":pres_row["name"],
                    "factor":float(pres_row["factor"]),
                    "sale_price":float(pres_row["sale_price"]),
                    "barcode":pres_row["barcode"] or ""
                }
            else:
                p=by_barcode.get(code_value) or by_sku.get(code_value.lower())

            if not p:
                messagebox.showwarning(
                    "Venta",
                    "No se encontró un producto con ese código."
                )
                barcode_entry.select_range(0,"end")
                return

            try:
                q=float(qty.get() or 1)
            except Exception:
                q=1

            add_product_to_cart(p,q,pres,[])
            barcode_entry.delete(0,"end")
            qty.delete(0,"end")
            qty.insert(0,"1")
            barcode_entry.focus_set()

        barcode_entry.bind("<Return>",scan_code)
        qty.bind("<Return>",add_selected)

        def selected_cart_index():
            sel=tree.selection()
            if not sel:
                return None
            return tree.index(sel[0])

        def increase_selected():
            idx=selected_cart_index()
            if idx is None:
                return
            item=self.cart[idx]
            stock=self.db.current_stock(item["product_id"])
            if item["inventory_qty"]+item["factor"]>stock:
                messagebox.showwarning("Venta",f"Inventario disponible: {stock:.2f}")
                return
            item["sale_qty"]+=1
            item["inventory_qty"]+=item["factor"]
            refresh_cart()

        def decrease_selected():
            idx=selected_cart_index()
            if idx is None:
                return
            item=self.cart[idx]
            item["sale_qty"]-=1
            item["inventory_qty"]-=item["factor"]
            if item["sale_qty"]<=0:
                self.cart.pop(idx)
            refresh_cart()

        def remove_selected():
            idx=selected_cart_index()
            if idx is None:
                return
            self.cart.pop(idx)
            refresh_cart()

        def clear_cart():
            if not self.cart:
                return
            if self.show_app_modal(
                "Vaciar venta",
                "¿Desea eliminar todos los artículos de la venta actual?",
                modal_type="question",
                primary_text="SÍ, VACIAR",
                secondary_text="VOLVER",
                detail=f"Artículos en carrito: {len(self.cart)} · Total: ${current_total():.2f}"
            ):
                self.cart=[]
                refresh_cart()

        tk.Button(
            cart_actions,text="+1",command=increase_selected,
            bg=COLORS["green"],fg="white",relief="flat",width=6,pady=5
        ).pack(side="left",padx=(0,5))

        tk.Button(
            cart_actions,text="-1",command=decrease_selected,
            bg="#E5E7EB",fg=COLORS["dark"],relief="flat",width=6,pady=5
        ).pack(side="left",padx=5)

        tk.Button(
            cart_actions,text="ELIMINAR ITEM",command=remove_selected,
            bg=COLORS["red"],fg="white",font=("Segoe UI",9,"bold"),
            relief="flat",padx=16,pady=6
        ).pack(side="left",padx=5)

        tk.Button(
            cart_actions,text="Vaciar venta",command=clear_cart,
            bg=COLORS["red"],fg="white",relief="flat",padx=12,pady=5
        ).pack(side="right")

        def received_changed(event=None):
            calculate_change()
            save_pending_draft()

        received.bind("<KeyRelease>",received_changed)

        def finalize(event=None):
            if not self.cash_session:
                messagebox.showwarning("Venta","Debe abrir caja antes de registrar ventas.")
                return
            if not self.cart:
                messagebox.showwarning("Venta","No hay productos en la venta.")
                return
            sale_committed=False
            try:
                total=current_total()
                amount_received=None
                change_given=0

                if pay.get()=="Efectivo":
                    try:
                        amount_received=float(received.get())
                    except Exception:
                        self.show_app_modal(
                            "Falta el efectivo recibido",
                            "Ingrese cuánto dinero entregó el cliente antes de cobrar.",
                            modal_type="warning",primary_text="INGRESAR MONTO"
                        )
                        received.focus_set()
                        return
                    if amount_received<total:
                        self.show_app_modal(
                            "Pago incompleto",
                            "El efectivo recibido todavía no cubre el total de la venta.",
                            modal_type="warning",primary_text="CORREGIR",
                            detail=f"Total: ${total:.2f} · Recibido: ${amount_received:.2f} · Falta: ${total-amount_received:.2f}"
                        )
                        received.focus_set()
                        return
                    change_given=amount_received-total

                cur=self.db.conn.cursor()
                cost_total=0

                for x in self.cart:
                    if x["product_type"]!="SERVICE" and self.db.current_stock(x["product_id"]) < x["inventory_qty"]:
                        raise ValueError(f"Inventario insuficiente para {x['name']}")
                    for addon in x.get("addons",[]):
                        comp_id=addon.get("component_product_id")
                        need=float(addon.get("component_qty") or 0)*x["sale_qty"]
                        if comp_id and need>0 and self.db.current_stock(comp_id)<need:
                            comp=self.db.one("SELECT name FROM products WHERE id=?",(comp_id,))
                            raise ValueError(f"Inventario insuficiente para {comp['name']}")

                sale_time=now_iso()
                cur.execute(
                    """INSERT INTO sales(
                        total,cost_total,payment_method,created_by,cash_session_id,
                        created_at,amount_received,change_given,status
                    ) VALUES(?,?,?,?,?,?,?,?,?)""",
                    (
                        total,0,pay.get(),self.user["id"],self.cash_session["id"],
                        sale_time,amount_received,change_given,"COMPLETED"
                    )
                )
                sale_id=cur.lastrowid

                for x in self.cart:
                    c=0
                    allocations=[]
                    if x["product_type"]!="SERVICE" and x["inventory_qty"]>0:
                        c,allocations=self.db.consume_fifo(x["product_id"],x["inventory_qty"])

                    addon_total=sum(a["extra_price"] for a in x.get("addons",[]))
                    display_price=x["price"]+addon_total
                    base_price=(x["price"]/x["factor"]) if x["factor"] else x["price"]

                    cur.execute(
                        """INSERT INTO sale_items(
                            sale_id,product_id,qty,unit_price,cost_total,sale_qty,presentation_name,presentation_factor,display_unit_price
                        ) VALUES(?,?,?,?,?,?,?,?,?)""",
                        (sale_id,x["product_id"],x["inventory_qty"],base_price,c,x["sale_qty"],
                         x["presentation"],x["factor"],display_price)
                    )
                    sale_item_id=cur.lastrowid

                    for a in allocations:
                        cur.execute("""INSERT INTO sale_cost_allocations(sale_item_id,lot_id,qty,unit_cost)
                                       VALUES(?,?,?,?)""",(sale_item_id,a["lot_id"],a["qty"],a["unit_cost"]))

                    if x["product_type"]!="SERVICE" and x["inventory_qty"]>0:
                        self.db.log_inventory(
                            x["product_id"],"VENTA",-x["inventory_qty"],
                            c/x["inventory_qty"] if x["inventory_qty"] else None,
                            "SALE",sale_id,"Salida por venta",self.user["id"]
                        )

                    # Process add-ons.
                    for addon in x.get("addons",[]):
                        comp_cost=0
                        comp_id=addon.get("component_product_id")
                        comp_need=float(addon.get("component_qty") or 0)*x["sale_qty"]
                        if comp_id and comp_need>0:
                            comp_cost,_addon_allocs=self.db.consume_fifo(comp_id,comp_need)
                            self.db.log_inventory(
                                comp_id,"VENTA_ADICIONAL",-comp_need,
                                comp_cost/comp_need if comp_need else None,
                                "SALE",sale_id,f"Adicional: {addon['name']}",self.user["id"]
                            )
                        cur.execute("""INSERT INTO sale_item_addons(
                            sale_item_id,addon_name,extra_price,component_product_id,component_qty,component_cost
                        ) VALUES(?,?,?,?,?,?)""",
                        (sale_item_id,addon["name"],float(addon["extra_price"]),
                         comp_id,comp_need,comp_cost))
                        c+=comp_cost

                    cur.execute("UPDATE sale_items SET cost_total=? WHERE id=?",(c,sale_item_id))
                    cost_total+=c

                cur.execute("UPDATE sales SET cost_total=? WHERE id=?",(cost_total,sale_id))
                self.db.conn.commit()
                sale_committed=True

                # A partir de aquí la venta YA está confirmada.
                # Limpiamos inmediatamente el borrador y el carrito para impedir
                # una venta duplicada si falla el ticket o cualquier elemento visual.
                self.cart=[]
                delete_pending_draft()

                print_note=""
                if print_var.get():
                    selected_width = 80
                    try:
                        if "ticket_size_combo" in locals() and ticket_size_combo.get()=="58 mm":
                            selected_width = 58
                        elif "ticket_size" in locals() and ticket_size.get()=="58 mm":
                            selected_width = 58
                    except Exception:
                        selected_width = 80
                    ok,detail=self.print_ticket(sale_id,selected_width)
                    if not ok:
                        print_note=f"\n\nLa venta se guardó, pero el ticket no pudo enviarse a la impresora.\nTicket: {detail}"

                msg=f"Venta #{sale_id} registrada.\nTotal: ${total:.2f}"
                if pay.get()=="Efectivo":
                    msg+=f"\nRecibido: ${amount_received:.2f}\nCambio: ${change_given:.2f}"
                msg+=print_note

                detail=f"Venta #{sale_id}  ·  Total ${total:.2f}"
                if pay.get()=="Efectivo":
                    detail+=f"  ·  Recibido ${amount_received:.2f}  ·  Cambio ${change_given:.2f}"
                try:
                    self.show_app_modal(
                        "Venta registrada",
                        "La venta fue guardada correctamente." + (
                            "\nEl ticket no pudo enviarse a la impresora." if print_note else ""
                        ),
                        modal_type="success",
                        primary_text="NUEVA VENTA",
                        detail=detail
                    )
                except Exception:
                    # Nunca convertir un fallo visual posterior al commit
                    # en un supuesto fallo de la venta.
                    pass

                received.configure(state="normal")
                received.delete(0,"end")
                pay.set("Efectivo")
                update_payment_ui()
                refresh_cart()
                self.build_dashboard()
                self.build_products()
                # La venta acaba de modificar el turno de caja.
                # Reconstruir la pantalla para que efectivo esperado y ventas
                # reflejen inmediatamente el nuevo movimiento.
                self.build_cash()
                if self.user["role"]=="admin" and hasattr(self,"tab_finances"):
                    try:self.build_finances()
                    except Exception:pass
                barcode_entry.focus_set()

            except ValueError as e:
                if not sale_committed:
                    self.db.conn.rollback()
                    self.show_app_modal(
                        "No se pudo completar la venta",
                        str(e),
                        modal_type="error",
                        primary_text="ACEPTAR"
                    )
            except Exception as e:
                if not sale_committed:
                    self.db.conn.rollback()
                    self.show_app_modal(
                        "No se pudo registrar la venta",
                        str(e),
                        modal_type="error",
                        primary_text="ACEPTAR"
                    )
                else:
                    # La venta ya está guardada. Un fallo posterior no debe inducir
                    # al cajero a cobrarla nuevamente.
                    try:
                        received.configure(state="normal")
                        received.delete(0,"end")
                        pay.set("Efectivo")
                        update_payment_ui()
                        refresh_cart()
                    except Exception:
                        pass
                    self.show_app_modal(
                        "Venta guardada",
                        "La venta quedó registrada correctamente, pero ocurrió un problema al actualizar la pantalla.",
                        modal_type="warning",
                        primary_text="CONTINUAR",
                        detail=f"Venta #{sale_id} · Total ${total:.2f}"
                    )

        checkout_btn.configure(command=finalize)

        # Enter contextual según el campo activo.
        name_search.bind("<Return>",lambda e:qty.focus_set())
        combo.bind("<Return>",lambda e:qty.focus_set())
        received.bind("<Return>",finalize)

        # Atajos de teclado del POS.
        self.bind("<F2>",lambda e:name_search.focus_set())
        self.bind("<F4>",finalize)
        self.bind("<Delete>",lambda e:remove_selected())

        recovered_draft=recover_pending_draft()
        refresh_cart()
        if recovered_draft:
            messagebox.showinfo(
                "Venta recuperada",
                "La venta pendiente fue restaurada correctamente. Puede continuar donde quedó."
            )
        barcode_entry.focus_set()

    def build_cash(self):
        for w in self.tab_cash.winfo_children():
            w.destroy()

        header=tk.Frame(self.tab_cash,bg=COLORS["light"])
        header.pack(fill="x",pady=(6,12))
        tk.Label(
            header,text="Gestión de caja",
            font=("Segoe UI",18,"bold"),bg=COLORS["light"],fg=COLORS["dark"]
        ).pack(side="left")

        status_text="CAJA ABIERTA" if self.cash_session else "CAJA CERRADA"
        status_bg=COLORS["green"] if self.cash_session else COLORS["red"]
        tk.Label(
            header,text=status_text,bg=status_bg,fg="white",
            font=("Segoe UI",9,"bold"),padx=14,pady=6
        ).pack(side="right")

        tk.Button(
            header,text="ACTUALIZAR",command=lambda:(self.load_cash_session(),self.build_cash()),
            bg="#E5E7EB",fg=COLORS["dark"],font=("Segoe UI",8,"bold"),
            relief="flat",padx=12,pady=6
        ).pack(side="right",padx=(0,8))

        # -------------------------------
        # CAJA CERRADA
        # -------------------------------
        if not self.cash_session:
            shell=tk.Frame(
                self.tab_cash,bg=COLORS["white"],
                highlightthickness=1,highlightbackground="#D1D5DB"
            )
            shell.pack(fill="x",pady=(0,10))

            hero=tk.Frame(shell,bg="#F8FAFC")
            hero.pack(fill="x")
            tk.Label(
                hero,text="CAJA CERRADA",bg="#F8FAFC",fg=COLORS["red"],
                font=("Segoe UI",10,"bold")
            ).pack(anchor="w",padx=22,pady=(18,3))
            tk.Label(
                hero,text="Inicie una nueva jornada de caja",
                bg="#F8FAFC",fg=COLORS["dark"],font=("Segoe UI",18,"bold")
            ).pack(anchor="w",padx=22)
            tk.Label(
                hero,
                text="Registre el efectivo con el que comienza el turno. "
                     "Este monto será la base para calcular el efectivo esperado al cierre.",
                bg="#F8FAFC",fg=COLORS["gray"],justify="left",
                wraplength=760,font=("Segoe UI",9)
            ).pack(anchor="w",padx=22,pady=(4,16))

            form=tk.Frame(shell,bg=COLORS["white"])
            form.pack(fill="x",padx=22,pady=18)

            left=tk.Frame(form,bg=COLORS["white"])
            left.pack(side="left",fill="x",expand=True)

            tk.Label(
                left,text="FONDO INICIAL",bg=COLORS["white"],
                fg=COLORS["gray"],font=("Segoe UI",8,"bold")
            ).pack(anchor="w")

            opening_var=tk.StringVar(value="0.00")
            opening_entry=tk.Entry(
                left,textvariable=opening_var,
                font=("Segoe UI",22,"bold"),justify="right",
                relief="solid",bd=1,width=14
            )
            opening_entry.pack(anchor="w",ipady=5,pady=(4,7))

            quick=tk.Frame(left,bg=COLORS["white"])
            quick.pack(anchor="w")

            def set_opening(value):
                opening_var.set(f"{float(value):.2f}")
                opening_entry.focus_set()
                opening_entry.icursor("end")

            for label,value in [("$0",0),("$10",10),("$20",20),("$50",50),("$100",100)]:
                tk.Button(
                    quick,text=label,command=lambda v=value:set_opening(v),
                    bg="#F3F4F6",fg=COLORS["dark"],relief="flat",
                    font=("Segoe UI",9,"bold"),padx=14,pady=6
                ).pack(side="left",padx=(0,5))

            def open_cash():
                try:
                    amount=float(opening_var.get().strip() or 0)
                except ValueError:
                    self.show_app_modal(
                        "Fondo inicial no válido",
                        "Ingrese un monto numérico para abrir la caja.",
                        modal_type="warning",primary_text="CORREGIR"
                    )
                    opening_entry.focus_set()
                    return

                if amount < 0:
                    self.show_app_modal(
                        "Fondo inicial no válido",
                        "El fondo inicial no puede ser negativo.",
                        modal_type="warning",primary_text="CORREGIR"
                    )
                    return

                if not self.show_app_modal(
                    "Abrir caja",
                    "¿Desea iniciar la jornada de caja con este fondo?",
                    modal_type="question",
                    primary_text="ABRIR CAJA",
                    secondary_text="VOLVER",
                    detail=f"Fondo inicial: ${amount:.2f}\nUsuario: {self.user['full_name']}"
                ):
                    return

                self.db.execute(
                    "INSERT INTO cash_sessions(user_id,opened_at,opening_amount,status) VALUES(?,?,?,'OPEN')",
                    (self.user["id"],now_iso(),amount)
                )
                self.load_cash_session()
                self.build_cash()
                self.build_dashboard()
                self.build_sales()
                if self.user["role"]=="admin" and hasattr(self,"tab_reports"):
                    try:self.build_reports()
                    except Exception:pass

            action=tk.Frame(form,bg=COLORS["white"])
            action.pack(side="right",padx=(30,0))
            tk.Button(
                action,text="ABRIR CAJA",command=open_cash,
                bg=COLORS["green"],fg="white",
                font=("Segoe UI",11,"bold"),relief="flat",
                padx=28,pady=13
            ).pack()
            tk.Label(
                action,text="La apertura queda registrada\ncon usuario y hora.",
                bg=COLORS["white"],fg=COLORS["gray"],
                font=("Segoe UI",8),justify="center"
            ).pack(pady=(7,0))

            opening_entry.bind("<Return>",lambda e:open_cash())
            opening_entry.focus_set()
            return

        # -------------------------------
        # CAJA ABIERTA
        # -------------------------------
        sess=self.cash_session

        sold_cash=float(self.db.one(
            """SELECT COALESCE(SUM(total),0) s FROM sales
               WHERE cash_session_id=? AND payment_method='Efectivo'
                 AND status='COMPLETED'""",(sess["id"],)
        )["s"])

        sold_transfer=float(self.db.one(
            """SELECT COALESCE(SUM(total),0) s FROM sales
               WHERE cash_session_id=? AND payment_method='Transferencia'
                 AND status='COMPLETED'""",(sess["id"],)
        )["s"])

        sold_other=float(self.db.one(
            """SELECT COALESCE(SUM(total),0) s FROM sales
               WHERE cash_session_id=? AND payment_method='Otro'
                 AND status='COMPLETED'""",(sess["id"],)
        )["s"])

        approved=float(self.db.one(
            """SELECT COALESCE(SUM(amount),0) s FROM expenses
               WHERE cash_session_id=? AND status='APPROVED'""",(sess["id"],)
        )["s"])

        refunds_cash=float(self.db.one(
            """SELECT COALESCE(SUM(total_refund),0) s FROM sale_returns
               WHERE cash_session_id=? AND refund_method='Efectivo'""",(sess["id"],)
        )["s"])

        cash_inflows=float(self.db.one(
            """SELECT COALESCE(SUM(amount),0) s FROM cash_inflows
               WHERE cash_session_id=?""",(sess["id"],)
        )["s"])

        pending=int(self.db.one(
            """SELECT COUNT(*) c FROM expenses
               WHERE cash_session_id=? AND status='PENDING'""",(sess["id"],)
        )["c"])

        opening=float(sess["opening_amount"])
        expected=opening+sold_cash+cash_inflows-approved-refunds_cash

        hero=tk.Frame(
            self.tab_cash,bg=COLORS["white"],
            highlightthickness=1,highlightbackground="#D1D5DB"
        )
        hero.pack(fill="x",pady=(0,10))

        top=tk.Frame(hero,bg="#F8FAFC")
        top.pack(fill="x")

        title_box=tk.Frame(top,bg="#F8FAFC")
        title_box.pack(side="left",fill="x",expand=True,padx=20,pady=14)
        tk.Label(
            title_box,text="JORNADA DE CAJA EN CURSO",
            bg="#F8FAFC",fg=COLORS["green"],font=("Segoe UI",9,"bold")
        ).pack(anchor="w")
        tk.Label(
            title_box,text=f"Abierta por {self.user['full_name']}",
            bg="#F8FAFC",fg=COLORS["dark"],font=("Segoe UI",15,"bold")
        ).pack(anchor="w")
        tk.Label(
            title_box,text=f"Inicio: {sess['opened_at']}",
            bg="#F8FAFC",fg=COLORS["gray"],font=("Segoe UI",8)
        ).pack(anchor="w",pady=(2,0))
        tk.Label(
            title_box,text=f"Datos actualizados: {datetime.now().strftime('%H:%M:%S')}",
            bg="#F8FAFC",fg=COLORS["gray"],font=("Segoe UI",7)
        ).pack(anchor="w",pady=(1,0))

        expected_box=tk.Frame(top,bg="#F8FAFC")
        expected_box.pack(side="right",padx=22,pady=12)
        tk.Label(
            expected_box,text="EFECTIVO ESPERADO",
            bg="#F8FAFC",fg=COLORS["gray"],font=("Segoe UI",8,"bold")
        ).pack(anchor="e")
        tk.Label(
            expected_box,text=f"${expected:.2f}",
            bg="#F8FAFC",fg=COLORS["dark"],font=("Segoe UI",24,"bold")
        ).pack(anchor="e")

        cards=tk.Frame(self.tab_cash,bg=COLORS["light"])
        cards.pack(fill="x",pady=(0,10))
        for i in range(4):
            cards.grid_columnconfigure(i,weight=1)

        def metric(parent,col,title,value,subtitle="",value_fg=None):
            card=tk.Frame(
                parent,bg=COLORS["white"],
                highlightthickness=1,highlightbackground="#E5E7EB"
            )
            card.grid(row=0,column=col,sticky="nsew",padx=(0 if col==0 else 5,5))
            tk.Label(
                card,text=title,bg=COLORS["white"],fg=COLORS["gray"],
                font=("Segoe UI",8,"bold")
            ).pack(anchor="w",padx=13,pady=(11,2))
            tk.Label(
                card,text=value,bg=COLORS["white"],
                fg=value_fg or COLORS["dark"],font=("Segoe UI",17,"bold")
            ).pack(anchor="w",padx=13)
            tk.Label(
                card,text=subtitle,bg=COLORS["white"],fg=COLORS["gray"],
                font=("Segoe UI",7)
            ).pack(anchor="w",padx=13,pady=(1,10))

        metric(cards,0,"FONDO INICIAL",f"${opening:.2f}","Inicio del turno")
        metric(cards,1,"VENTAS EFECTIVO",f"${sold_cash:.2f}","Ingresan a caja")
        metric(cards,2,"GASTOS APROBADOS",f"${approved:.2f}","Salen de caja",
               COLORS["red"] if approved else COLORS["dark"])
        metric(cards,3,"DEVOLUCIONES",f"${refunds_cash:.2f}","Reembolsos en efectivo",
               COLORS["red"] if refunds_cash else COLORS["dark"])

        detail=tk.Frame(
            self.tab_cash,bg=COLORS["white"],
            highlightthickness=1,highlightbackground="#E5E7EB"
        )
        detail.pack(fill="x",pady=(0,10))
        tk.Label(
            detail,text="Resumen del turno",
            bg=COLORS["white"],fg=COLORS["dark"],font=("Segoe UI",11,"bold")
        ).pack(anchor="w",padx=18,pady=(13,7))

        detail_grid=tk.Frame(detail,bg=COLORS["white"])
        detail_grid.pack(fill="x",padx=18,pady=(0,13))
        detail_grid.grid_columnconfigure(1,weight=1)
        detail_grid.grid_columnconfigure(3,weight=1)

        rows=[
            ("Ventas por transferencia",f"${sold_transfer:.2f}",
             "Ventas por otro medio",f"${sold_other:.2f}"),
            ("Ingresos de caja",f"${cash_inflows:.2f}",
             "Gastos pendientes",str(pending)),
            ("Devoluciones efectivo",f"${refunds_cash:.2f}",
             "Efectivo esperado",f"${expected:.2f}"),
        ]
        for r,row in enumerate(rows):
            tk.Label(detail_grid,text=row[0],bg=COLORS["white"],fg=COLORS["gray"],
                     font=("Segoe UI",9)).grid(row=r,column=0,sticky="w",pady=4)
            tk.Label(detail_grid,text=row[1],bg=COLORS["white"],fg=COLORS["dark"],
                     font=("Segoe UI",9,"bold")).grid(row=r,column=1,sticky="w",padx=(8,25),pady=4)
            tk.Label(detail_grid,text=row[2],bg=COLORS["white"],fg=COLORS["gray"],
                     font=("Segoe UI",9)).grid(row=r,column=2,sticky="w",pady=4)
            tk.Label(detail_grid,text=row[3],bg=COLORS["white"],fg=COLORS["dark"],
                     font=("Segoe UI",9,"bold")).grid(row=r,column=3,sticky="w",padx=(8,0),pady=4)

        action=tk.Frame(
            self.tab_cash,bg=COLORS["white"],
            highlightthickness=1,highlightbackground="#E5E7EB"
        )
        action.pack(fill="x")

        action_text=tk.Frame(action,bg=COLORS["white"])
        action_text.pack(side="left",fill="x",expand=True,padx=18,pady=15)
        tk.Label(
            action_text,text="¿Finalizó el turno?",
            bg=COLORS["white"],fg=COLORS["dark"],font=("Segoe UI",11,"bold")
        ).pack(anchor="w")
        tk.Label(
            action_text,
            text="El corte realizará el arqueo por denominaciones y comparará "
                 "el efectivo contado con el efectivo esperado.",
            bg=COLORS["white"],fg=COLORS["gray"],
            font=("Segoe UI",8),wraplength=650,justify="left"
        ).pack(anchor="w",pady=(2,0))

        def close_cash():
            pending_now=int(self.db.one(
                """SELECT COUNT(*) c FROM expenses
                   WHERE cash_session_id=? AND status='PENDING'""",
                (sess["id"],)
            )["c"])

            if pending_now:
                if self.user["role"]=="admin":
                    self.show_app_modal(
                        "Corte de caja pendiente",
                        f"Hay {pending_now} gasto(s) pendiente(s) de revisión.",
                        modal_type="warning",primary_text="ACEPTAR",
                        detail="Revise la sección Gastos antes de cerrar la caja."
                    )
                else:
                    self.show_app_modal(
                        "Corte de caja pendiente",
                        "Hay gastos pendientes de autorización del gerente.",
                        modal_type="warning",primary_text="ACEPTAR",
                        detail="La caja no puede cerrarse hasta que los gastos sean aprobados o rechazados."
                    )
                return
            self.denomination_count_dialog(sess["id"],expected)

        tk.Button(
            action,text="REALIZAR CORTE DE CAJA",
            command=close_cash,bg=COLORS["red"],fg="white",
            font=("Segoe UI",10,"bold"),relief="flat",
            padx=22,pady=11
        ).pack(side="right",padx=18,pady=15)

    def denomination_count_dialog(self, session_id, expected):
        win=tk.Toplevel(self);win.title("Arqueo por denominaciones");win.geometry("500x650")
        win.minsize(470,600);win.transient(self);win.grab_set()
        box=tk.Frame(win,padx=25,pady=20);box.pack(fill="both",expand=True)

        tk.Label(box,text="Arqueo de caja",font=("Segoe UI",17,"bold")).pack(anchor="w")
        tk.Label(box,text=f"Efectivo esperado: ${expected:.2f}",font=("Segoe UI",12,"bold"),
                 fg=COLORS["green"]).pack(anchor="w",pady=(4,14))

        denoms=[20.00,10.00,5.00,1.00,0.25,0.10,0.05,0.01]
        entries={}
        total_var=tk.StringVar(value="Total contado: $0.00")

        grid=tk.Frame(box);grid.pack(fill="x")
        tk.Label(grid,text="Denominación",font=("Segoe UI",9,"bold")).grid(row=0,column=0,padx=5,pady=5,sticky="w")
        tk.Label(grid,text="Cantidad",font=("Segoe UI",9,"bold")).grid(row=0,column=1,padx=5,pady=5)
        tk.Label(grid,text="Subtotal",font=("Segoe UI",9,"bold")).grid(row=0,column=2,padx=5,pady=5)
        subtotal_vars={}

        def calculate(event=None):
            total=0
            for d,e in entries.items():
                try:q=int(e.get() or 0)
                except:q=0
                sub=d*q;total+=sub
                subtotal_vars[d].set(f"${sub:.2f}")
            total_var.set(f"Total contado: ${total:.2f}")
            return total

        for i,d in enumerate(denoms,1):
            tk.Label(grid,text=f"${d:.2f}",font=("Segoe UI",10)).grid(row=i,column=0,padx=5,pady=5,sticky="w")
            e=tk.Entry(grid,width=10,font=("Segoe UI",11));e.insert(0,"0");e.grid(row=i,column=1,padx=10,pady=5)
            entries[d]=e
            v=tk.StringVar(value="$0.00");subtotal_vars[d]=v
            tk.Label(grid,textvariable=v,font=("Segoe UI",10)).grid(row=i,column=2,padx=10,pady=5,sticky="e")
            e.bind("<KeyRelease>",calculate)

        tk.Label(box,textvariable=total_var,font=("Segoe UI",16,"bold")).pack(anchor="w",pady=(18,4))
        diff_var=tk.StringVar(value=f"Diferencia: ${-expected:.2f}")
        tk.Label(box,textvariable=diff_var,font=("Segoe UI",12,"bold")).pack(anchor="w",pady=(0,12))

        def update_all(event=None):
            total=calculate()
            diff_var.set(f"Diferencia: ${total-expected:.2f}")
        for e in entries.values(): e.bind("<KeyRelease>",update_all)

        def finish():
            counted=calculate()
            breakdown={}
            for d,e in entries.items():
                try:q=int(e.get() or 0)
                except:q=0
                if q<0:
                    self.show_app_modal(
                        "Cantidad no válida",
                        "Las cantidades de billetes y monedas no pueden ser negativas.",
                        modal_type="error",
                        primary_text="CORREGIR"
                    )
                    return
                breakdown[str(d)]=q
            diff=counted-expected
            estado = "CAJA CUADRADA" if abs(diff) < 0.005 else (
                "SOBRANTE" if diff > 0 else "FALTANTE"
            )
            confirm=self.show_app_modal(
                "Confirmar corte de caja",
                "Revise el arqueo antes de cerrar definitivamente la caja.",
                modal_type="question",
                primary_text="CONFIRMAR CORTE",
                secondary_text="VOLVER",
                detail=(
                    f"Efectivo esperado: ${expected:.2f}\n"
                    f"Efectivo contado: ${counted:.2f}\n"
                    f"Diferencia: ${diff:.2f}\n"
                    f"Resultado: {estado}"
                )
            )
            if not confirm:return
            self.db.execute("""UPDATE cash_sessions
                               SET closed_at=?,counted_amount=?,expected_amount=?,difference=?,denominations_json=?,status='CLOSED'
                               WHERE id=?""",
                            (now_iso(),counted,expected,diff,json.dumps(breakdown),session_id))
            win.destroy()
            estado = "Caja cuadrada" if abs(diff) < 0.005 else (
                "Sobrante en caja" if diff > 0 else "Faltante en caja"
            )
            self.show_app_modal(
                "Corte de caja completado",
                "El cierre de caja fue registrado correctamente.",
                modal_type="success" if abs(diff) < 0.005 else "warning",
                primary_text="ACEPTAR",
                detail=(
                    f"Efectivo esperado: ${expected:.2f}\n"
                    f"Efectivo contado: ${counted:.2f}\n"
                    f"Diferencia: ${diff:.2f}\n"
                    f"Resultado: {estado}"
                )
            )
            self.cash_session=None
            self.build_cash()
            self.build_dashboard()
            self.build_sales()
            if self.user["role"]=="admin" and hasattr(self,"tab_reports"):
                try:self.build_reports()
                except Exception:pass

        tk.Button(box,text="CONFIRMAR CORTE",command=finish,bg=COLORS["red"],fg="white",
                  font=("Segoe UI",10,"bold"),relief="flat",pady=10).pack(fill="x",pady=(8,5))
        tk.Button(box,text="Cancelar",command=win.destroy,bg="#E5E7EB",fg=COLORS["dark"],
                  relief="flat",pady=9).pack(fill="x")

    def build_expenses(self):
        for w in self.tab_expenses.winfo_children():
            w.destroy()

        header=tk.Frame(self.tab_expenses,bg=COLORS["light"])
        header.pack(fill="x",pady=(6,10))

        title_box=tk.Frame(header,bg=COLORS["light"])
        title_box.pack(side="left")
        tk.Label(
            title_box,text="Gastos / Movimientos financieros",
            bg=COLORS["light"],fg=COLORS["dark"],
            font=("Segoe UI",18,"bold")
        ).pack(anchor="w")

        privacy_text=(
            "Gerencia: vista global de movimientos."
            if self.user["role"]=="admin"
            else "Vista privada: solo se muestran sus propios movimientos."
        )
        tk.Label(
            title_box,text=privacy_text,
            bg=COLORS["light"],fg=COLORS["gray"],
            font=("Segoe UI",8)
        ).pack(anchor="w",pady=(2,0))

        # ---------------- Registro integrado ----------------
        form_card=tk.Frame(
            self.tab_expenses,bg=COLORS["white"],
            highlightthickness=1,highlightbackground="#D1D5DB"
        )
        form_card.pack(fill="x",pady=(0,10))

        tk.Label(
            form_card,text="REGISTRAR MOVIMIENTO",
            bg=COLORS["white"],fg=COLORS["dark"],
            font=("Segoe UI",11,"bold")
        ).pack(anchor="w",padx=16,pady=(12,3))

        tk.Label(
            form_card,
            text="Registre gastos, salidas de efectivo o ingresos de caja que no provengan de ventas.",
            bg=COLORS["white"],fg=COLORS["gray"],font=("Segoe UI",8)
        ).pack(anchor="w",padx=16,pady=(0,8))

        form=tk.Frame(form_card,bg=COLORS["white"])
        form.pack(fill="x",padx=16,pady=(0,12))

        tk.Label(form,text="Tipo",bg=COLORS["white"],fg=COLORS["gray"],
                 font=("Segoe UI",8,"bold")).grid(row=0,column=0,sticky="w",padx=(0,8))
        type_var=tk.StringVar(value="Gasto")
        type_combo=ttk.Combobox(
            form,textvariable=type_var,state="readonly",
            values=["Gasto","Retiro de caja","Compra menor","Otro movimiento","Ingreso de caja"],
            width=18
        )
        type_combo.grid(row=1,column=0,sticky="ew",padx=(0,8))

        tk.Label(form,text="Descripción",bg=COLORS["white"],fg=COLORS["gray"],
                 font=("Segoe UI",8,"bold")).grid(row=0,column=1,sticky="w",padx=(0,8))
        desc_var=tk.StringVar()
        desc_entry=tk.Entry(form,textvariable=desc_var,font=("Segoe UI",10),relief="solid",bd=1)
        desc_entry.grid(row=1,column=1,sticky="ew",padx=(0,8),ipady=4)

        tk.Label(form,text="Monto",bg=COLORS["white"],fg=COLORS["gray"],
                 font=("Segoe UI",8,"bold")).grid(row=0,column=2,sticky="w",padx=(0,8))
        amount_var=tk.StringVar()
        amount_entry=tk.Entry(
            form,textvariable=amount_var,font=("Segoe UI",12,"bold"),
            justify="right",relief="solid",bd=1,width=12
        )
        amount_entry.grid(row=1,column=2,sticky="ew",padx=(0,8),ipady=3)

        tk.Label(form,text="Nota",bg=COLORS["white"],fg=COLORS["gray"],
                 font=("Segoe UI",8,"bold")).grid(row=0,column=3,sticky="w",padx=(0,8))
        note_var=tk.StringVar()
        note_entry=tk.Entry(form,textvariable=note_var,font=("Segoe UI",10),relief="solid",bd=1)
        note_entry.grid(row=1,column=3,sticky="ew",padx=(0,8),ipady=4)

        form.grid_columnconfigure(1,weight=2)
        form.grid_columnconfigure(3,weight=2)

        register_btn=tk.Button(
            form,text="REGISTRAR MOVIMIENTO",
            bg=COLORS["green"],fg="white",
            font=("Segoe UI",9,"bold"),relief="flat",
            padx=18,pady=8
        )
        register_btn.grid(row=1,column=4,sticky="ew")

        # ---------------- Historial ----------------
        history_card=tk.Frame(
            self.tab_expenses,bg=COLORS["white"],
            highlightthickness=1,highlightbackground="#D1D5DB"
        )
        history_card.pack(fill="both",expand=True)

        history_header=tk.Frame(history_card,bg=COLORS["white"])
        history_header.pack(fill="x",padx=14,pady=(10,6))

        history_title="HISTORIAL DE MOVIMIENTOS" if self.user["role"]=="admin" else "MI HISTORIAL DE MOVIMIENTOS"
        tk.Label(
            history_header,text=history_title,
            bg=COLORS["white"],fg=COLORS["dark"],
            font=("Segoe UI",11,"bold")
        ).pack(side="left")

        summary_var=tk.StringVar(value="")
        tk.Label(
            history_header,textvariable=summary_var,
            bg=COLORS["white"],fg=COLORS["gray"],font=("Segoe UI",8)
        ).pack(side="right")

        filterbar=tk.Frame(history_card,bg=COLORS["white"])
        filterbar.pack(fill="x",padx=14,pady=(0,6))

        tk.Label(filterbar,text="Desde",bg=COLORS["white"],font=("Segoe UI",8,"bold")).pack(side="left")
        from_var=tk.StringVar(value=datetime.now().replace(day=1).strftime("%Y-%m-%d"))
        from_entry=tk.Entry(filterbar,textvariable=from_var,width=12)
        from_entry.pack(side="left",padx=(4,8))

        tk.Label(filterbar,text="Hasta",bg=COLORS["white"],font=("Segoe UI",8,"bold")).pack(side="left")
        to_var=tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        to_entry=tk.Entry(filterbar,textvariable=to_var,width=12)
        to_entry.pack(side="left",padx=(4,8))

        refresh_btn=tk.Button(
            filterbar,text="ACTUALIZAR",
            bg="#E5E7EB",fg=COLORS["dark"],
            font=("Segoe UI",8,"bold"),relief="flat",
            padx=12,pady=4
        )
        refresh_btn.pack(side="left",padx=4)

        scope_label=(
            "Gerencia puede ver movimientos de todos los usuarios."
            if self.user["role"]=="admin"
            else f"Usuario: {self.user['full_name']}"
        )
        tk.Label(
            filterbar,text=scope_label,
            bg=COLORS["white"],fg=COLORS["gray"],
            font=("Segoe UI",8,"bold" if self.user["role"]!="admin" else "normal")
        ).pack(side="right")

        admin_actions=None
        if self.user["role"]=="admin":
            admin_actions=tk.Frame(history_card,bg=COLORS["white"])
            admin_actions.pack(fill="x",padx=14,pady=(0,6))

            tk.Label(
                admin_actions,
                text="Seleccione un movimiento PENDIENTE para aprobarlo o rechazarlo.",
                bg=COLORS["white"],fg=COLORS["gray"],font=("Segoe UI",8)
            ).pack(side="left")

        cols=("id","date","user","type","description","amount","status","note")
        tree=ttk.Treeview(history_card,columns=cols,show="headings",height=12)
        for c,h,w in [
            ("id","ID",55),("date","Fecha",145),("user","Usuario",150),
            ("type","Tipo",120),("description","Descripción",260),
            ("amount","Monto",85),("status","Estado",95),("note","Nota",220)
        ]:
            tree.heading(c,text=h)
            tree.column(c,width=w)
        tree.pack(fill="both",expand=True,padx=14,pady=(0,10))

        def parse_dates():
            try:
                d1=datetime.strptime(from_var.get().strip(),"%Y-%m-%d").date()
                d2=datetime.strptime(to_var.get().strip(),"%Y-%m-%d").date()
                if d1>d2:
                    raise ValueError
                return d1,d2
            except Exception:
                self.show_app_modal(
                    "Fechas no válidas",
                    "Use el formato YYYY-MM-DD y verifique el rango.",
                    modal_type="warning",primary_text="CORREGIR"
                )
                return None,None

        def load_history():
            d1,d2=parse_dates()
            if not d1:
                return

            for item in tree.get_children():
                tree.delete(item)

            if self.user["role"]=="admin":
                rows=self.db.all(
                    """SELECT * FROM (
                           SELECT 'EXPENSE' source,e.id id,e.requested_at fecha,
                                  e.requested_by owner_id,u.full_name usuario,
                                  e.description descripcion,e.amount monto,
                                  e.status estado,e.note nota
                           FROM expenses e
                           JOIN users u ON u.id=e.requested_by

                           UNION ALL

                           SELECT 'INFLOW',ci.id,ci.created_at,
                                  ci.created_by,u.full_name,
                                  'Ingreso de caja | '||ci.concept,
                                  ci.amount,'REGISTRADO',ci.note
                           FROM cash_inflows ci
                           JOIN users u ON u.id=ci.created_by
                       )
                       WHERE date(fecha) BETWEEN date(?) AND date(?)
                       ORDER BY datetime(fecha) DESC LIMIT 3000""",
                    (d1.strftime("%Y-%m-%d"),d2.strftime("%Y-%m-%d"))
                )
            else:
                rows=self.db.all(
                    """SELECT * FROM (
                           SELECT 'EXPENSE' source,e.id id,e.requested_at fecha,
                                  e.requested_by owner_id,u.full_name usuario,
                                  e.description descripcion,e.amount monto,
                                  e.status estado,e.note nota
                           FROM expenses e
                           JOIN users u ON u.id=e.requested_by

                           UNION ALL

                           SELECT 'INFLOW',ci.id,ci.created_at,
                                  ci.created_by,u.full_name,
                                  'Ingreso de caja | '||ci.concept,
                                  ci.amount,'REGISTRADO',ci.note
                           FROM cash_inflows ci
                           JOIN users u ON u.id=ci.created_by
                       )
                       WHERE owner_id=?
                         AND date(fecha) BETWEEN date(?) AND date(?)
                       ORDER BY datetime(fecha) DESC LIMIT 3000""",
                    (self.user["id"],d1.strftime("%Y-%m-%d"),d2.strftime("%Y-%m-%d"))
                )

            total_out=0.0
            total_in=0.0

            for r in rows:
                raw_desc=r["descripcion"] or ""
                if " | " in raw_desc:
                    movement_type,description=raw_desc.split(" | ",1)
                else:
                    movement_type="Gasto"
                    description=raw_desc

                amount=float(r["monto"] or 0)
                if r["source"]=="INFLOW":
                    total_in+=amount
                    display_id=f"I{r['id']}"
                else:
                    total_out+=amount
                    display_id=f"G{r['id']}"

                tree.insert(
                    "","end",
                    values=(
                        display_id,r["fecha"],r["usuario"],
                        movement_type,description,
                        f"${amount:.2f}",
                        r["estado"],r["nota"] or ""
                    ),
                    tags=(r["source"],str(r["id"]))
                )

            scope="todos los usuarios" if self.user["role"]=="admin" else "mis movimientos"
            summary_var.set(
                f"{len(rows)} registro(s) · Ingresos caja ${total_in:.2f} · "
                f"Otros movimientos ${total_out:.2f} · {scope}"
            )

        def register_movement():
            description=desc_var.get().strip()
            note=note_var.get().strip()
            movement_type=type_var.get().strip() or "Gasto"

            if not description:
                self.show_app_modal(
                    "Falta descripción",
                    "Ingrese una descripción para el movimiento.",
                    modal_type="warning",primary_text="CORREGIR"
                )
                desc_entry.focus_set()
                return

            try:
                amount=float(amount_var.get().strip())
            except Exception:
                self.show_app_modal(
                    "Monto no válido",
                    "Ingrese un monto numérico mayor que cero.",
                    modal_type="warning",primary_text="CORREGIR"
                )
                amount_entry.focus_set()
                return

            if amount<=0:
                self.show_app_modal(
                    "Monto no válido",
                    "El monto debe ser mayor que cero.",
                    modal_type="warning",primary_text="CORREGIR"
                )
                return

            # INGRESO DE CAJA: efectivo real recibido fuera de una venta.
            if movement_type=="Ingreso de caja":
                self.load_cash_session()
                if not self.cash_session:
                    self.show_app_modal(
                        "Caja cerrada",
                        "Debe abrir una caja antes de registrar un ingreso de efectivo.",
                        modal_type="warning",primary_text="ACEPTAR",
                        detail=(
                            "El ingreso debe quedar asociado a una jornada de caja "
                            "para que el efectivo esperado y el corte sean correctos."
                        )
                    )
                    return

                if not self.show_app_modal(
                    "Registrar ingreso de caja",
                    "Este dinero aumentará el efectivo esperado de la caja actual.",
                    modal_type="question",
                    primary_text="REGISTRAR",
                    secondary_text="VOLVER",
                    detail=(
                        f"Concepto: {description}\n"
                        f"Monto: ${amount:.2f}\n"
                        f"Usuario: {self.user['full_name']}\n"
                        f"Nota: {note or '-'}\n\n"
                        "No se contabilizará como venta ni como utilidad operativa."
                    )
                ):
                    return

                try:
                    self.db.execute(
                        """INSERT INTO cash_inflows(
                               cash_session_id,concept,amount,note,created_by,created_at
                           ) VALUES(?,?,?,?,?,?)""",
                        (
                            self.cash_session["id"],description,amount,note,
                            self.user["id"],now_iso()
                        )
                    )
                    self.show_app_modal(
                        "Ingreso registrado",
                        "El efectivo fue agregado correctamente a la caja.",
                        modal_type="success",primary_text="ACEPTAR",
                        detail=(
                            f"Concepto: {description}\n"
                            f"Monto: ${amount:.2f}\n"
                            "El efectivo esperado de caja ya incluye este ingreso."
                        )
                    )
                    desc_var.set("")
                    amount_var.set("")
                    note_var.set("")
                    type_var.set("Gasto")
                    load_history()
                    self.build_cash()
                    self.build_dashboard()
                    if self.user["role"]=="admin" and hasattr(self,"tab_finances"):
                        try:self.build_finances()
                        except Exception:pass
                except Exception as e:
                    self.show_app_modal(
                        "No se pudo registrar",str(e),
                        modal_type="error",primary_text="ACEPTAR"
                    )
                return

            status="APPROVED" if self.user["role"]=="admin" else "PENDING"
            approved_by=self.user["id"] if status=="APPROVED" else None
            approved_at=now_iso() if status=="APPROVED" else None
            full_description=f"{movement_type} | {description}"

            try:
                self.db.execute(
                    """INSERT INTO expenses(
                       cash_session_id,description,amount,requested_by,requested_at,
                       status,approved_by,approved_at,note
                       ) VALUES(?,?,?,?,?,?,?,?,?)""",
                    (
                        self.cash_session["id"] if self.cash_session else None,
                        full_description,amount,self.user["id"],now_iso(),
                        status,approved_by,approved_at,note
                    )
                )

                self.show_app_modal(
                    "Movimiento registrado",
                    "El movimiento financiero fue guardado correctamente.",
                    modal_type="success",primary_text="ACEPTAR",
                    detail=(
                        f"Tipo: {movement_type}\n"
                        f"Monto: ${amount:.2f}\n"
                        f"Estado: {'Aprobado' if status=='APPROVED' else 'Pendiente de Gerencia'}"
                    )
                )

                desc_var.set("")
                amount_var.set("")
                note_var.set("")
                type_var.set("Gasto")
                load_history()
                self.build_cash()
                self.build_dashboard()
                if self.user["role"]=="admin" and hasattr(self,"tab_finances"):
                    try:self.build_finances()
                    except Exception:pass

            except Exception as e:
                self.show_app_modal(
                    "No se pudo registrar",str(e),
                    modal_type="error",primary_text="ACEPTAR"
                )

        def selected_expense():
            sel=tree.selection()
            if not sel:
                return None
            tags=tree.item(sel[0],"tags")
            if tags and tags[0]=="INFLOW":
                return None
            try:
                expense_id=int(tags[1]) if len(tags)>1 else int(str(tree.item(sel[0],"values")[0]).lstrip("G"))
            except Exception:
                return None
            return self.db.one(
                """SELECT e.*,u.full_name
                   FROM expenses e
                   JOIN users u ON u.id=e.requested_by
                   WHERE e.id=?""",
                (expense_id,)
            )

        def approve_selected():
            if self.user["role"]!="admin":
                return
            expense=selected_expense()
            if not expense:
                self.show_app_modal(
                    "Seleccione un movimiento",
                    "Seleccione un gasto o egreso PENDIENTE. Los ingresos de caja no requieren aprobación.",
                    modal_type="warning",primary_text="ACEPTAR"
                )
                return
            if expense["status"]!="PENDING":
                self.show_app_modal(
                    "Movimiento ya procesado",
                    f"Este movimiento tiene estado {expense['status']}.",
                    modal_type="info",primary_text="ACEPTAR"
                )
                return

            if not self.show_app_modal(
                "Aprobar movimiento",
                "¿Desea aprobar este movimiento financiero?",
                modal_type="question",
                primary_text="APROBAR",
                secondary_text="VOLVER",
                detail=(
                    f"Empleado: {expense['full_name']}\n"
                    f"Descripción: {expense['description']}\n"
                    f"Monto: ${float(expense['amount']):.2f}"
                )
            ):
                return

            self.db.execute(
                """UPDATE expenses
                   SET status='APPROVED',approved_by=?,approved_at=?
                   WHERE id=? AND status='PENDING'""",
                (self.user["id"],now_iso(),expense["id"])
            )
            self.show_app_modal(
                "Movimiento aprobado",
                "El gasto fue aprobado y ya afecta el efectivo esperado de la caja.",
                modal_type="success",primary_text="ACEPTAR",
                detail=f"Monto aprobado: ${float(expense['amount']):.2f}"
            )
            load_history()
            self.build_cash()
            self.build_dashboard()
            if hasattr(self,"tab_finances"):
                try:self.build_finances()
                except Exception:pass

        def reject_selected():
            if self.user["role"]!="admin":
                return
            expense=selected_expense()
            if not expense:
                self.show_app_modal(
                    "Seleccione un movimiento",
                    "Seleccione un gasto o egreso PENDIENTE. Los ingresos de caja no requieren aprobación.",
                    modal_type="warning",primary_text="ACEPTAR"
                )
                return
            if expense["status"]!="PENDING":
                self.show_app_modal(
                    "Movimiento ya procesado",
                    f"Este movimiento tiene estado {expense['status']}.",
                    modal_type="info",primary_text="ACEPTAR"
                )
                return

            reason=simpledialog.askstring(
                "Rechazar movimiento",
                "Motivo del rechazo:"
            )
            if reason is None:
                return
            reason=reason.strip()

            if not self.show_app_modal(
                "Confirmar rechazo",
                "El movimiento permanecerá en el historial como RECHAZADO y no afectará la caja.",
                modal_type="question",
                primary_text="RECHAZAR",
                secondary_text="VOLVER",
                detail=(
                    f"Empleado: {expense['full_name']}\n"
                    f"Monto: ${float(expense['amount']):.2f}"
                )
            ):
                return

            old_note=expense["note"] or ""
            new_note=(old_note + (" · " if old_note else "") +
                      (f"Rechazo: {reason}" if reason else "Rechazado por Gerencia"))
            self.db.execute(
                """UPDATE expenses
                   SET status='REJECTED',approved_by=?,approved_at=?,note=?
                   WHERE id=? AND status='PENDING'""",
                (self.user["id"],now_iso(),new_note,expense["id"])
            )
            self.show_app_modal(
                "Movimiento rechazado",
                "El movimiento fue rechazado correctamente.",
                modal_type="success",primary_text="ACEPTAR"
            )
            load_history()
            self.build_cash()
            self.build_dashboard()
            if hasattr(self,"tab_finances"):
                try:self.build_finances()
                except Exception:pass

        def open_detail(event=None):
            sel=tree.selection()
            if not sel:
                return

            tags=tree.item(sel[0],"tags")
            source=tags[0] if tags else "EXPENSE"
            try:
                row_id=int(tags[1]) if len(tags)>1 else 0
            except Exception:
                return

            if source=="INFLOW":
                row=self.db.one(
                    """SELECT ci.*,u.full_name
                       FROM cash_inflows ci
                       JOIN users u ON u.id=ci.created_by
                       WHERE ci.id=?""",
                    (row_id,)
                )
                if not row:
                    return

                if self.user["role"]!="admin" and int(row["created_by"])!=int(self.user["id"]):
                    self.show_app_modal(
                        "Acceso restringido",
                        "No puede consultar movimientos de otro usuario.",
                        modal_type="warning",primary_text="ACEPTAR"
                    )
                    return

                self.show_app_modal(
                    f"Ingreso de caja #{row_id}",
                    "Detalle del ingreso de efectivo.",
                    modal_type="info",primary_text="CERRAR",
                    detail=(
                        f"Concepto: {row['concept']}\n"
                        f"Monto: ${float(row['amount']):.2f}\n"
                        f"Usuario: {row['full_name']}\n"
                        f"Fecha: {row['created_at']}\n"
                        f"Nota: {row['note'] or '-'}\n"
                        f"Jornada de caja: #{row['cash_session_id']}\n\n"
                        "Movimiento de efectivo no proveniente de ventas."
                    )
                )
                return

            self.open_expense_detail(row_id)

        if self.user["role"]=="admin" and admin_actions is not None:
            tk.Button(
                admin_actions,text="APROBAR",
                command=approve_selected,
                bg=COLORS["green"],fg="white",
                font=("Segoe UI",9,"bold"),relief="flat",
                padx=16,pady=6
            ).pack(side="right",padx=(5,0))

            tk.Button(
                admin_actions,text="RECHAZAR",
                command=reject_selected,
                bg=COLORS["red"],fg="white",
                font=("Segoe UI",9,"bold"),relief="flat",
                padx=16,pady=6
            ).pack(side="right",padx=5)

        register_btn.configure(command=register_movement)
        refresh_btn.configure(command=load_history)

        tree.bind("<Double-1>",open_detail)
        tree.bind("<Return>",open_detail)
        desc_entry.bind("<Return>",lambda e:amount_entry.focus_set())
        amount_entry.bind("<Return>",lambda e:note_entry.focus_set())
        note_entry.bind("<Return>",lambda e:register_movement())
        from_entry.bind("<Return>",lambda e:load_history())
        to_entry.bind("<Return>",lambda e:load_history())

        load_history()


    def open_expense_detail(self, expense_id):
        expense=self.db.one(
            """SELECT e.*,ru.full_name requested_name,
                      au.full_name approved_name
               FROM expenses e
               JOIN users ru ON ru.id=e.requested_by
               LEFT JOIN users au ON au.id=e.approved_by
               WHERE e.id=?""",
            (expense_id,)
        )
        if not expense:
            return

        if self.user["role"]!="admin" and int(expense["requested_by"])!=int(self.user["id"]):
            self.show_app_modal(
                "Acceso restringido",
                "No puede consultar movimientos de otro usuario.",
                modal_type="warning",primary_text="ACEPTAR"
            )
            return

        raw_desc=expense["description"] or ""
        if " | " in raw_desc:
            movement_type,description=raw_desc.split(" | ",1)
        else:
            movement_type="Gasto"
            description=raw_desc

        detail=(
            f"Tipo: {movement_type}\n"
            f"Descripción: {description}\n"
            f"Monto: ${float(expense['amount']):.2f}\n"
            f"Solicitado por: {expense['requested_name']}\n"
            f"Fecha: {expense['requested_at']}\n"
            f"Estado: {expense['status']}\n"
            f"Procesado por: {expense['approved_name'] or '-'}\n"
            f"Procesado: {expense['approved_at'] or '-'}\n"
            f"Nota: {expense['note'] or '-'}"
        )
        self.show_app_modal(
            f"Movimiento financiero #{expense_id}",
            "Detalle del movimiento registrado.",
            modal_type="info",
            primary_text="CERRAR",
            detail=detail
        )

    def request_expense(self):
        if not self.cash_session:
            messagebox.showwarning("Gastos","Debe existir una caja abierta para registrar un gasto.")
            return
        desc=simpledialog.askstring("Gasto","Descripción del gasto:")
        if not desc:return
        amount=simpledialog.askfloat("Gasto","Monto:",minvalue=0.01)
        if amount is None:return
        self.db.execute("""INSERT INTO expenses(cash_session_id,description,amount,requested_by,requested_at,status)
                           VALUES(?,?,?,?,?,'PENDING')""",(self.cash_session["id"],desc,amount,self.user["id"],now_iso()))
        messagebox.showinfo("Gasto","Gasto registrado como PENDIENTE.\nEl gerente deberá aprobarlo antes del cierre de caja.")
        self.build_expenses();self.build_dashboard()

    def build_users(self):
        for w in self.tab_users.winfo_children(): w.destroy()
        top=tk.Frame(self.tab_users,bg=COLORS["light"]);top.pack(fill="x",pady=8)
        tk.Label(top,text="Empleados y usuarios",font=("Segoe UI",18,"bold"),bg=COLORS["light"]).pack(side="left")
        tk.Button(top,text="+ Añadir empleado",command=self.add_user,bg=COLORS["green"],fg="white",relief="flat").pack(side="right",padx=5)

        cols=("id","name","username","role","schedule","active")
        tree=ttk.Treeview(self.tab_users,columns=cols,show="headings")
        settings=[
            ("id","ID",55),("name","Nombre",250),("username","Usuario",140),
            ("role","Rol",110),("schedule","Jornada",180),("active","Activo",80)
        ]
        for c,h,w in settings:
            tree.heading(c,text=h);tree.column(c,width=w)
        tree.pack(fill="both",expand=True,pady=8)

        for u in self.db.all("SELECT * FROM users ORDER BY full_name"):
            tree.insert("","end",values=(
                u["id"],u["full_name"],u["username"],
                "Gerente" if u["role"]=="admin" else "Empleado",
                u["schedule_type"],"Sí" if u["active"] else "No"
            ))

        actions=tk.Frame(self.tab_users,bg=COLORS["light"]);actions.pack(fill="x",pady=(4,0))

        def selected_user():
            sel=tree.selection()
            if not sel:
                messagebox.showwarning("Empleados","Seleccione un usuario.")
                return None
            user_id=int(tree.item(sel[0],"values")[0])
            return self.db.one("SELECT * FROM users WHERE id=?",(user_id,))

        def edit_selected():
            u=selected_user()
            if u:self.edit_user(u["id"])

        def history_selected(event=None):
            u=selected_user()
            if u:
                self.employee_activity_history(u["id"])

        def toggle_selected():
            u=selected_user()
            if not u:return
            if u["id"] == self.user["id"]:
                messagebox.showwarning("Empleados","No puede desactivar su propia cuenta mientras está conectado.")
                return
            new_active=0 if u["active"] else 1
            self.db.execute("UPDATE users SET active=? WHERE id=?",(new_active,u["id"]))
            self.build_users()

        def delete_selected():
            u=selected_user()
            if not u:return
            if u["id"] == self.user["id"]:
                messagebox.showwarning("Empleados","No puede eliminar la cuenta con la que está conectado.")
                return
            # Protect historical traceability. If the user has activity, soft-delete instead.
            activity = (
                self.db.one("SELECT COUNT(*) c FROM sales WHERE created_by=?",(u["id"],))["c"] +
                self.db.one("SELECT COUNT(*) c FROM purchases WHERE created_by=?",(u["id"],))["c"] +
                self.db.one("SELECT COUNT(*) c FROM expenses WHERE requested_by=? OR approved_by=?",(u["id"],u["id"]))["c"] +
                self.db.one("SELECT COUNT(*) c FROM cash_sessions WHERE user_id=?",(u["id"],))["c"]
            )
            if activity:
                if messagebox.askyesno(
                    "Eliminar empleado",
                    "Este empleado tiene movimientos históricos.\n\n"
                    "Para no perder la auditoría, su cuenta se desactivará y no podrá volver a ingresar.\n"
                    "¿Desea continuar?"
                ):
                    self.db.execute("UPDATE users SET active=0 WHERE id=?",(u["id"],))
                    self.build_users()
                return
            if messagebox.askyesno("Eliminar empleado",f"¿Eliminar definitivamente a {u['full_name']}?"):
                self.db.execute("DELETE FROM users WHERE id=?",(u["id"],))
                self.build_users()

        tk.Button(actions,text="Modificar",command=edit_selected,bg=COLORS["blue"],fg="white",relief="flat",padx=16,pady=7).pack(side="left",padx=5)
        tk.Button(
            actions,text="HISTORIAL DE ACTIVIDAD",command=history_selected,
            bg=COLORS["green"],fg="white",font=("Segoe UI",9,"bold"),
            relief="flat",padx=16,pady=7
        ).pack(side="left",padx=5)
        tk.Button(actions,text="Activar / Desactivar",command=toggle_selected,bg=COLORS["yellow"],fg=COLORS["dark"],relief="flat",padx=16,pady=7).pack(side="left",padx=5)
        tk.Button(actions,text="Eliminar",command=delete_selected,bg=COLORS["red"],fg="white",relief="flat",padx=16,pady=7).pack(side="left",padx=5)

        tree.bind("<Double-1>",history_selected)
        tree.bind("<Return>",history_selected)

        tk.Label(
            actions,
            text="Los empleados con ventas, compras, caja o gastos se desactivan en lugar de borrar su historial.",
            bg=COLORS["light"],fg=COLORS["gray"],font=("Segoe UI",9)
        ).pack(side="right",padx=8)

    def user_form(self, title, user_id=None):
        existing=self.db.one("SELECT * FROM users WHERE id=?",(user_id,)) if user_id else None
        win=tk.Toplevel(self);win.title(title);win.geometry("460x560");win.transient(self);win.grab_set()
        box=tk.Frame(win,padx=24,pady=20);box.pack(fill="both",expand=True)
        tk.Label(box,text=title,font=("Segoe UI",16,"bold")).pack(anchor="w",pady=(0,14))

        entries={}
        values={
            "name": existing["full_name"] if existing else "",
            "username": existing["username"] if existing else "",
            "schedule": existing["schedule_type"] if existing else "",
        }
        for label,key in [("Nombre completo *","name"),("Usuario *","username"),("Jornada / turno","schedule")]:
            tk.Label(box,text=label,font=("Segoe UI",9,"bold")).pack(anchor="w")
            e=tk.Entry(box,font=("Segoe UI",11));e.pack(fill="x",pady=(4,10),ipady=5)
            e.insert(0,values[key]);entries[key]=e

        tk.Label(box,text="Rol",font=("Segoe UI",9,"bold")).pack(anchor="w")
        role=ttk.Combobox(box,state="readonly",values=["employee","admin"])
        role.pack(fill="x",pady=(4,10))
        role.set(existing["role"] if existing else "employee")

        tk.Label(box,text="Contraseña",font=("Segoe UI",9,"bold")).pack(anchor="w")
        password=tk.Entry(box,font=("Segoe UI",11),show="•");password.pack(fill="x",pady=(4,4),ipady=5)
        tk.Label(
            box,
            text="En modificación, déjela vacía para conservar la contraseña actual.",
            font=("Segoe UI",8),fg=COLORS["gray"]
        ).pack(anchor="w",pady=(0,12))

        active_var=tk.BooleanVar(value=bool(existing["active"]) if existing else True)
        tk.Checkbutton(box,text="Usuario activo",variable=active_var).pack(anchor="w",pady=(0,14))

        def save():
            name=entries["name"].get().strip()
            username=entries["username"].get().strip()
            pwd=password.get()
            schedule=entries["schedule"].get().strip()
            if not name or not username:
                messagebox.showerror("Empleado","Nombre y usuario son obligatorios.");return
            if not existing and not pwd:
                messagebox.showerror("Empleado","Debe asignar una contraseña temporal.");return
            try:
                if existing:
                    if existing["id"] == self.user["id"] and not active_var.get():
                        messagebox.showwarning("Empleado","No puede desactivar su propia cuenta.");return
                    if pwd:
                        self.db.execute(
                            """UPDATE users SET full_name=?,username=?,password_hash=?,role=?,schedule_type=?,active=? WHERE id=?""",
                            (name,username,hash_password(pwd),role.get(),schedule,1 if active_var.get() else 0,existing["id"])
                        )
                    else:
                        self.db.execute(
                            """UPDATE users SET full_name=?,username=?,role=?,schedule_type=?,active=? WHERE id=?""",
                            (name,username,role.get(),schedule,1 if active_var.get() else 0,existing["id"])
                        )
                    messagebox.showinfo("Empleado","Datos actualizados correctamente.")
                else:
                    self.db.execute(
                        """INSERT INTO users(full_name,username,password_hash,role,schedule_type,active,created_at)
                           VALUES(?,?,?,?,?,?,?)""",
                        (name,username,hash_password(pwd),role.get(),schedule,1 if active_var.get() else 0,now_iso())
                    )
                    messagebox.showinfo("Empleado","Empleado creado correctamente.")
                win.destroy();self.build_users()
            except sqlite3.IntegrityError:
                messagebox.showerror("Empleado","Ese nombre de usuario ya existe.")

        tk.Button(box,text="Guardar cambios" if existing else "Guardar empleado",
                  command=save,bg=COLORS["green"],fg="white",relief="flat",pady=9).pack(fill="x",pady=8)


    def employee_activity_history(self, user_id):
        if self.user["role"]!="admin":
            return

        employee=self.db.one("SELECT * FROM users WHERE id=?",(user_id,))
        if not employee:
            return

        win=tk.Toplevel(self)
        win.title(f"Historial de actividad - {employee['full_name']}")
        win.geometry("1050x680")
        win.minsize(900,560)
        win.transient(self)
        win.grab_set()

        root=tk.Frame(win,bg=COLORS["light"],padx=18,pady=15)
        root.pack(fill="both",expand=True)

        header=tk.Frame(root,bg=COLORS["light"])
        header.pack(fill="x",pady=(0,10))

        title_box=tk.Frame(header,bg=COLORS["light"])
        title_box.pack(side="left")
        tk.Label(
            title_box,text="Historial de actividad",
            bg=COLORS["light"],fg=COLORS["dark"],
            font=("Segoe UI",17,"bold")
        ).pack(anchor="w")
        tk.Label(
            title_box,
            text=f"{employee['full_name']} · {employee['username']} · "
                 f"{'Gerente' if employee['role']=='admin' else 'Empleado'}",
            bg=COLORS["light"],fg=COLORS["gray"],
            font=("Segoe UI",9)
        ).pack(anchor="w")

        filterbar=tk.Frame(root,bg=COLORS["white"],bd=1,relief="solid")
        filterbar.pack(fill="x",pady=(0,10))

        tk.Label(filterbar,text="Desde",bg="white",font=("Segoe UI",8,"bold")).pack(
            side="left",padx=(10,4),pady=8
        )
        from_var=tk.StringVar(value=datetime.now().replace(day=1).strftime("%Y-%m-%d"))
        from_entry=tk.Entry(filterbar,textvariable=from_var,width=12)
        from_entry.pack(side="left",pady=8)

        tk.Label(filterbar,text="Hasta",bg="white",font=("Segoe UI",8,"bold")).pack(
            side="left",padx=(10,4),pady=8
        )
        to_var=tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        to_entry=tk.Entry(filterbar,textvariable=to_var,width=12)
        to_entry.pack(side="left",pady=8)

        summary_var=tk.StringVar(value="")
        current_rows=[]

        cols=("date","type","reference","detail","amount")
        tree=ttk.Treeview(root,columns=cols,show="headings")
        for c,h,w in [
            ("date","Fecha",155),
            ("type","Actividad",155),
            ("reference","Referencia",115),
            ("detail","Detalle",450),
            ("amount","Importe",100),
        ]:
            tree.heading(c,text=h)
            tree.column(c,width=w)
        tree.pack(fill="both",expand=True)

        tk.Label(
            root,textvariable=summary_var,bg=COLORS["light"],
            fg=COLORS["dark"],font=("Segoe UI",9,"bold")
        ).pack(anchor="w",pady=(6,3))

        def parse_dates():
            try:
                d1=datetime.strptime(from_var.get().strip(),"%Y-%m-%d").date()
                d2=datetime.strptime(to_var.get().strip(),"%Y-%m-%d").date()
                if d1>d2:
                    raise ValueError
                return d1,d2
            except Exception:
                self.show_app_modal(
                    "Fechas no válidas",
                    "Use el formato YYYY-MM-DD y verifique que Desde no sea posterior a Hasta.",
                    modal_type="warning",
                    primary_text="CORREGIR"
                )
                return None,None

        def fetch_rows(d1,d2):
            # El resultado es una bitácora consolidada de las operaciones
            # que ya registran usuario en la base de datos.
            sql="""
            SELECT * FROM (
                SELECT created_at fecha,'Venta' tipo,
                       'Venta #'||id referencia,
                       payment_method||' · Estado: '||status detalle,
                       total importe
                FROM sales WHERE created_by=?

                UNION ALL

                SELECT created_at,'Compra',
                       'Compra #'||id,
                       COALESCE(supplier,'')||
                       CASE WHEN document_no<>'' THEN ' · Doc: '||document_no ELSE '' END,
                       total
                FROM purchases WHERE created_by=?

                UNION ALL

                SELECT created_at,'Producto creado',
                       sku,
                       name||' · '||COALESCE(category,''),
                       NULL
                FROM products WHERE created_by=?

                UNION ALL

                SELECT im.created_at,'Inventario',
                       COALESCE(im.reference_type,'')||
                       CASE WHEN im.reference_id IS NOT NULL THEN ' #'||im.reference_id ELSE '' END,
                       p.name||' · '||im.movement_type||' · Cant: '||printf('%.2f',im.qty)||
                       CASE WHEN im.note<>'' THEN ' · '||im.note ELSE '' END,
                       CASE WHEN im.unit_cost IS NOT NULL THEN ABS(im.qty*im.unit_cost) ELSE NULL END
                FROM inventory_movements im
                JOIN products p ON p.id=im.product_id
                WHERE im.created_by=?

                UNION ALL

                SELECT requested_at,'Gasto solicitado',
                       'Gasto #'||id,
                       description||' · Estado: '||status,
                       amount
                FROM expenses WHERE requested_by=?

                UNION ALL

                SELECT approved_at,'Gasto procesado',
                       'Gasto #'||id,
                       description||' · '||status,
                       amount
                FROM expenses
                WHERE approved_by=? AND approved_at IS NOT NULL

                UNION ALL

                SELECT opened_at,'Caja abierta',
                       'Caja #'||id,
                       'Fondo inicial: $'||printf('%.2f',opening_amount),
                       opening_amount
                FROM cash_sessions WHERE user_id=?

                UNION ALL

                SELECT closed_at,'Corte de caja',
                       'Caja #'||id,
                       'Esperado $'||printf('%.2f',COALESCE(expected_amount,0))||
                       ' · Contado $'||printf('%.2f',COALESCE(counted_amount,0))||
                       ' · Diferencia $'||printf('%.2f',COALESCE(difference,0)),
                       COALESCE(counted_amount,0)
                FROM cash_sessions
                WHERE user_id=? AND closed_at IS NOT NULL

                UNION ALL

                SELECT login_at,'Ingreso al sistema',
                       'Sesión #'||id,
                       'Inicio de sesión',
                       NULL
                FROM user_sessions WHERE user_id=?

                UNION ALL

                SELECT logout_at,'Salida del sistema',
                       'Sesión #'||id,
                       CASE
                         WHEN logout_type<>'' THEN logout_type
                         ELSE 'Cierre de sesión'
                       END,
                       NULL
                FROM user_sessions
                WHERE user_id=? AND logout_at IS NOT NULL

                UNION ALL

                SELECT created_at,'Devolución',
                       'Devolución #'||id,
                       'Venta #'||sale_id||' · '||reason||' · '||refund_method,
                       total_refund
                FROM sale_returns WHERE created_by=?
            )
            WHERE date(fecha) BETWEEN date(?) AND date(?)
            ORDER BY datetime(fecha) DESC
            LIMIT 5000
            """
            params=(
                user_id,user_id,user_id,user_id,user_id,user_id,user_id,user_id,
                user_id,user_id,user_id,
                d1.strftime("%Y-%m-%d"),d2.strftime("%Y-%m-%d")
            )
            return self.db.all(sql,params)

        def load_history():
            nonlocal current_rows
            d1,d2=parse_dates()
            if not d1:
                return

            rows=fetch_rows(d1,d2)
            current_rows=[dict(r) for r in rows]

            for item in tree.get_children():
                tree.delete(item)

            totals={}
            for r in rows:
                amount=r["importe"]
                amount_text="" if amount is None else f"${float(amount):.2f}"
                tree.insert(
                    "","end",
                    values=(r["fecha"],r["tipo"],r["referencia"],r["detalle"],amount_text)
                )
                totals[r["tipo"]]=totals.get(r["tipo"],0)+1

            main_counts=[
                f"{k}: {v}" for k,v in sorted(totals.items())
            ]
            summary_var.set(
                f"{len(rows)} actividad(es) · " +
                (" · ".join(main_counts[:6]) if main_counts else "Sin movimientos en el período")
            )

        def set_month():
            from_var.set(datetime.now().replace(day=1).strftime("%Y-%m-%d"))
            to_var.set(datetime.now().strftime("%Y-%m-%d"))
            load_history()

        def set_all():
            first=self.db.one(
                """SELECT MIN(fecha) fecha FROM (
                    SELECT created_at fecha FROM sales WHERE created_by=?
                    UNION ALL SELECT created_at FROM purchases WHERE created_by=?
                    UNION ALL SELECT created_at FROM products WHERE created_by=?
                    UNION ALL SELECT opened_at FROM cash_sessions WHERE user_id=?
                    UNION ALL SELECT login_at FROM user_sessions WHERE user_id=?
                )""",
                (user_id,user_id,user_id,user_id,user_id)
            )
            from_var.set((first["fecha"][:10] if first and first["fecha"] else "2000-01-01"))
            to_var.set(datetime.now().strftime("%Y-%m-%d"))
            load_history()

        def print_history():
            if not current_rows:
                self.show_app_modal(
                    "Sin información",
                    "No hay actividades visibles para imprimir.",
                    modal_type="warning",
                    primary_text="ACEPTAR"
                )
                return

            rows=[
                (
                    r["fecha"],r["tipo"],r["referencia"],r["detalle"],
                    "" if r["importe"] is None else f"${float(r['importe']):.2f}"
                )
                for r in current_rows
            ]
            self.open_printable_report(
                f"Historial de actividad - {employee['full_name']}",
                ["Fecha","Actividad","Referencia","Detalle","Importe"],
                rows,
                {
                    "Empleado":employee["full_name"],
                    "Usuario":employee["username"],
                    "Rol":"Gerente" if employee["role"]=="admin" else "Empleado",
                    "Desde":from_var.get(),
                    "Hasta":to_var.get(),
                    "Actividades":str(len(rows)),
                }
            )

        tk.Button(
            filterbar,text="APLICAR",command=load_history,
            bg=COLORS["green"],fg="white",relief="flat",
            font=("Segoe UI",8,"bold"),padx=12,pady=5
        ).pack(side="left",padx=8,pady=5)

        tk.Button(
            filterbar,text="ESTE MES",command=set_month,
            bg="#E5E7EB",fg=COLORS["dark"],relief="flat",
            font=("Segoe UI",8,"bold"),padx=10,pady=5
        ).pack(side="left",padx=3,pady=5)

        tk.Button(
            filterbar,text="TODO",command=set_all,
            bg="#E5E7EB",fg=COLORS["dark"],relief="flat",
            font=("Segoe UI",8,"bold"),padx=10,pady=5
        ).pack(side="left",padx=3,pady=5)

        tk.Button(
            filterbar,text="IMPRIMIR HISTORIAL",command=print_history,
            bg=COLORS["blue"],fg="white",relief="flat",
            font=("Segoe UI",8,"bold"),padx=12,pady=5
        ).pack(side="right",padx=8,pady=5)

        from_entry.bind("<Return>",lambda e:load_history())
        to_entry.bind("<Return>",lambda e:load_history())
        load_history()

    def add_user(self):
        self.user_form("Nuevo empleado")

    def edit_user(self, user_id):
        self.user_form("Modificar empleado",user_id)


    def open_sale_detail_report(self, sale_id):
        sale=self.db.one("""SELECT s.*,u.full_name FROM sales s
                            JOIN users u ON u.id=s.created_by WHERE s.id=?""",(sale_id,))
        if not sale:
            return
        items=self.db.all("""SELECT p.sku,p.name,si.*
                             FROM sale_items si JOIN products p ON p.id=si.product_id
                             WHERE si.sale_id=? ORDER BY si.id""",(sale_id,))
        rows=[]
        for i in items:
            qty=float(i["sale_qty"] if i["sale_qty"] is not None else i["qty"])
            price=float(i["display_unit_price"] if i["display_unit_price"] is not None else i["unit_price"])
            subtotal=qty*price

            addon_rows=self.db.all(
                """SELECT addon_name,extra_price
                   FROM sale_item_addons
                   WHERE sale_item_id=?
                   ORDER BY id""",
                (i["id"],)
            )
            addons_text=", ".join(
                f"{a['addon_name']} (+${float(a['extra_price']):.2f})"
                for a in addon_rows
            ) or "-"

            rows.append((
                i["sku"],i["name"],i["presentation_name"] or "",
                addons_text,
                f"{qty:.2f}",f"${price:.2f}",f"${subtotal:.2f}"
            ))
        summary={
            "Venta":f"#{sale_id}",
            "Fecha":sale["created_at"],
            "Cajero":sale["full_name"],
            "Forma de pago":sale["payment_method"],
            "Total":f"${float(sale['total']):.2f}",
            "Estado":sale["status"],
        }
        if sale["payment_method"]=="Efectivo":
            summary["Recibido"]=f"${float(sale['amount_received'] or 0):.2f}"
            summary["Cambio"]=f"${float(sale['change_given'] or 0):.2f}"
        self.open_printable_report(
            f"Detalle de venta #{sale_id}",
            ["Código","Producto","Presentación","Adicionales","Cantidad","Precio","Subtotal"],
            rows,summary
        )

    def open_cash_cut_report(self, cut_id):
        cut=self.db.one("""SELECT c.*,u.full_name FROM cash_sessions c
                           JOIN users u ON u.id=c.user_id WHERE c.id=?""",(cut_id,))
        if not cut:
            return
        sales=self.db.all("""SELECT id,created_at,payment_method,total,status
                             FROM sales WHERE cash_session_id=? ORDER BY id""",(cut_id,))
        rows=[(
            s["id"],s["created_at"],s["payment_method"],
            f"${float(s['total']):.2f}",s["status"]
        ) for s in sales]
        expenses=float(self.db.one(
            "SELECT COALESCE(SUM(amount),0) s FROM expenses WHERE cash_session_id=? AND status='APPROVED'",
            (cut_id,)
        )["s"])
        summary={
            "Empleado":cut["full_name"],
            "Apertura":cut["opened_at"],
            "Cierre":cut["closed_at"] or "",
            "Fondo inicial":f"${float(cut['opening_amount'] or 0):.2f}",
            "Esperado":f"${float(cut['expected_amount'] or 0):.2f}",
            "Contado":f"${float(cut['counted_amount'] or 0):.2f}",
            "Diferencia":f"${float(cut['difference'] or 0):.2f}",
            "Gastos aprobados":f"${expenses:.2f}",
        }
        self.open_printable_report(
            f"Corte de caja #{cut_id}",
            ["Venta","Fecha","Pago","Total","Estado"],
            rows,summary
        )


    def build_returns(self):
        for w in self.tab_returns.winfo_children():
            w.destroy()

        tk.Label(
            self.tab_returns,text="Devoluciones / Anulaciones",
            font=("Segoe UI",18,"bold"),bg=COLORS["light"]
        ).pack(anchor="w",pady=(6,2))
        tk.Label(
            self.tab_returns,
            text="La venta original se conserva para auditoría. Las devoluciones generan un registro separado.",
            bg=COLORS["light"],fg=COLORS["gray"],font=("Segoe UI",9)
        ).pack(anchor="w",pady=(0,8))

        # Barra fija de acciones. Se reserva primero en la parte inferior
        # para que nunca quede oculta por las tablas en pantallas 1366x720.
        returns_actions=tk.Frame(self.tab_returns,bg=COLORS["light"])
        returns_actions.pack(side="bottom",fill="x",pady=(6,2))

        search=tk.Frame(self.tab_returns,bg="white",bd=1,relief="solid")
        search.pack(fill="x",pady=(0,8))
        tk.Label(search,text="Venta #",bg="white",font=("Segoe UI",9,"bold")).pack(side="left",padx=(10,5),pady=8)
        sale_search=tk.Entry(search,width=10)
        sale_search.pack(side="left",pady=8)
        tk.Label(search,text="Deje vacío para mostrar las últimas ventas.",bg="white",
                 fg=COLORS["gray"],font=("Segoe UI",8)).pack(side="left",padx=8)

        top_cols=("id","date","cashier","total","returned","status")
        sales_tree=ttk.Treeview(self.tab_returns,columns=top_cols,show="headings",height=6)
        for c,h,w in [
            ("id","Venta",65),("date","Fecha",150),("cashier","Empleado",180),
            ("total","Total",90),("returned","Devuelto",90),("status","Estado",100)
        ]:
            sales_tree.heading(c,text=h);sales_tree.column(c,width=w)
        sales_tree.pack(fill="x",pady=(0,8))

        tk.Label(self.tab_returns,text="Artículos de la venta",bg=COLORS["light"],
                 font=("Segoe UI",11,"bold")).pack(anchor="w")

        item_cols=("item_id","product","presentation","sold","returned","available","price")
        item_tree=ttk.Treeview(self.tab_returns,columns=item_cols,show="headings")
        for c,h,w in [
            ("item_id","Item",55),("product","Producto",240),("presentation","Presentación",140),
            ("sold","Vendido",80),("returned","Devuelto",80),("available","Disponible",90),
            ("price","Precio",90)
        ]:
            item_tree.heading(c,text=h);item_tree.column(c,width=w)
        item_tree.pack(fill="both",expand=True,pady=(3,8))

        status_var=tk.StringVar(value="")
        tk.Label(self.tab_returns,textvariable=status_var,bg=COLORS["light"],
                 font=("Segoe UI",9,"bold")).pack(anchor="w",pady=(0,4))

        def load_sales():
            for x in sales_tree.get_children():sales_tree.delete(x)
            q=sale_search.get().strip()
            if q:
                if not q.isdigit():
                    messagebox.showwarning("Devoluciones","El número de venta debe ser numérico.")
                    return
                rows=self.db.all(
                    """SELECT s.*,u.full_name,
                              COALESCE((SELECT SUM(sr.total_refund) FROM sale_returns sr WHERE sr.sale_id=s.id),0) returned_total
                       FROM sales s
                       LEFT JOIN users u ON u.id=s.created_by
                       WHERE s.id=?
                       ORDER BY s.id DESC""",(int(q),)
                )
            else:
                rows=self.db.all(
                    """SELECT s.*,u.full_name,
                              COALESCE((SELECT SUM(sr.total_refund) FROM sale_returns sr WHERE sr.sale_id=s.id),0) returned_total
                       FROM sales s
                       LEFT JOIN users u ON u.id=s.created_by
                       ORDER BY s.id DESC LIMIT 100"""
                )
            for r in rows:
                sales_tree.insert("","end",values=(
                    r["id"],r["created_at"],r["full_name"] or "",
                    f"${float(r['total']):.2f}",f"${float(r['returned_total']):.2f}",
                    r["status"]
                ))

        def selected_sale_id():
            sel=sales_tree.selection()
            return int(sales_tree.item(sel[0],"values")[0]) if sel else None

        def load_items(event=None):
            for x in item_tree.get_children():item_tree.delete(x)
            sid=selected_sale_id()
            if not sid:
                status_var.set("")
                return
            sale=self.db.one("SELECT * FROM sales WHERE id=?",(sid,))
            items=self.db.all(
                """SELECT si.*,p.name,p.product_type
                   FROM sale_items si
                   JOIN products p ON p.id=si.product_id
                   WHERE si.sale_id=? ORDER BY si.id""",(sid,)
            )
            for i in items:
                sold_qty=float(i["sale_qty"] if i["sale_qty"] is not None else i["qty"])
                rr=self.db.one(
                    "SELECT COALESCE(SUM(sale_qty_returned),0) q FROM sale_return_items WHERE sale_item_id=?",
                    (i["id"],)
                )
                returned=float(rr["q"] or 0)
                available=max(0.0,sold_qty-returned)
                price=float(i["display_unit_price"] if i["display_unit_price"] is not None else i["unit_price"])
                item_tree.insert("","end",values=(
                    i["id"],i["name"],i["presentation_name"] or "",
                    f"{sold_qty:.2f}",f"{returned:.2f}",f"{available:.2f}",f"${price:.2f}"
                ))
            status_var.set(
                "Venta anulada." if sale and sale["status"]=="VOIDED"
                else "Seleccione un artículo para devolver o anule la venta completa."
            )

        def return_selected_item():
            sid=selected_sale_id()
            isel=item_tree.selection()
            if not sid or not isel:
                messagebox.showwarning("Devolución","Seleccione una venta y un artículo.")
                return
            sale=self.db.one("SELECT * FROM sales WHERE id=?",(sid,))
            if not sale or sale["status"]!="COMPLETED":
                messagebox.showwarning("Devolución","Solo se pueden devolver artículos de ventas completadas.")
                return

            item_id=int(item_tree.item(isel[0],"values")[0])
            item=self.db.one(
                """SELECT si.*,p.name,p.product_type
                   FROM sale_items si JOIN products p ON p.id=si.product_id
                   WHERE si.id=?""",(item_id,)
            )
            sold_qty=float(item["sale_qty"] if item["sale_qty"] is not None else item["qty"])
            already=float(self.db.one(
                "SELECT COALESCE(SUM(sale_qty_returned),0) q FROM sale_return_items WHERE sale_item_id=?",
                (item_id,)
            )["q"])
            available=max(0.0,sold_qty-already)
            if available<=0:
                messagebox.showinfo("Devolución","Este artículo ya fue devuelto completamente.")
                return

            q=simpledialog.askfloat(
                "Cantidad a devolver",
                f"Producto: {item['name']}\\nDisponible para devolución: {available:.2f}\\n\\nCantidad:",
                minvalue=0.0001,maxvalue=available
            )
            if q is None:return

            reason=simpledialog.askstring("Motivo","Motivo de la devolución:")
            if not reason:return

            methods=["Efectivo","Transferencia","Otro"]
            method=sale["payment_method"] if sale["payment_method"] in methods else "Otro"
            if not messagebox.askyesno(
                "Confirmar devolución",
                f"Venta #{sid}\\n{item['name']}\\nCantidad: {q:.2f}\\n"
                f"Reembolso por: {method}\\n\\n¿Registrar devolución?"
            ):
                return

            try:
                cur=self.db.conn.cursor()
                ratio=q/sold_qty if sold_qty else 0
                inventory_qty=float(item["qty"] or 0)*ratio
                unit_refund=float(item["display_unit_price"] if item["display_unit_price"] is not None else item["unit_price"])
                refund=q*unit_refund

                # Costo principal según asignaciones FIFO originales.
                main_cost=float(self.db.one(
                    "SELECT COALESCE(SUM(qty*unit_cost),0) c FROM sale_cost_allocations WHERE sale_item_id=?",
                    (item_id,)
                )["c"])
                main_cost_return=main_cost*ratio

                cur.execute(
                    """INSERT INTO sale_returns(
                       sale_id,cash_session_id,refund_method,total_refund,reason,created_by,created_at
                       ) VALUES(?,?,?,?,?,?,?)""",
                    (
                        sid,
                        self.cash_session["id"] if self.cash_session else None,
                        method,refund,reason,self.user["id"],now_iso()
                    )
                )
                return_id=cur.lastrowid
                cur.execute(
                    """INSERT INTO sale_return_items(
                       return_id,sale_item_id,product_id,sale_qty_returned,
                       inventory_qty_returned,refund_amount,cost_amount
                       ) VALUES(?,?,?,?,?,?,?)""",
                    (return_id,item_id,item["product_id"],q,inventory_qty,refund,main_cost_return)
                )

                # Restaurar producto principal como lote de devolución.
                if item["product_type"]!="SERVICE" and inventory_qty>0:
                    unit_cost=(main_cost_return/inventory_qty) if inventory_qty else 0
                    cur.execute(
                        """INSERT INTO inventory_lots(
                           product_id,purchase_item_id,qty_received,qty_remaining,unit_cost,created_at
                           ) VALUES(?,NULL,?,?,?,?)""",
                        (item["product_id"],inventory_qty,inventory_qty,unit_cost,now_iso())
                    )
                    self.db.log_inventory(
                        item["product_id"],"DEVOLUCION_CLIENTE",inventory_qty,unit_cost,
                        "RETURN",return_id,reason,self.user["id"]
                    )

                # Restaurar componentes inventariables de adicionales proporcionalmente.
                addons=self.db.all(
                    """SELECT * FROM sale_item_addons
                       WHERE sale_item_id=? AND component_product_id IS NOT NULL
                         AND component_qty>0""",(item_id,)
                )
                for a in addons:
                    comp_qty=float(a["component_qty"] or 0)*ratio
                    comp_cost=float(a["component_cost"] or 0)*ratio
                    if comp_qty<=0:continue
                    comp_unit=comp_cost/comp_qty if comp_qty else 0
                    cur.execute(
                        """INSERT INTO inventory_lots(
                           product_id,purchase_item_id,qty_received,qty_remaining,unit_cost,created_at
                           ) VALUES(?,NULL,?,?,?,?)""",
                        (a["component_product_id"],comp_qty,comp_qty,comp_unit,now_iso())
                    )
                    self.db.log_inventory(
                        a["component_product_id"],"DEVOLUCION_ADICIONAL",comp_qty,comp_unit,
                        "RETURN",return_id,f"{reason} · {a['addon_name']}",self.user["id"]
                    )

                self.db.conn.commit()
                messagebox.showinfo(
                    "Devolución registrada",
                    f"Devolución #{return_id} registrada.\\nReembolso: ${refund:.2f}"
                )
                load_sales();load_items();self.build_products();self.build_dashboard();self.build_cash()
            except Exception as e:
                self.db.conn.rollback()
                messagebox.showerror("Devolución",f"No se pudo registrar.\\n{e}")

        def void_selected_sale():
            sid=selected_sale_id()
            if not sid:
                messagebox.showwarning("Anulación","Seleccione una venta.")
                return
            sale=self.db.one("SELECT * FROM sales WHERE id=?",(sid,))
            if not sale or sale["status"]!="COMPLETED":
                messagebox.showinfo("Anulación","La venta ya está anulada o no está disponible.")
                return
            previous_returns=float(self.db.one(
                "SELECT COALESCE(SUM(total_refund),0) r FROM sale_returns WHERE sale_id=?",(sid,)
            )["r"])
            if previous_returns>0:
                messagebox.showwarning(
                    "Anulación",
                    "Esta venta ya tiene devoluciones parciales. Devuelva los artículos restantes en lugar de anularla."
                )
                return
            reason=simpledialog.askstring("Anular venta","Motivo de la anulación completa:")
            if not reason:return
            if not messagebox.askyesno(
                "Confirmar anulación",
                f"¿Anular completamente la venta #{sid}?\\n"
                "Se restaurarán productos y componentes de adicionales al inventario."
            ):
                return
            try:
                cur=self.db.conn.cursor()
                items=self.db.all(
                    """SELECT si.*,p.product_type
                       FROM sale_items si JOIN products p ON p.id=si.product_id
                       WHERE si.sale_id=?""",(sid,)
                )
                for item in items:
                    if item["product_type"]!="SERVICE" and float(item["qty"] or 0)>0:
                        main_cost=float(self.db.one(
                            "SELECT COALESCE(SUM(qty*unit_cost),0) c FROM sale_cost_allocations WHERE sale_item_id=?",
                            (item["id"],)
                        )["c"])
                        unit_cost=main_cost/float(item["qty"]) if item["qty"] else 0
                        cur.execute(
                            """INSERT INTO inventory_lots(
                               product_id,purchase_item_id,qty_received,qty_remaining,unit_cost,created_at
                               ) VALUES(?,NULL,?,?,?,?)""",
                            (item["product_id"],item["qty"],item["qty"],unit_cost,now_iso())
                        )
                        self.db.log_inventory(
                            item["product_id"],"ANULACION_VENTA",item["qty"],unit_cost,
                            "SALE",sid,reason,self.user["id"]
                        )

                    addons=self.db.all(
                        """SELECT * FROM sale_item_addons
                           WHERE sale_item_id=? AND component_product_id IS NOT NULL
                             AND component_qty>0""",(item["id"],)
                    )
                    for a in addons:
                        cq=float(a["component_qty"] or 0)
                        cc=float(a["component_cost"] or 0)
                        cu=cc/cq if cq else 0
                        cur.execute(
                            """INSERT INTO inventory_lots(
                               product_id,purchase_item_id,qty_received,qty_remaining,unit_cost,created_at
                               ) VALUES(?,NULL,?,?,?,?)""",
                            (a["component_product_id"],cq,cq,cu,now_iso())
                        )
                        self.db.log_inventory(
                            a["component_product_id"],"ANULACION_ADICIONAL",cq,cu,
                            "SALE",sid,f"{reason} · {a['addon_name']}",self.user["id"]
                        )

                cur.execute(
                    """UPDATE sales
                       SET status='VOIDED',voided_by=?,voided_at=?,void_reason=?
                       WHERE id=?""",
                    (self.user["id"],now_iso(),reason,sid)
                )
                self.db.conn.commit()
                messagebox.showinfo("Anulación","Venta anulada e inventario restaurado.")
                load_sales();load_items();self.build_products();self.build_dashboard();self.build_cash()
            except Exception as e:
                self.db.conn.rollback()
                messagebox.showerror("Anulación",f"No se pudo anular.\\n{e}")

        tk.Button(
            search,text="BUSCAR",command=load_sales,
            bg=COLORS["green"],fg="white",relief="flat",padx=14,pady=5
        ).pack(side="left",padx=5,pady=6)

        tk.Button(
            returns_actions,text="DEVOLVER ITEM SELECCIONADO",command=return_selected_item,
            bg=COLORS["blue"],fg="white",font=("Segoe UI",9,"bold"),
            relief="flat",padx=16,pady=8
        ).pack(side="left",padx=(0,6))

        tk.Button(
            returns_actions,text="ANULAR VENTA COMPLETA",command=void_selected_sale,
            bg=COLORS["red"],fg="white",font=("Segoe UI",9,"bold"),
            relief="flat",padx=16,pady=8
        ).pack(side="left",padx=6)

        tk.Button(
            returns_actions,text="ACTUALIZAR",command=lambda:(load_sales(),load_items()),
            bg="#E5E7EB",fg=COLORS["dark"],font=("Segoe UI",9,"bold"),
            relief="flat",padx=14,pady=8
        ).pack(side="left",padx=6)

        tk.Label(
            returns_actions,
            text="Seleccione una venta y luego un artículo para devolver.",
            bg=COLORS["light"],fg=COLORS["gray"],font=("Segoe UI",8)
        ).pack(side="right",padx=8)

        sales_tree.bind("<<TreeviewSelect>>",load_items)
        sale_search.bind("<Return>",lambda e:load_sales())
        load_sales()


    def build_finances(self):
        if self.user["role"]!="admin":
            return

        for w in self.tab_finances.winfo_children():
            w.destroy()

        tk.Label(
            self.tab_finances,text="Finanzas",
            font=("Segoe UI",18,"bold"),
            bg=COLORS["light"],fg=COLORS["dark"]
        ).pack(anchor="w",pady=(6,2))

        tk.Label(
            self.tab_finances,
            text="Consolidado financiero de ventas, compras, gastos, devoluciones y controles de caja.",
            bg=COLORS["light"],fg=COLORS["gray"],font=("Segoe UI",8)
        ).pack(anchor="w",pady=(0,8))

        # ---------------- Filtros ----------------
        filterbar=tk.Frame(
            self.tab_finances,bg=COLORS["white"],
            highlightthickness=1,highlightbackground="#D1D5DB"
        )
        filterbar.pack(fill="x",pady=(0,8))

        today=datetime.now().date()
        from_var=tk.StringVar(value=today.replace(day=1).strftime("%Y-%m-%d"))
        to_var=tk.StringVar(value=today.strftime("%Y-%m-%d"))
        type_var=tk.StringVar(value="Todos")

        top=tk.Frame(filterbar,bg=COLORS["white"])
        top.pack(fill="x",padx=10,pady=7)

        tk.Label(top,text="Desde",bg="white",font=("Segoe UI",8,"bold")).pack(side="left")
        from_entry=tk.Entry(top,textvariable=from_var,width=12)
        from_entry.pack(side="left",padx=(4,8))

        tk.Label(top,text="Hasta",bg="white",font=("Segoe UI",8,"bold")).pack(side="left")
        to_entry=tk.Entry(top,textvariable=to_var,width=12)
        to_entry.pack(side="left",padx=(4,8))

        tk.Label(top,text="Tipo",bg="white",font=("Segoe UI",8,"bold")).pack(side="left")
        type_combo=ttk.Combobox(
            top,textvariable=type_var,state="readonly",width=18,
            values=[
                "Todos","Venta","Ingreso de caja","Compra","Gasto","Devolución",
                "Apertura de caja","Corte de caja"
            ]
        )
        type_combo.pack(side="left",padx=(4,8))

        # ---------------- Resumen ----------------
        summary=tk.Frame(self.tab_finances,bg=COLORS["light"])
        summary.pack(fill="x",pady=(0,8))
        for i in range(4):
            summary.grid_columnconfigure(i,weight=1)

        income_var=tk.StringVar(value="$0.00")
        expense_var=tk.StringVar(value="$0.00")
        net_var=tk.StringVar(value="$0.00")
        pending_var=tk.StringVar(value="$0.00")

        def finance_card(col,title,var,subtitle):
            card=tk.Frame(
                summary,bg=COLORS["white"],
                highlightthickness=1,highlightbackground="#E5E7EB"
            )
            card.grid(row=0,column=col,sticky="nsew",padx=(0 if col==0 else 5,5))
            tk.Label(
                card,text=title,bg=COLORS["white"],
                fg=COLORS["gray"],font=("Segoe UI",8,"bold")
            ).pack(anchor="w",padx=12,pady=(9,1))
            tk.Label(
                card,textvariable=var,bg=COLORS["white"],
                fg=COLORS["dark"],font=("Segoe UI",17,"bold")
            ).pack(anchor="w",padx=12)
            tk.Label(
                card,text=subtitle,bg=COLORS["white"],
                fg=COLORS["gray"],font=("Segoe UI",7)
            ).pack(anchor="w",padx=12,pady=(1,9))

        finance_card(0,"INGRESOS DE EFECTIVO",income_var,"Ventas + ingresos de caja")
        finance_card(1,"EGRESOS",expense_var,"Compras + gastos + devoluciones")
        finance_card(2,"FLUJO NETO",net_var,"Entradas menos salidas de dinero")
        finance_card(3,"GASTOS PENDIENTES",pending_var,"Aún no afectan caja")

        # ---------------- Estado de Resultados ----------------
        results_card=tk.Frame(
            self.tab_finances,bg=COLORS["white"],
            highlightthickness=1,highlightbackground="#D1D5DB"
        )
        results_card.pack(fill="x",pady=(0,8))

        results_header=tk.Frame(results_card,bg=COLORS["white"])
        results_header.pack(fill="x",padx=12,pady=(9,5))

        tk.Label(
            results_header,text="ESTADO DE RESULTADOS",
            bg=COLORS["white"],fg=COLORS["dark"],
            font=("Segoe UI",11,"bold")
        ).pack(side="left")

        tk.Label(
            results_header,
            text="Utilidad basada en costo FIFO/PEPS de lo realmente vendido",
            bg=COLORS["white"],fg=COLORS["gray"],
            font=("Segoe UI",8)
        ).pack(side="right")

        result_grid=tk.Frame(results_card,bg=COLORS["white"])
        result_grid.pack(fill="x",padx=12,pady=(0,10))
        for i in range(7):
            result_grid.grid_columnconfigure(i,weight=1)

        gross_sales_var=tk.StringVar(value="$0.00")
        returns_var=tk.StringVar(value="$0.00")
        net_sales_var=tk.StringVar(value="$0.00")
        cogs_var=tk.StringVar(value="$0.00")
        gross_profit_var=tk.StringVar(value="$0.00")
        operating_expenses_var=tk.StringVar(value="$0.00")
        operating_profit_var=tk.StringVar(value="$0.00")
        gross_margin_var=tk.StringVar(value="0.00%")
        net_margin_var=tk.StringVar(value="0.00%")

        def result_metric(col,title,var):
            box=tk.Frame(result_grid,bg="#F8FAFC")
            box.grid(row=0,column=col,sticky="nsew",padx=3)
            tk.Label(
                box,text=title,bg="#F8FAFC",fg=COLORS["gray"],
                font=("Segoe UI",7,"bold"),wraplength=125
            ).pack(padx=7,pady=(7,1))
            tk.Label(
                box,textvariable=var,bg="#F8FAFC",fg=COLORS["dark"],
                font=("Segoe UI",11,"bold")
            ).pack(padx=7,pady=(0,7))

        result_metric(0,"VENTAS BRUTAS",gross_sales_var)
        result_metric(1,"DEVOLUCIONES",returns_var)
        result_metric(2,"VENTAS NETAS",net_sales_var)
        result_metric(3,"COSTO VENDIDO FIFO",cogs_var)
        result_metric(4,"UTILIDAD BRUTA",gross_profit_var)
        result_metric(5,"GASTOS OPERATIVOS",operating_expenses_var)
        result_metric(6,"UTILIDAD NETA OPERATIVA",operating_profit_var)

        margin_line=tk.Frame(results_card,bg=COLORS["white"])
        margin_line.pack(fill="x",padx=15,pady=(0,9))
        tk.Label(
            margin_line,text="Margen bruto:",
            bg="white",fg=COLORS["gray"],font=("Segoe UI",8,"bold")
        ).pack(side="left")
        tk.Label(
            margin_line,textvariable=gross_margin_var,
            bg="white",fg=COLORS["dark"],font=("Segoe UI",9,"bold")
        ).pack(side="left",padx=(4,18))
        tk.Label(
            margin_line,text="Margen neto operativo:",
            bg="white",fg=COLORS["gray"],font=("Segoe UI",8,"bold")
        ).pack(side="left")
        tk.Label(
            margin_line,textvariable=net_margin_var,
            bg="white",fg=COLORS["dark"],font=("Segoe UI",9,"bold")
        ).pack(side="left",padx=4)

        # ---------------- Barra fija de impresión ----------------
        print_bar=tk.Frame(self.tab_finances,bg=COLORS["light"])
        print_bar.pack(side="bottom",fill="x",pady=(6,2))

        # ---------------- Tabla ----------------
        cols=("date","type","direction","reference","user","detail","amount","status")
        tree=ttk.Treeview(self.tab_finances,columns=cols,show="headings")
        for c,h,w in [
            ("date","Fecha",145),("type","Tipo",110),("direction","Movimiento",85),
            ("reference","Referencia",105),("user","Usuario",140),
            ("detail","Detalle",330),("amount","Monto",90),("status","Estado",95)
        ]:
            tree.heading(c,text=h)
            tree.column(c,width=w)
        tree.pack(fill="both",expand=True,pady=(0,7))

        current_rows=[]

        def parse_dates():
            try:
                d1=datetime.strptime(from_var.get().strip(),"%Y-%m-%d").date()
                d2=datetime.strptime(to_var.get().strip(),"%Y-%m-%d").date()
                if d1>d2:
                    raise ValueError
                return d1,d2
            except Exception:
                self.show_app_modal(
                    "Fechas no válidas",
                    "Use el formato YYYY-MM-DD y verifique el rango.",
                    modal_type="warning",primary_text="CORREGIR"
                )
                return None,None

        def fetch_movements(d1,d2):
            # effect:
            # +1 ingreso, -1 egreso, 0 control/no afecta resultado.
            sql="""
            SELECT * FROM (
                SELECT s.created_at fecha,'Venta' tipo,'INGRESO' direccion,
                       'Venta #'||s.id referencia,
                       u.full_name usuario,
                       s.payment_method||' · Venta completada' detalle,
                       s.total monto,'COMPLETED' estado,1 efecto
                FROM sales s
                JOIN users u ON u.id=s.created_by
                WHERE s.status='COMPLETED'

                UNION ALL

                SELECT ci.created_at,'Ingreso de caja','INGRESO',
                       'Ingreso #'||ci.id,
                       u.full_name,
                       ci.concept||
                       CASE WHEN ci.note<>'' THEN ' · '||ci.note ELSE '' END,
                       ci.amount,'REGISTRADO',1
                FROM cash_inflows ci
                JOIN users u ON u.id=ci.created_by

                UNION ALL

                SELECT p.created_at,'Compra','EGRESO',
                       'Compra #'||p.id,
                       u.full_name,
                       COALESCE(p.supplier,'')||
                       CASE WHEN p.document_no<>'' THEN ' · Doc: '||p.document_no ELSE '' END,
                       p.total,'REGISTRADA',-1
                FROM purchases p
                JOIN users u ON u.id=p.created_by

                UNION ALL

                SELECT e.requested_at,'Gasto',
                       CASE WHEN e.status='APPROVED' THEN 'EGRESO' ELSE 'PENDIENTE' END,
                       'Gasto #'||e.id,
                       u.full_name,
                       e.description,
                       e.amount,e.status,
                       CASE WHEN e.status='APPROVED' THEN -1 ELSE 0 END
                FROM expenses e
                JOIN users u ON u.id=e.requested_by
                WHERE e.status<>'REJECTED'

                UNION ALL

                SELECT r.created_at,'Devolución','EGRESO',
                       'Dev #'||r.id,
                       u.full_name,
                       'Venta #'||r.sale_id||' · '||r.refund_method||' · '||r.reason,
                       r.total_refund,'REGISTRADA',-1
                FROM sale_returns r
                JOIN users u ON u.id=r.created_by

                UNION ALL

                SELECT c.opened_at,'Apertura de caja','CONTROL',
                       'Caja #'||c.id,
                       u.full_name,
                       'Fondo inicial de caja',
                       c.opening_amount,c.status,0
                FROM cash_sessions c
                JOIN users u ON u.id=c.user_id

                UNION ALL

                SELECT c.closed_at,'Corte de caja','CONTROL',
                       'Caja #'||c.id,
                       u.full_name,
                       'Esperado $'||printf('%.2f',COALESCE(c.expected_amount,0))||
                       ' · Contado $'||printf('%.2f',COALESCE(c.counted_amount,0))||
                       ' · Diferencia $'||printf('%.2f',COALESCE(c.difference,0)),
                       COALESCE(c.counted_amount,0),'CERRADA',0
                FROM cash_sessions c
                JOIN users u ON u.id=c.user_id
                WHERE c.closed_at IS NOT NULL
            )
            WHERE date(fecha) BETWEEN date(?) AND date(?)
            ORDER BY datetime(fecha) DESC
            LIMIT 10000
            """
            return self.db.all(sql,(d1.strftime("%Y-%m-%d"),d2.strftime("%Y-%m-%d")))

        def load_finances():
            nonlocal current_rows
            d1,d2=parse_dates()
            if not d1:
                return

            rows=fetch_movements(d1,d2)
            selected=type_var.get()
            if selected!="Todos":
                rows=[r for r in rows if r["tipo"]==selected]

            current_rows=[dict(r) for r in rows]

            for item in tree.get_children():
                tree.delete(item)

            income=0.0
            expenses_total=0.0
            pending=0.0

            for r in rows:
                amount=float(r["monto"] or 0)
                effect=int(r["efecto"] or 0)
                if effect>0:
                    income+=amount
                elif effect<0:
                    expenses_total+=amount
                elif r["direccion"]=="PENDIENTE":
                    pending+=amount

                tree.insert(
                    "","end",
                    values=(
                        r["fecha"],r["tipo"],r["direccion"],r["referencia"],
                        r["usuario"],r["detalle"],f"${amount:.2f}",r["estado"]
                    )
                )

            income_var.set(f"${income:.2f}")
            expense_var.set(f"${expenses_total:.2f}")
            net_var.set(f"${income-expenses_total:.2f}")
            pending_var.set(f"${pending:.2f}")

            # Estado de Resultados:
            # Compras NO son gasto operativo. El costo se reconoce al vender
            # usando cost_total, que ya proviene del consumo FIFO/PEPS.
            gross_sales_row=self.db.one(
                """SELECT COALESCE(SUM(total),0) total
                   FROM sales
                   WHERE status='COMPLETED'
                     AND date(created_at) BETWEEN date(?) AND date(?)""",
                (d1.strftime("%Y-%m-%d"),d2.strftime("%Y-%m-%d"))
            )
            returns_row=self.db.one(
                """SELECT COALESCE(SUM(total_refund),0) total
                   FROM sale_returns
                   WHERE date(created_at) BETWEEN date(?) AND date(?)""",
                (d1.strftime("%Y-%m-%d"),d2.strftime("%Y-%m-%d"))
            )
            cogs_row=self.db.one(
                """SELECT COALESCE(SUM(cost_total),0) total
                   FROM sales
                   WHERE status='COMPLETED'
                     AND date(created_at) BETWEEN date(?) AND date(?)""",
                (d1.strftime("%Y-%m-%d"),d2.strftime("%Y-%m-%d"))
            )
            op_exp_row=self.db.one(
                """SELECT COALESCE(SUM(amount),0) total
                   FROM expenses
                   WHERE status='APPROVED'
                     AND date(requested_at) BETWEEN date(?) AND date(?)""",
                (d1.strftime("%Y-%m-%d"),d2.strftime("%Y-%m-%d"))
            )

            gross_sales=float(gross_sales_row["total"] or 0)
            returned=float(returns_row["total"] or 0)
            cogs=float(cogs_row["total"] or 0)
            operating_expenses=float(op_exp_row["total"] or 0)

            # Ajuste proporcional del costo por devoluciones.
            # sale_returns guarda el valor reembolsado; al regresar mercancía
            # al inventario se revierte también su costo. Si existe información
            # detallada por item, usarla para estimar el costo devuelto.
            returned_cost=0.0
            try:
                rc=self.db.one(
                    """SELECT COALESCE(SUM(ri.cost_amount),0) total
                       FROM sale_return_items ri
                       JOIN sale_returns r ON r.id=ri.return_id
                       JOIN sale_items si ON si.id=ri.sale_item_id
                       WHERE date(r.created_at) BETWEEN date(?) AND date(?)""",
                    (d1.strftime("%Y-%m-%d"),d2.strftime("%Y-%m-%d"))
                )
                returned_cost=float(rc["total"] or 0)
            except Exception:
                returned_cost=0.0

            net_sales=gross_sales-returned
            net_cogs=max(0.0,cogs-returned_cost)
            gross_profit=net_sales-net_cogs
            operating_profit=gross_profit-operating_expenses

            gross_margin=(gross_profit/net_sales*100) if net_sales else 0.0
            net_margin=(operating_profit/net_sales*100) if net_sales else 0.0

            gross_sales_var.set(f"${gross_sales:.2f}")
            returns_var.set(f"${returned:.2f}")
            net_sales_var.set(f"${net_sales:.2f}")
            cogs_var.set(f"${net_cogs:.2f}")
            gross_profit_var.set(f"${gross_profit:.2f}")
            operating_expenses_var.set(f"${operating_expenses:.2f}")
            operating_profit_var.set(f"${operating_profit:.2f}")
            gross_margin_var.set(f"{gross_margin:.2f}%")
            net_margin_var.set(f"{net_margin:.2f}%")

        def quick_range(kind):
            d=datetime.now().date()
            if kind=="HOY":
                a=b=d
            elif kind=="AYER":
                a=b=d.replace() - __import__("datetime").timedelta(days=1)
            elif kind=="SEMANA":
                a=d-__import__("datetime").timedelta(days=d.weekday())
                b=d
            else:
                a=d.replace(day=1)
                b=d
            from_var.set(a.strftime("%Y-%m-%d"))
            to_var.set(b.strftime("%Y-%m-%d"))
            load_finances()

        # Avoid datetime module ambiguity: buttons use simple helpers below.
        import datetime as _dt_fin
        def set_quick(kind):
            d=_dt_fin.date.today()
            if kind=="HOY":
                a=b=d
            elif kind=="AYER":
                a=b=d-_dt_fin.timedelta(days=1)
            elif kind=="SEMANA":
                a=d-_dt_fin.timedelta(days=d.weekday()); b=d
            else:
                a=d.replace(day=1); b=d
            from_var.set(a.strftime("%Y-%m-%d"))
            to_var.set(b.strftime("%Y-%m-%d"))
            load_finances()

        for label,key in [
            ("Hoy","HOY"),("Ayer","AYER"),
            ("Esta semana","SEMANA"),("Este mes","MES")
        ]:
            tk.Button(
                top,text=label,command=lambda k=key:set_quick(k),
                bg="#E5E7EB",fg=COLORS["dark"],
                relief="flat",padx=8,pady=4
            ).pack(side="left",padx=2)

        tk.Button(
            top,text="APLICAR",command=load_finances,
            bg=COLORS["green"],fg="white",
            relief="flat",padx=12,pady=4
        ).pack(side="right")

        def print_finances():
            d1,d2=parse_dates()
            if not d1:
                return

            if not current_rows:
                self.show_app_modal(
                    "Sin movimientos",
                    "No hay movimientos financieros visibles para imprimir.",
                    modal_type="warning",primary_text="ACEPTAR"
                )
                return

            rows=[
                (
                    r["fecha"],r["tipo"],r["direccion"],r["referencia"],
                    r["usuario"],r["detalle"],
                    f"${float(r['monto'] or 0):.2f}",r["estado"]
                )
                for r in current_rows
            ]

            self.open_printable_report(
                "Informe Financiero Consolidado",
                ["Fecha","Tipo","Movimiento","Referencia","Usuario","Detalle","Monto","Estado"],
                rows,
                {
                    "Período":f"{from_var.get()} al {to_var.get()}",
                    "Filtro":type_var.get(),
                    "Ingresos":income_var.get(),
                    "Egresos":expense_var.get(),
                    "Flujo neto":net_var.get(),
                    "Gastos pendientes":pending_var.get(),
                    "Ventas netas":net_sales_var.get(),
                    "Utilidad bruta":gross_profit_var.get(),
                    "Utilidad neta operativa":operating_profit_var.get(),
                    "Margen neto":net_margin_var.get(),
                    "Registros":str(len(rows)),
                }
            )

        def print_income_statement_detailed():
            d1,d2=parse_dates()
            if not d1:
                return

            # Ventas del período
            sales_rows=self.db.all(
                """SELECT s.id,s.created_at,u.full_name,s.payment_method,
                          s.total,s.cost_total
                   FROM sales s
                   JOIN users u ON u.id=s.created_by
                   WHERE s.status='COMPLETED'
                     AND date(s.created_at) BETWEEN date(?) AND date(?)
                   ORDER BY datetime(s.created_at)""",
                (d1.strftime("%Y-%m-%d"),d2.strftime("%Y-%m-%d"))
            )

            # Devoluciones del período
            return_rows=self.db.all(
                """SELECT r.id,r.created_at,r.sale_id,u.full_name,
                          r.refund_method,r.reason,r.total_refund
                   FROM sale_returns r
                   JOIN users u ON u.id=r.created_by
                   WHERE date(r.created_at) BETWEEN date(?) AND date(?)
                   ORDER BY datetime(r.created_at)""",
                (d1.strftime("%Y-%m-%d"),d2.strftime("%Y-%m-%d"))
            )

            # Gastos operativos aprobados
            expense_rows=self.db.all(
                """SELECT e.id,e.requested_at,u.full_name,
                          e.description,e.amount,e.note
                   FROM expenses e
                   JOIN users u ON u.id=e.requested_by
                   WHERE e.status='APPROVED'
                     AND date(e.requested_at) BETWEEN date(?) AND date(?)
                   ORDER BY datetime(e.requested_at)""",
                (d1.strftime("%Y-%m-%d"),d2.strftime("%Y-%m-%d"))
            )

            # Ingresos de caja no provenientes de ventas (informativos)
            cash_inflow_rows=self.db.all(
                """SELECT ci.id,ci.created_at,u.full_name,
                          ci.concept,ci.amount,ci.note
                   FROM cash_inflows ci
                   JOIN users u ON u.id=ci.created_by
                   WHERE date(ci.created_at) BETWEEN date(?) AND date(?)
                   ORDER BY datetime(ci.created_at)""",
                (d1.strftime("%Y-%m-%d"),d2.strftime("%Y-%m-%d"))
            )

            # Compras (informativas: no se descuentan directamente de la utilidad)
            purchase_rows=self.db.all(
                """SELECT p.id,p.created_at,u.full_name,
                          COALESCE(p.supplier,'') supplier,
                          COALESCE(p.document_no,'') document_no,
                          p.total
                   FROM purchases p
                   JOIN users u ON u.id=p.created_by
                   WHERE date(p.created_at) BETWEEN date(?) AND date(?)
                   ORDER BY datetime(p.created_at)""",
                (d1.strftime("%Y-%m-%d"),d2.strftime("%Y-%m-%d"))
            )

            detail_rows=[]

            # Encabezado contable
            detail_rows.extend([
                ("RESUMEN","","","",""),
                ("Ventas brutas","","","",gross_sales_var.get()),
                ("(-) Devoluciones","","","",returns_var.get()),
                ("VENTAS NETAS","","","",net_sales_var.get()),
                ("(-) Costo FIFO/PEPS de lo vendido","","","",cogs_var.get()),
                ("UTILIDAD BRUTA","","","",gross_profit_var.get()),
                ("(-) Gastos operativos aprobados","","","",operating_expenses_var.get()),
                ("UTILIDAD NETA OPERATIVA","","","",operating_profit_var.get()),
                ("Margen bruto","","","",gross_margin_var.get()),
                ("Margen neto operativo","","","",net_margin_var.get()),
            ])

            # Detalle de ventas
            detail_rows.append(("","","","",""))
            detail_rows.append(("DETALLE DE VENTAS","","","",""))
            for r in sales_rows:
                detail_rows.append((
                    r["created_at"],
                    f"Venta #{r['id']}",
                    r["full_name"],
                    f"{r['payment_method']} · Costo FIFO ${float(r['cost_total'] or 0):.2f}",
                    f"${float(r['total'] or 0):.2f}"
                ))

            # Detalle de devoluciones
            detail_rows.append(("","","","",""))
            detail_rows.append(("DETALLE DE DEVOLUCIONES","","","",""))
            for r in return_rows:
                detail_rows.append((
                    r["created_at"],
                    f"Devolución #{r['id']}",
                    r["full_name"],
                    f"Venta #{r['sale_id']} · {r['refund_method']} · {r['reason']}",
                    f"-${float(r['total_refund'] or 0):.2f}"
                ))

            # Gastos aprobados
            detail_rows.append(("","","","",""))
            detail_rows.append(("GASTOS OPERATIVOS APROBADOS","","","",""))
            for r in expense_rows:
                detail_rows.append((
                    r["requested_at"],
                    f"Gasto #{r['id']}",
                    r["full_name"],
                    f"{r['description']} · {r['note'] or ''}".strip(" ·"),
                    f"-${float(r['amount'] or 0):.2f}"
                ))

            # Ingresos de caja informativos
            detail_rows.append(("","","","",""))
            detail_rows.append(("INGRESOS DE CAJA NO PROVENIENTES DE VENTAS","","","",""))
            for r in cash_inflow_rows:
                detail_rows.append((
                    r["created_at"],
                    f"Ingreso #{r['id']}",
                    r["full_name"],
                    f"{r['concept']} · {r['note'] or ''}".strip(" ·"),
                    f"${float(r['amount'] or 0):.2f}"
                ))

            # Compras informativas
            detail_rows.append(("","","","",""))
            detail_rows.append(("COMPRAS DEL PERÍODO (INFORMATIVAS)","","","",""))
            for r in purchase_rows:
                detail_rows.append((
                    r["created_at"],
                    f"Compra #{r['id']}",
                    r["full_name"],
                    f"{r['supplier']} · Doc {r['document_no']}".strip(" ·"),
                    f"${float(r['total'] or 0):.2f}"
                ))

            self.open_printable_report(
                "Estado de Resultados Detallado",
                ["Fecha / Concepto","Referencia","Usuario","Detalle","Valor"],
                detail_rows,
                {
                    "Período":f"{from_var.get()} al {to_var.get()}",
                    "Método de costo":"FIFO / PEPS",
                    "Ventas brutas":gross_sales_var.get(),
                    "Devoluciones":returns_var.get(),
                    "Ventas netas":net_sales_var.get(),
                    "Costo vendido FIFO":cogs_var.get(),
                    "Utilidad bruta":gross_profit_var.get(),
                    "Gastos operativos":operating_expenses_var.get(),
                    "Utilidad neta operativa":operating_profit_var.get(),
                    "Margen bruto":gross_margin_var.get(),
                    "Margen neto operativo":net_margin_var.get(),
                    "Ingresos de caja no venta":f"${sum(float(r['amount'] or 0) for r in cash_inflow_rows):.2f}",
                    "Compras del período":f"${sum(float(r['total'] or 0) for r in purchase_rows):.2f}",
                    "Nota":"Los ingresos de caja no provenientes de ventas afectan el efectivo y el flujo financiero, pero no se contabilizan como ventas ni utilidad operativa. Las compras se reconocen como costo cuando la mercadería se vende.",
                }
            )

        tk.Button(
            print_bar,text="IMPRIMIR INFORME FINANCIERO",
            command=print_finances,
            bg=COLORS["blue"],fg="white",
            font=("Segoe UI",9,"bold"),relief="flat",
            padx=16,pady=8
        ).pack(side="left")

        tk.Button(
            print_bar,text="IMPRIMIR ESTADO DE RESULTADOS DETALLADO",
            command=print_income_statement_detailed,
            bg=COLORS["green"],fg="white",
            font=("Segoe UI",9,"bold"),relief="flat",
            padx=16,pady=8
        ).pack(side="left",padx=8)

        tk.Label(
            print_bar,
            text="Los botones permanecen visibles aunque la tabla tenga muchos movimientos.",
            bg=COLORS["light"],fg=COLORS["gray"],font=("Segoe UI",8)
        ).pack(side="right",padx=8)

        from_entry.bind("<Return>",lambda e:load_finances())
        to_entry.bind("<Return>",lambda e:load_finances())
        type_combo.bind("<<ComboboxSelected>>",lambda e:load_finances())
        load_finances()

    def build_reports(self):
        import datetime as _dt

        for w in self.tab_reports.winfo_children():
            w.destroy()

        tk.Label(
            self.tab_reports,text="Reportes y auditoría",
            font=("Segoe UI",18,"bold"),bg=COLORS["light"]
        ).pack(anchor="w",pady=8)

        nb=ttk.Notebook(self.tab_reports)
        nb.pack(fill="both",expand=True)

        tab_sales=tk.Frame(nb,bg=COLORS["light"])
        tab_cash=tk.Frame(nb,bg=COLORS["light"])
        tab_inv=tk.Frame(nb,bg=COLORS["light"])
        nb.add(tab_sales,text="Ventas")
        nb.add(tab_cash,text="Cortes de caja")
        nb.add(tab_inv,text="Historial inventario")

        # ---------------------------------------------------------
        # Utilidades comunes de filtros
        # ---------------------------------------------------------
        def fmt_date(d):
            return d.strftime("%Y-%m-%d")

        def parse_range(vfrom,vto):
            try:
                d1=_dt.datetime.strptime(vfrom.get().strip(),"%Y-%m-%d").date()
                d2=_dt.datetime.strptime(vto.get().strip(),"%Y-%m-%d").date()
                if d2<d1:
                    raise ValueError
                return d1,d2
            except Exception:
                messagebox.showwarning(
                    "Reportes",
                    "Rango de fechas inválido.\nUse el formato AAAA-MM-DD."
                )
                return None,None

        def make_filter_bar(parent,apply_callback,extra_builder=None):
            frame=tk.Frame(parent,bg="white",bd=1,relief="solid")
            frame.pack(fill="x",pady=(0,7))

            top=tk.Frame(frame,bg="white",padx=10,pady=7)
            top.pack(fill="x")

            today=_dt.date.today()
            vfrom=tk.StringVar(value=fmt_date(today))
            vto=tk.StringVar(value=fmt_date(today))

            tk.Label(top,text="Desde",bg="white",font=("Segoe UI",9,"bold")).pack(side="left")
            tk.Entry(top,textvariable=vfrom,width=11).pack(side="left",padx=(5,10))
            tk.Label(top,text="Hasta",bg="white",font=("Segoe UI",9,"bold")).pack(side="left")
            tk.Entry(top,textvariable=vto,width=11).pack(side="left",padx=(5,12))

            def set_quick(kind):
                d=_dt.date.today()
                if kind=="HOY":
                    a=b=d
                elif kind=="AYER":
                    a=b=d-_dt.timedelta(days=1)
                elif kind=="SEMANA":
                    a=d-_dt.timedelta(days=d.weekday()); b=d
                else:
                    a=d.replace(day=1); b=d
                vfrom.set(fmt_date(a));vto.set(fmt_date(b))
                apply_callback()

            for label,key in [
                ("Hoy","HOY"),("Ayer","AYER"),
                ("Esta semana","SEMANA"),("Este mes","MES")
            ]:
                tk.Button(
                    top,text=label,command=lambda k=key:set_quick(k),
                    bg="#E5E7EB",fg=COLORS["dark"],relief="flat",
                    padx=8,pady=4
                ).pack(side="left",padx=2)

            tk.Button(
                top,text="APLICAR",command=apply_callback,
                bg=COLORS["green"],fg="white",relief="flat",
                padx=13,pady=4
            ).pack(side="right")

            if extra_builder:
                extra=tk.Frame(frame,bg="white",padx=10,pady=(0,7))
                extra.pack(fill="x")
                extra_builder(extra)

            tk.Label(
                frame,text="Fechas: AAAA-MM-DD · Por defecto se muestra solamente HOY",
                bg="white",fg=COLORS["gray"],font=("Segoe UI",8)
            ).pack(anchor="e",padx=10,pady=(0,5))

            return vfrom,vto

        # =========================================================
        # VENTAS
        # =========================================================
        sales_filter=tk.Frame(tab_sales,bg=COLORS["light"])
        sales_filter.pack(fill="x")

        sales_summary=tk.StringVar()
        tk.Label(
            tab_sales,textvariable=sales_summary,
            bg=COLORS["light"],font=("Segoe UI",10,"bold")
        ).pack(anchor="w",pady=(0,4))

        cols=("id","date","cashier","method","addons","sales","returned","net","cost","status")
        tree=ttk.Treeview(tab_sales,columns=cols,show="headings")
        for c,h,w in [
            ("id","Venta",55),("date","Fecha",135),("cashier","Empleado",135),
            ("method","Pago",75),("addons","Adicionales",210),
            ("sales","Venta",75),("returned","Devuelto",75),("net","Neto",75),
            ("cost","Costo",75),("status","Estado",85)
        ]:
            tree.heading(c,text=h);tree.column(c,width=w)

        def load_sales():
            if not hasattr(load_sales,"vfrom"):return
            d1,d2=parse_range(load_sales.vfrom,load_sales.vto)
            if not d1:return
            for x in tree.get_children():tree.delete(x)
            rows=self.db.all(
                """SELECT s.*,u.full_name
                   FROM sales s JOIN users u ON u.id=s.created_by
                   WHERE date(s.created_at) BETWEEN date(?) AND date(?)
                   ORDER BY s.id DESC""",
                (fmt_date(d1),fmt_date(d2))
            )
            valid=[r for r in rows if r["status"]=="COMPLETED"]
            ventas=sum(float(r["total"] or 0) for r in valid)
            costo=sum(float(r["cost_total"] or 0) for r in valid)
            ret_row=self.db.one(
                """SELECT COALESCE(SUM(total_refund),0) r
                   FROM sale_returns
                   WHERE date(created_at) BETWEEN date(?) AND date(?)""",
                (fmt_date(d1),fmt_date(d2))
            )
            devoluciones=float(ret_row["r"] or 0)
            sales_summary.set(
                f"{len(rows)} registro(s) · Venta bruta: ${ventas:.2f} · "
                f"Devoluciones: ${devoluciones:.2f} · Venta neta: ${ventas-devoluciones:.2f}"
            )
            for r in rows:
                addon_rows=self.db.all(
                    """SELECT sia.addon_name,COUNT(*) AS veces
                       FROM sale_item_addons sia
                       JOIN sale_items si ON si.id=sia.sale_item_id
                       WHERE si.sale_id=?
                       GROUP BY sia.addon_name
                       ORDER BY sia.addon_name""",
                    (r["id"],)
                )
                addons_text=", ".join(
                    f"{a['addon_name']} x{a['veces']}" if int(a["veces"])>1 else a["addon_name"]
                    for a in addon_rows
                ) or "-"

                returned=float(self.db.one(
                    "SELECT COALESCE(SUM(total_refund),0) r FROM sale_returns WHERE sale_id=?",
                    (r["id"],)
                )["r"])
                gross=float(r["total"] or 0)
                tree.insert("","end",values=(
                    r["id"],r["created_at"],r["full_name"],r["payment_method"],
                    addons_text,
                    f"${gross:.2f}",f"${returned:.2f}",f"${gross-returned:.2f}",
                    f"${float(r['cost_total']):.2f}",r["status"]
                ))

        sf,st=make_filter_bar(sales_filter,load_sales)
        load_sales.vfrom=sf;load_sales.vto=st
        tree.pack(fill="both",expand=True,pady=5)

        def void_sale():
            sel=tree.selection()
            if not sel:
                messagebox.showwarning("Anulación","Seleccione una venta.");return
            sale_id=int(tree.item(sel[0],"values")[0])
            sale=self.db.one("SELECT * FROM sales WHERE id=?",(sale_id,))
            if not sale or sale["status"]!="COMPLETED":
                messagebox.showinfo("Anulación","La venta ya está anulada o no está disponible.");return
            reason=simpledialog.askstring("Anular venta","Motivo de la anulación:")
            if not reason:return
            if not messagebox.askyesno(
                "Confirmar",
                f"¿Anular la venta #{sale_id} y devolver sus productos al inventario?"
            ):
                return
            try:
                cur=self.db.conn.cursor()
                items=self.db.all("SELECT * FROM sale_items WHERE sale_id=?",(sale_id,))
                for item in items:
                    # Servicios no restauran inventario.
                    prod=self.db.one("SELECT product_type FROM products WHERE id=?",(item["product_id"],))
                    if prod and prod["product_type"]=="SERVICE":
                        continue
                    allocs=self.db.all(
                        "SELECT * FROM sale_cost_allocations WHERE sale_item_id=?",(item["id"],)
                    )
                    if allocs:
                        for a in allocs:
                            cur.execute(
                                "UPDATE inventory_lots SET qty_remaining=qty_remaining+? WHERE id=?",
                                (a["qty"],a["lot_id"])
                            )
                    elif item["qty"]:
                        avg=float(item["cost_total"])/float(item["qty"])
                        cur.execute(
                            """INSERT INTO inventory_lots(
                               product_id,purchase_item_id,qty_received,qty_remaining,unit_cost,created_at
                               ) VALUES(?,NULL,?,?,?,?)""",
                            (item["product_id"],item["qty"],item["qty"],avg,now_iso())
                        )
                    if item["qty"]:
                        self.db.log_inventory(
                            item["product_id"],"ANULACION_VENTA",item["qty"],
                            float(item["cost_total"])/float(item["qty"]) if item["qty"] else None,
                            "SALE",sale_id,reason,self.user["id"]
                        )
                cur.execute(
                    """UPDATE sales SET status='VOIDED',voided_by=?,voided_at=?,void_reason=?
                       WHERE id=?""",
                    (self.user["id"],now_iso(),reason,sale_id)
                )
                self.db.conn.commit()
                messagebox.showinfo("Anulación","Venta anulada e inventario restaurado.")
                load_sales();self.build_products();self.build_dashboard()
            except Exception as e:
                self.db.conn.rollback()
                messagebox.showerror("Anulación",f"No se pudo anular.\n{e}")

        def open_selected_sale(event=None):
            sel=tree.selection()
            if sel:
                self.open_sale_detail_report(int(tree.item(sel[0],"values")[0]))

        def print_sales_report():
            d1,d2=parse_range(sf,st)
            if not d1:return
            data=[list(tree.item(x,"values")) for x in tree.get_children()]
            valid=[]
            for row in data:
                if row[9]=="COMPLETED":
                    valid.append(row)
            self.open_printable_report(
                f"Reporte de ventas · {fmt_date(d1)} a {fmt_date(d2)}",
                ["Venta","Fecha","Empleado","Pago","Adicionales","Venta","Devuelto","Neto","Costo","Estado"],
                data,
                {"Período":f"{fmt_date(d1)} a {fmt_date(d2)}",
                 "Registros":str(len(data))}
            )

        sales_actions=tk.Frame(tab_sales,bg=COLORS["light"])
        sales_actions.pack(fill="x",pady=(2,7))
        tk.Label(
            sales_actions,text="Para devoluciones o anulaciones use el menú Devoluciones.",
            bg=COLORS["light"],fg=COLORS["gray"],font=("Segoe UI",9,"bold")
        ).pack(side="left")
        tk.Button(
            sales_actions,text="Vista imprimible",command=print_sales_report,
            bg=COLORS["blue"],fg="white",relief="flat",padx=15,pady=7
        ).pack(side="left",padx=8)
        tree.bind("<Double-1>",open_selected_sale)
        tree.bind("<Return>",open_selected_sale)
        load_sales()

        # =========================================================
        # CORTES DE CAJA
        # =========================================================
        cash_filter=tk.Frame(tab_cash,bg=COLORS["light"])
        cash_filter.pack(fill="x")

        cash_summary=tk.StringVar()
        tk.Label(
            tab_cash,textvariable=cash_summary,
            bg=COLORS["light"],font=("Segoe UI",10,"bold")
        ).pack(anchor="w",pady=(0,4))

        ccols=("id","user","opened","closed","opening","expected","counted","difference")
        ctree=ttk.Treeview(tab_cash,columns=ccols,show="headings")
        for c,h,w in [
            ("id","Corte",65),("user","Empleado",180),("opened","Apertura",145),
            ("closed","Cierre",145),("opening","Fondo",90),("expected","Esperado",95),
            ("counted","Contado",95),("difference","Diferencia",95)
        ]:
            ctree.heading(c,text=h);ctree.column(c,width=w)

        def load_cash():
            if not hasattr(load_cash,"vfrom"):return
            d1,d2=parse_range(load_cash.vfrom,load_cash.vto)
            if not d1:return
            for x in ctree.get_children():ctree.delete(x)
            rows=self.db.all(
                """SELECT c.*,u.full_name
                   FROM cash_sessions c JOIN users u ON u.id=c.user_id
                   WHERE c.status='CLOSED'
                     AND date(c.opened_at) BETWEEN date(?) AND date(?)
                   ORDER BY c.id DESC""",
                (fmt_date(d1),fmt_date(d2))
            )
            diff=sum(float(r["difference"] or 0) for r in rows)
            cash_summary.set(f"{len(rows)} corte(s) · Diferencia acumulada: ${diff:.2f}")
            for r in rows:
                ctree.insert("","end",values=(
                    r["id"],r["full_name"],r["opened_at"],r["closed_at"],
                    f"${float(r['opening_amount'] or 0):.2f}",
                    f"${float(r['expected_amount'] or 0):.2f}",
                    f"${float(r['counted_amount'] or 0):.2f}",
                    f"${float(r['difference'] or 0):.2f}"
                ))

        cf,ct=make_filter_bar(cash_filter,load_cash)
        load_cash.vfrom=cf;load_cash.vto=ct
        ctree.pack(fill="both",expand=True,pady=5)

        def show_cut_detail():
            sel=ctree.selection()
            if not sel:return
            cid=int(ctree.item(sel[0],"values")[0])
            r=self.db.one(
                """SELECT c.*,u.full_name FROM cash_sessions c
                   JOIN users u ON u.id=c.user_id WHERE c.id=?""",(cid,)
            )
            sales_cash=float(self.db.one(
                """SELECT COALESCE(SUM(total),0) s FROM sales
                   WHERE cash_session_id=? AND payment_method='Efectivo'
                     AND status='COMPLETED'""",(cid,)
            )["s"])
            transfers=float(self.db.one(
                """SELECT COALESCE(SUM(total),0) s FROM sales
                   WHERE cash_session_id=? AND payment_method='Transferencia'
                     AND status='COMPLETED'""",(cid,)
            )["s"])
            expenses=float(self.db.one(
                """SELECT COALESCE(SUM(amount),0) s FROM expenses
                   WHERE cash_session_id=? AND status='APPROVED'""",(cid,)
            )["s"])
            breakdown=""
            try:
                data=json.loads(r["denominations_json"] or "{}")
                breakdown="\n".join(
                    [f"${float(k):.2f} × {v}" for k,v in data.items() if int(v)>0]
                )
            except Exception:
                pass
            messagebox.showinfo(
                "Detalle del corte",
                f"Empleado: {r['full_name']}\nApertura: {r['opened_at']}\n"
                f"Cierre: {r['closed_at']}\n\n"
                f"Fondo inicial: ${float(r['opening_amount'] or 0):.2f}\n"
                f"Ventas efectivo: ${sales_cash:.2f}\nTransferencias: ${transfers:.2f}\n"
                f"Gastos aprobados: ${expenses:.2f}\n"
                f"Esperado: ${float(r['expected_amount'] or 0):.2f}\n"
                f"Contado: ${float(r['counted_amount'] or 0):.2f}\n"
                f"Diferencia: ${float(r['difference'] or 0):.2f}\n\n"
                f"Denominaciones:\n{breakdown or 'Sin desglose'}"
            )

        def open_selected_cut(event=None):
            sel=ctree.selection()
            if sel:
                self.open_cash_cut_report(int(ctree.item(sel[0],"values")[0]))

        def print_cash_report():
            d1,d2=parse_range(cf,ct)
            if not d1:return
            data=[list(ctree.item(x,"values")) for x in ctree.get_children()]
            self.open_printable_report(
                f"Reporte de cortes de caja · {fmt_date(d1)} a {fmt_date(d2)}",
                ["Corte","Empleado","Apertura","Cierre","Fondo","Esperado","Contado","Diferencia"],
                data,
                {"Período":f"{fmt_date(d1)} a {fmt_date(d2)}","Cortes":str(len(data))}
            )

        cash_actions=tk.Frame(tab_cash,bg=COLORS["light"])
        cash_actions.pack(fill="x",pady=(2,7))
        tk.Button(
            cash_actions,text="Ver detalle del corte",command=show_cut_detail,
            bg=COLORS["blue"],fg="white",relief="flat",padx=15,pady=7
        ).pack(side="left")
        tk.Button(
            cash_actions,text="Vista imprimible",command=print_cash_report,
            bg=COLORS["green"],fg="white",relief="flat",padx=15,pady=7
        ).pack(side="left",padx=8)
        ctree.bind("<Double-1>",open_selected_cut)
        ctree.bind("<Return>",open_selected_cut)
        load_cash()

        # =========================================================
        # HISTORIAL DE INVENTARIO
        # =========================================================
        # Esta sección se construye de forma independiente y tolerante
        # para que un problema en un filtro no deje la pestaña en blanco.

        inv_top=tk.Frame(tab_inv,bg=COLORS["light"])
        inv_top.pack(fill="x",pady=(0,6))

        today=_dt.date.today()
        inv_from=tk.StringVar(value=fmt_date(today))
        inv_to=tk.StringVar(value=fmt_date(today))
        product_var=tk.StringVar(value="Todos")
        movement_var=tk.StringVar(value="Todos")

        # Primera fila: fechas y accesos rápidos.
        date_row=tk.Frame(inv_top,bg="white",bd=1,relief="solid",padx=10,pady=7)
        date_row.pack(fill="x")

        tk.Label(date_row,text="Desde",bg="white",font=("Segoe UI",9,"bold")).pack(side="left")
        tk.Entry(date_row,textvariable=inv_from,width=11).pack(side="left",padx=(5,10))
        tk.Label(date_row,text="Hasta",bg="white",font=("Segoe UI",9,"bold")).pack(side="left")
        tk.Entry(date_row,textvariable=inv_to,width=11).pack(side="left",padx=(5,12))

        # Segunda fila: producto y tipo de movimiento.
        filter_row=tk.Frame(inv_top,bg="white",bd=1,relief="solid",padx=10,pady=7)
        filter_row.pack(fill="x",pady=(3,0))

        tk.Label(filter_row,text="Producto",bg="white",
                 font=("Segoe UI",9,"bold")).pack(side="left")

        # No dependemos de product_type para construir este filtro;
        # así también funciona con bases creadas por versiones anteriores.
        all_products=self.db.all(
            "SELECT id,sku,name FROM products WHERE active=1 ORDER BY name"
        )
        product_options=["Todos"]+[
            f"{p['id']} | {p['sku']} | {p['name']}" for p in all_products
        ]
        product_combo=ttk.Combobox(
            filter_row,textvariable=product_var,state="readonly",
            values=product_options,width=34
        )
        product_combo.pack(side="left",padx=(5,14))
        product_combo.set("Todos")

        tk.Label(filter_row,text="Movimiento",bg="white",
                 font=("Segoe UI",9,"bold")).pack(side="left")

        try:
            real_types=self.db.all(
                """SELECT DISTINCT movement_type
                   FROM inventory_movements
                   WHERE movement_type IS NOT NULL AND movement_type<>''
                   ORDER BY movement_type"""
            )
            movement_options=["Todos"]+[r["movement_type"] for r in real_types]
        except Exception:
            movement_options=["Todos"]

        movement_combo=ttk.Combobox(
            filter_row,textvariable=movement_var,state="readonly",
            values=movement_options,width=22
        )
        movement_combo.pack(side="left",padx=(5,10))
        movement_combo.set("Todos")

        inv_summary=tk.StringVar(value="Cargando historial...")
        tk.Label(
            tab_inv,textvariable=inv_summary,
            bg=COLORS["light"],font=("Segoe UI",10,"bold")
        ).pack(anchor="w",pady=(2,5))

        table_box=tk.Frame(tab_inv,bg=COLORS["light"])
        table_box.pack(fill="both",expand=True)

        icols=("date","product","type","qty","cost","ref","user","note")
        itree=ttk.Treeview(table_box,columns=icols,show="headings")
        for c,h,w in [
            ("date","Fecha / hora",145),
            ("product","Producto",190),
            ("type","Movimiento",140),
            ("qty","Cantidad",85),
            ("cost","Costo unit.",90),
            ("ref","Referencia",105),
            ("user","Usuario",125),
            ("note","Nota / motivo",230),
        ]:
            itree.heading(c,text=h)
            itree.column(c,width=w)

        yscroll=ttk.Scrollbar(table_box,orient="vertical",command=itree.yview)
        xscroll=ttk.Scrollbar(table_box,orient="horizontal",command=itree.xview)
        itree.configure(yscrollcommand=yscroll.set,xscrollcommand=xscroll.set)

        yscroll.pack(side="right",fill="y")
        xscroll.pack(side="bottom",fill="x")
        itree.pack(side="left",fill="both",expand=True)

        def get_inv_dates():
            try:
                d1=_dt.datetime.strptime(inv_from.get().strip(),"%Y-%m-%d").date()
                d2=_dt.datetime.strptime(inv_to.get().strip(),"%Y-%m-%d").date()
                if d2<d1:
                    raise ValueError
                return d1,d2
            except Exception:
                messagebox.showwarning(
                    "Historial de inventario",
                    "Revise las fechas. Use el formato AAAA-MM-DD."
                )
                return None,None

        def load_inventory_history(show_errors=True):
            d1,d2=get_inv_dates()
            if not d1:return

            try:
                where=["date(m.created_at) BETWEEN date(?) AND date(?)"]
                params=[fmt_date(d1),fmt_date(d2)]

                if product_var.get() and product_var.get()!="Todos":
                    pid=int(product_var.get().split("|",1)[0].strip())
                    where.append("m.product_id=?")
                    params.append(pid)

                if movement_var.get() and movement_var.get()!="Todos":
                    where.append("m.movement_type=?")
                    params.append(movement_var.get())

                sql=f"""SELECT m.*,p.name AS product_name,u.full_name
                        FROM inventory_movements m
                        JOIN products p ON p.id=m.product_id
                        LEFT JOIN users u ON u.id=m.created_by
                        WHERE {' AND '.join(where)}
                        ORDER BY m.id DESC
                        LIMIT 5000"""
                movements=self.db.all(sql,tuple(params))

                for item in itree.get_children():
                    itree.delete(item)

                total_in=0.0
                total_out=0.0

                for mov in movements:
                    # Compatibilidad defensiva con diferentes versiones de la tabla.
                    keys=mov.keys()
                    if "qty" in keys:
                        q=float(mov["qty"] or 0)
                    elif "qty_change" in keys:
                        q=float(mov["qty_change"] or 0)
                    else:
                        q=0.0

                    if q>0:
                        total_in+=q
                    elif q<0:
                        total_out+=abs(q)

                    ref_type=mov["reference_type"] if "reference_type" in keys else ""
                    ref_id=mov["reference_id"] if "reference_id" in keys else None
                    ref=f"{ref_type} #{ref_id}" if ref_id else (ref_type or "")

                    unit_cost=mov["unit_cost"] if "unit_cost" in keys else None
                    cost_text="" if unit_cost is None else f"${float(unit_cost):.4f}"

                    full_name=mov["full_name"] if "full_name" in keys else ""
                    note_text=mov["note"] if "note" in keys else ""

                    itree.insert(
                        "","end",
                        values=(
                            mov["created_at"],
                            mov["product_name"],
                            mov["movement_type"],
                            f"{q:+.2f}",
                            cost_text,
                            ref,
                            full_name or "",
                            note_text or ""
                        )
                    )

                # Valor actual del inventario a costo.
                # Se calcula con los lotes FIFO que todavía tienen existencia.
                if product_var.get() and product_var.get()!="Todos":
                    valuation_pid=int(product_var.get().split("|",1)[0].strip())
                    valuation=self.db.one(
                        """SELECT COALESCE(SUM(qty_remaining * unit_cost),0) AS inventory_value
                           FROM inventory_lots
                           WHERE product_id=? AND qty_remaining>0""",
                        (valuation_pid,)
                    )
                else:
                    valuation=self.db.one(
                        """SELECT COALESCE(SUM(qty_remaining * unit_cost),0) AS inventory_value
                           FROM inventory_lots
                           WHERE qty_remaining>0"""
                    )

                inventory_value=float(valuation["inventory_value"] or 0) if valuation else 0.0

                inv_summary.set(
                    f"{len(movements)} movimiento(s) · "
                    f"Entradas: {total_in:.2f} · Salidas: {total_out:.2f} · "
                    f"Valor inventario (costo): ${inventory_value:.2f}"
                )

            except Exception as e:
                inv_summary.set("No se pudo cargar el historial.")
                if show_errors:
                    messagebox.showerror(
                        "Historial de inventario",
                        f"No se pudo cargar el historial.\n\nDetalle: {e}"
                    )

        def set_inv_quick(kind):
            d=_dt.date.today()
            if kind=="HOY":
                a=b=d
            elif kind=="AYER":
                a=b=d-_dt.timedelta(days=1)
            elif kind=="SEMANA":
                a=d-_dt.timedelta(days=d.weekday())
                b=d
            else:
                a=d.replace(day=1)
                b=d

            inv_from.set(fmt_date(a))
            inv_to.set(fmt_date(b))
            load_inventory_history()

        for label,key in [
            ("Hoy","HOY"),
            ("Ayer","AYER"),
            ("Esta semana","SEMANA"),
            ("Este mes","MES"),
        ]:
            tk.Button(
                date_row,text=label,
                command=lambda k=key:set_inv_quick(k),
                bg="#E5E7EB",fg=COLORS["dark"],
                relief="flat",padx=8,pady=4
            ).pack(side="left",padx=2)

        tk.Button(
            date_row,text="APLICAR",
            command=load_inventory_history,
            bg=COLORS["green"],fg="white",
            relief="flat",padx=13,pady=4
        ).pack(side="right")

        def print_inventory_report():
            d1,d2=get_inv_dates()
            if not d1:return
            data=[list(itree.item(x,"values")) for x in itree.get_children()]
            extras={
                "Período":f"{fmt_date(d1)} a {fmt_date(d2)}",
                "Registros":str(len(data))
            }
            if product_var.get()!="Todos":
                extras["Producto"]=product_var.get().split("|")[-1].strip()
            if movement_var.get()!="Todos":
                extras["Movimiento"]=movement_var.get()

            self.open_printable_report(
                f"Historial de inventario · {fmt_date(d1)} a {fmt_date(d2)}",
                ["Fecha","Producto","Movimiento","Cantidad",
                 "Costo unit.","Referencia","Usuario","Nota"],
                data,extras
            )

        inv_actions=tk.Frame(tab_inv,bg=COLORS["light"])
        inv_actions.pack(fill="x",pady=(6,4))

        tk.Button(
            inv_actions,text="Actualizar / aplicar filtros",
            command=load_inventory_history,
            bg=COLORS["green"],fg="white",
            relief="flat",padx=15,pady=7
        ).pack(side="left")

        tk.Button(
            inv_actions,text="Vista imprimible",
            command=print_inventory_report,
            bg=COLORS["blue"],fg="white",
            relief="flat",padx=15,pady=7
        ).pack(side="left",padx=8)

        # Al cambiar los combos, refresca inmediatamente.
        product_combo.bind("<<ComboboxSelected>>",lambda e:load_inventory_history())
        movement_combo.bind("<<ComboboxSelected>>",lambda e:load_inventory_history())

        itree.bind("<Double-1>",lambda e:print_inventory_report())
        itree.bind("<Return>",lambda e:print_inventory_report())

        # La tabla ya está construida antes de consultar los datos.
        # Si no hay movimientos de hoy, se verá la tabla vacía con "0 movimientos",
        # en vez de una pestaña completamente en blanco.
        load_inventory_history(show_errors=True)


if __name__ == "__main__":
    app = TiendaMejiaApp()
    app.mainloop()
