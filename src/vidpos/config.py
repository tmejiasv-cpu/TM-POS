"""Configuración central de vidPOS.

Los valores por defecto viven aquí. El usuario puede sobrescribirlos
creando un archivo `data/config.json` junto a la aplicación.
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

APP_NAME = "vidPOS"
APP_VERSION = "0.1.0"
APP_SLOGAN = "Vende fácil, controla todo"


def _resolve_app_dir() -> Path:
    """Carpeta base de la aplicación.

    - En desarrollo: carpeta del proyecto (donde está pyproject.toml).
    - En ejecutable PyInstaller: carpeta donde está el .exe.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    # config.py está en src/vidpos/config.py -> subimos 3 niveles
    return Path(__file__).resolve().parents[2]


def _resolve_resource_dir() -> Path:
    """Carpeta de recursos empaquetados (assets)."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", _resolve_app_dir()))
    return _resolve_app_dir()


APP_DIR = _resolve_app_dir()
RESOURCE_DIR = _resolve_resource_dir()

DATA_DIR = APP_DIR / "data"
LOGS_DIR = APP_DIR / "logs"
BACKUPS_DIR = APP_DIR / "backups"
TICKETS_DIR = APP_DIR / "tickets"
REPORTS_DIR = APP_DIR / "reportes"
ASSETS_DIR = RESOURCE_DIR / "assets"

for _d in (DATA_DIR, LOGS_DIR, BACKUPS_DIR, TICKETS_DIR, REPORTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)


@dataclass
class AppConfig:
    """Configuración del negocio. Serializable a JSON."""

    # Identidad
    business_name: str = "Mi Tienda"
    business_slogan: str = "Donde siempre hay de todo"
    business_address: str = ""
    business_phone: str = ""
    business_tax_id: str = ""

    # Regional
    currency_symbol: str = "$"
    currency_code: str = "USD"
    locale: str = "es_NI"
    timezone: str = "America/Managua"

    # Operación
    low_stock_alert: bool = True
    allow_negative_stock: bool = False
    require_cash_session: bool = True
    default_payment_method: str = "Efectivo"
    payment_methods: list[str] = field(
        default_factory=lambda: ["Efectivo", "Transferencia", "Tarjeta", "Otro"]
    )

    # Ticket / impresión
    ticket_width_mm: int = 80
    ticket_print_logo: bool = True
    ticket_footer_message: str = "¡Gracias por su compra!"
    auto_print_on_sale: bool = False

    # Seguridad
    pbkdf2_iterations: int = 120_000
    session_timeout_minutes: int = 0  # 0 = sin timeout
    max_login_attempts: int = 5

    # Respaldo
    auto_backup_on_cash_close: bool = True
    backup_keep_count: int = 30

    # Interfaz
    theme: str = "light"
    window_width: int = 1280
    window_height: int = 760

    @classmethod
    def load(cls, path: Path | None = None) -> "AppConfig":
        path = path or (DATA_DIR / "config.json")
        if not path.exists():
            cfg = cls()
            cfg.save(path)
            return cfg
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return cls()
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in raw.items() if k in known})

    def save(self, path: Path | None = None) -> None:
        path = path or (DATA_DIR / "config.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(asdict(self), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


# Colores del tema (centralizados; la UI los consume desde aquí)
COLORS = {
    "primary": "#69B238",
    "primary_dark": "#4E8A28",
    "danger": "#E7342A",
    "warning": "#F6C40E",
    "info": "#2563EB",
    "dark": "#222222",
    "light": "#F6F7F8",
    "white": "#FFFFFF",
    "gray": "#6B7280",
    "gray_light": "#E5E7EB",
    "border": "#D1D5DB",
    "success_bg": "#E8F5E9",
    "danger_bg": "#FFEBEE",
}