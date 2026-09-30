"""Modal institucional moderno de vidPOS.

Diseño:
  - Tamaño adaptativo según contenido.
  - Ícono circular centrado arriba.
  - Título y mensaje centrados.
  - Bloque de detalle opcional con scroll.
  - Barra de color del tipo arriba.
  - Esquinas con borde fino.
  - Fade-in suave al aparecer.

Misma API que antes:
    modal.info(parent, título, mensaje, detalle=None)
    modal.success(parent, título, mensaje, detalle=None)
    modal.warning(parent, título, mensaje, detalle=None)
    modal.error(parent, título, mensaje, detalle=None)
    modal.confirm(parent, título, mensaje, primary_text=..., ...) -> bool

Atajos:
    Enter = aceptar
    Escape = cancelar
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from vidpos.ui.theme import COLORS, FONTS, make_button


# =============================================================================
# Configuración por tipo de modal
# =============================================================================
_TYPES = {
    "info": {
        "icon": "i",
        "color": COLORS["info"],
        "color_dark": "#1D4ED8",
    },
    "success": {
        "icon": "✓",
        "color": COLORS["success"],
        "color_dark": "#15803D",
    },
    "warning": {
        "icon": "!",
        "color": COLORS["warning"],
        "color_dark": COLORS["warning_dark"],
    },
    "error": {
        "icon": "×",
        "color": COLORS["danger"],
        "color_dark": COLORS["danger_dark"],
    },
    "question": {
        "icon": "?",
        "color": COLORS["primary"],
        "color_dark": COLORS["primary_dark"],
    },
}


# =============================================================================
# Cálculo de tamaño adaptativo
# =============================================================================
def _calc_size(message: str, detail: str | None, has_secondary: bool) -> tuple[int, int]:
    """Calcula el tamaño ideal de la ventana según el contenido."""
    msg_lines = max(1, len(message) // 45 + message.count("\n") + 1)
    detail_lines = 0
    if detail:
        detail_lines = min(
            max(3, len(str(detail)) // 45 + str(detail).count("\n")),
            14,
        )

    # Ancho: 420 base, 520 si hay detalle
    width = 520 if detail else 460

    # Alto: calculado por bloques
    base_height = 240          # ícono + título + mensaje + botones
    detail_height = detail_lines * 18 + 40 if detail else 0
    button_height = 20 if has_secondary else 0

    height = base_height + detail_height + button_height
    height = max(240, min(height, 620))

    return width, height


# =============================================================================
# Modal principal
# =============================================================================
def show_modal(
    parent: tk.Misc,
    *,
    title: str,
    message: str,
    modal_type: str = "info",
    primary_text: str = "ACEPTAR",
    secondary_text: str | None = None,
    detail: str | None = None,
) -> bool:
    """Muestra un modal moderno adaptativo. Retorna True si el usuario confirma."""
    cfg = _TYPES.get(modal_type, _TYPES["info"])
    accent = cfg["color"]
    accent_dark = cfg["color_dark"]

    result = {"value": False}

    # -------- Ventana --------
    win = tk.Toplevel(parent)
    win.title(title)
    win.configure(bg=COLORS["border"])   # fondo del borde exterior
    win.transient(parent.winfo_toplevel())
    win.grab_set()
    win.resizable(False, False)

    width, height = _calc_size(message, detail, bool(secondary_text))
    win.geometry(f"{width}x{height}")
    win.minsize(400, 220)

    # Centrar sobre el padre
    win.update_idletasks()
    parent_tk = parent.winfo_toplevel()
    px = parent_tk.winfo_rootx()
    py = parent_tk.winfo_rooty()
    pw = parent_tk.winfo_width()
    ph = parent_tk.winfo_height()
    x = max(0, px + (pw - width) // 2)
    y = max(0, py + (ph - height) // 2)
    win.geometry(f"{width}x{height}+{x}+{y}")

    # -------- Contenedor con borde fino --------
    # El "borde" es el propio fondo del Toplevel
    inner = tk.Frame(win, bg=COLORS["white"])
    inner.pack(fill="both", expand=True, padx=1, pady=1)

    # -------- Barra superior de color --------
    tk.Frame(inner, bg=accent, height=4).pack(fill="x")

    # -------- Ícono circular (Canvas) --------
    icon_frame = tk.Frame(inner, bg=COLORS["white"])
    icon_frame.pack(pady=(22, 8))

    icon_size = 56
    canvas = tk.Canvas(
        icon_frame, width=icon_size, height=icon_size,
        bg=COLORS["white"], highlightthickness=0,
    )
    canvas.pack()

    # Círculo de color
    canvas.create_oval(
        0, 0, icon_size, icon_size,
        fill=accent, outline="",
    )
    # Símbolo blanco centrado
    canvas.create_text(
        icon_size // 2, icon_size // 2 - 1,
        text=cfg["icon"],
        fill="white",
        font=("Segoe UI", 26, "bold"),
    )

    # -------- Título --------
    tk.Label(
        inner, text=title,
        bg=COLORS["white"], fg=COLORS["dark"],
        font=FONTS["h3"],
    ).pack(pady=(0, 6))

    # -------- Mensaje principal --------
    tk.Label(
        inner, text=message,
        bg=COLORS["white"], fg=COLORS["text"],
        font=FONTS["body"],
        wraplength=width - 60,
        justify="center",
    ).pack(padx=30, pady=(0, 8))

    # -------- Bloque de detalle con scroll --------
    if detail:
        detail_outer = tk.Frame(inner, bg="#F8FAFC")
        detail_outer.pack(fill="x", padx=30, pady=(4, 12))

        dtext = tk.Text(
            detail_outer, wrap="word",
            bg="#F8FAFC", fg=COLORS["text"],
            font=FONTS["mono"],
            relief="flat", borderwidth=0,
            padx=14, pady=10,
            height=min(max(len(str(detail).splitlines()), 4), 12),
            highlightthickness=0,
        )
        dtext.pack(fill="both", expand=True)

        dtext.insert("1.0", str(detail))
        dtext.configure(state="disabled")

        def _dscroll(event):
            try:
                dtext.yview_scroll(-1 if event.delta > 0 else 1, "units")
                return "break"
            except Exception:
                return None

        dtext.bind("<MouseWheel>", _dscroll)

    # -------- Botones --------
    btn_row = tk.Frame(inner, bg=COLORS["white"])
    btn_row.pack(side="bottom", pady=(8, 18))

    def close_with(value: bool):
        result["value"] = value
        try:
            win.grab_release()
        except Exception:
            pass
        win.destroy()

    # Botón secundario (izquierda)
    if secondary_text:
        theme_kind = "neutral"
        b = tk.Button(
            btn_row, text=secondary_text,
            command=lambda: close_with(False),
            bg=COLORS["gray_light"], fg=COLORS["text"],
            activebackground=COLORS["border"],
            activeforeground=COLORS["text"],
            relief="flat", bd=0,
            font=FONTS["small_bold"],
            padx=22, pady=10, cursor="hand2",
        )
        b.pack(side="left", padx=(0, 8))

    # Botón primario
    pb = tk.Button(
        btn_row, text=primary_text,
        command=lambda: close_with(True),
        bg=accent, fg="white",
        activebackground=accent_dark,
        activeforeground="white",
        relief="flat", bd=0,
        font=FONTS["small_bold"],
        padx=28, pady=10, cursor="hand2",
    )
    pb.pack(side="left")

    # Foco en el primario
    pb.focus_set()

    # -------- Atajos --------
    win.bind("<Escape>", lambda e: close_with(False))
    win.bind("<Return>", lambda e: close_with(True))

    # -------- Fade-in suave --------
    try:
        win.attributes("-alpha", 0.0)
        def _fade(step: int = 0):
            alpha = min(1.0, step / 8)
            try:
                win.attributes("-alpha", alpha)
            except Exception:
                return
            if step < 8:
                win.after(15, lambda: _fade(step + 1))
        win.after(10, _fade)
    except Exception:
        pass

    parent.wait_window(win)
    return result["value"]


# =============================================================================
# Atajos semánticos (misma API que antes)
# =============================================================================
def info(parent, title: str, message: str, detail: str | None = None) -> None:
    show_modal(parent, title=title, message=message,
               modal_type="info", detail=detail)


def success(parent, title: str, message: str, detail: str | None = None) -> None:
    show_modal(parent, title=title, message=message,
               modal_type="success", detail=detail)


def warning(parent, title: str, message: str, detail: str | None = None) -> None:
    show_modal(parent, title=title, message=message,
               modal_type="warning", detail=detail)


def error(parent, title: str, message: str, detail: str | None = None) -> None:
    show_modal(parent, title=title, message=message,
               modal_type="error", detail=detail)


def confirm(
    parent,
    title: str,
    message: str,
    *,
    primary_text: str = "CONFIRMAR",
    secondary_text: str = "CANCELAR",
    detail: str | None = None,
) -> bool:
    return show_modal(
        parent, title=title, message=message,
        modal_type="question",
        primary_text=primary_text,
        secondary_text=secondary_text,
        detail=detail,
    )