"""Carga centralizada de recursos de marca de vidPOS.

Todos los paths apuntan a assets/ con nombres estandarizados.
Las imágenes se cachean para no recargarlas en cada llamada.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from vidpos.config import ASSETS_DIR

log = logging.getLogger(__name__)

# ---------- Rutas estándar ----------
ISOTIPO             = ASSETS_DIR / "isotipo.png"
ISOTIPO_WHITE       = ASSETS_DIR / "isotipo_white.png"       # opcional
LOGO_HORIZONTAL     = ASSETS_DIR / "logo_horizontal.png"
LOGO_COMPACT        = ASSETS_DIR / "logo_compact.png"        # opcional
LOGO_WHITE          = ASSETS_DIR / "logo_white.png"
LOGO_BLACK          = ASSETS_DIR / "logo_horizontal_black.png"
LOGO_WITH_TERMINAL  = ASSETS_DIR / "logo_horizontal_with_terminal.png"
LOGO_SPLASH         = ASSETS_DIR / "logo_splash.png"         # opcional
FAVICON             = ASSETS_DIR / "favicon.png"
ICON_ICO            = ASSETS_DIR / "vidpos.ico"


def has_pillow() -> bool:
    """Verifica si Pillow está disponible."""
    try:
        import PIL  # noqa: F401
        return True
    except ImportError:
        return False


@lru_cache(maxsize=64)
def _load_pil_image(path: str, max_w: int, max_h: int):
    """Carga y redimensiona una imagen con Pillow. Cacheada."""
    if not has_pillow():
        return None
    from PIL import Image

    p = Path(path)
    if not p.exists():
        log.debug("Asset no encontrado: %s", p)
        return None
    try:
        img = Image.open(p)
        if img.mode not in ("RGBA", "RGB"):
            img = img.convert("RGBA")
        img.thumbnail((max_w, max_h), Image.LANCZOS)
        return img
    except Exception:
        log.exception("Error cargando asset %s", p)
        return None


def get_photo_image(path: Path, max_w: int, max_h: int):
    """Devuelve un ImageTk.PhotoImage listo para Tkinter.

    Retorna None si no hay Pillow o si el archivo no existe.
    """
    if not has_pillow():
        return None
    pil_img = _load_pil_image(str(path), max_w, max_h)
    if pil_img is None:
        return None
    from PIL import ImageTk
    return ImageTk.PhotoImage(pil_img)


def set_window_icon(window) -> None:
    """Aplica el ícono de la ventana. Prioriza .ico, fallback a PNG."""
    try:
        if ICON_ICO.exists():
            window.iconbitmap(str(ICON_ICO))
            return
    except Exception:
        pass
    try:
        photo = get_photo_image(ISOTIPO, 64, 64)
        if photo:
            window.iconphoto(True, photo)
            window._icon_ref = photo  # evitar garbage collector
    except Exception:
        log.debug("No se pudo aplicar el ícono de ventana")


# =============================================================================
# Helpers convenientes para los views
# =============================================================================
def logo_horizontal(width: int = 220, height: int = 60):
    """Logo horizontal a color (login, splash)."""
    return get_photo_image(LOGO_HORIZONTAL, width, height)


def logo_white(width: int = 220, height: int = 60):
    """Logo blanco para sidebar oscuro.

    Fallback a logo_horizontal si logo_white.png no existe.
    """
    path = LOGO_WHITE if LOGO_WHITE.exists() else LOGO_HORIZONTAL
    return get_photo_image(path, width, height)


def logo_black(width: int = 220, height: int = 60):
    """Logo negro monocromático para impresión B/N."""
    path = LOGO_BLACK if LOGO_BLACK.exists() else LOGO_HORIZONTAL
    return get_photo_image(path, width, height)


def logo_compact(width: int = 200, height: int = 60):
    """Logo compacto sin taglines. Fallback a horizontal."""
    path = LOGO_COMPACT if LOGO_COMPACT.exists() else LOGO_HORIZONTAL
    return get_photo_image(path, width, height)


def logo_with_terminal(width: int = 320, height: int = 320):
    """Logo con terminal POS (marketing, splash)."""
    return get_photo_image(LOGO_WITH_TERMINAL, width, height)


def logo_splash(width: int = 480, height: int = 480):
    """Logo grande para splash screen.

    Fallback a logo_with_terminal si logo_splash.png no existe.
    """
    path = LOGO_SPLASH if LOGO_SPLASH.exists() else LOGO_WITH_TERMINAL
    return get_photo_image(path, width, height)


def isotipo(size: int = 48):
    """Isotipo cuadrado (íconos, barras, botones)."""
    return get_photo_image(ISOTIPO, size, size)


def isotipo_white(size: int = 48):
    """Isotipo blanco para fondos oscuros.

    Fallback a isotipo normal si isotipo_white.png no existe.
    """
    path = ISOTIPO_WHITE if ISOTIPO_WHITE.exists() else ISOTIPO
    return get_photo_image(path, size, size)