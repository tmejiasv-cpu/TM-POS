"""Tema visual de vidPOS: colores, fuentes, estilos ttk.

Paleta institucional basada en el logo oficial:
  - Azul vidPOS    #1E7FD6  → acción principal
  - Azul oscuro    #0F2137  → sidebar, texto fuerte
  - Verde check    #2E9B47  → confirmación, éxito
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk


# =============================================================================
# Paleta institucional
# =============================================================================
COLORS = {
    # ---------- Marca primaria (azul vidPOS) ----------
    "primary":         "#1E7FD6",
    "primary_dark":    "#155FA8",
    "primary_light":   "#E8F2FB",

    # ---------- Marca secundaria (verde check) ----------
    "accent":          "#2E9B47",
    "accent_dark":     "#207233",
    "accent_light":    "#E6F4EA",

    # ---------- Dark (azul oscuro del "vid") ----------
    "dark":            "#0F2137",
    "dark_2":          "#1A2F4A",
    "dark_3":          "#243B5C",

    # ---------- Estados ----------
    "danger":          "#D93025",
    "danger_dark":     "#B02418",
    "danger_light":    "#FCE8E6",
    "warning":         "#F4B400",
    "warning_dark":    "#C69000",
    "warning_light":   "#FEF7E0",
    "success":         "#2E9B47",
    "info":            "#1E7FD6",

    # ---------- Neutros ----------
    "light":           "#F6F7F9",
    "white":           "#FFFFFF",
    "gray":            "#6B7280",
    "gray_light":      "#E5E7EB",
    "border":          "#D1D5DB",
    "text":            "#1F2937",
    "text_muted":      "#6B7280",
}


# =============================================================================
# Fuentes
# =============================================================================
FONT_FAMILY = "Segoe UI"

FONTS = {
    "h1":         (FONT_FAMILY, 22, "bold"),
    "h2":         (FONT_FAMILY, 18, "bold"),
    "h3":         (FONT_FAMILY, 15, "bold"),
    "h4":         (FONT_FAMILY, 12, "bold"),
    "body":       (FONT_FAMILY, 10),
    "body_bold":  (FONT_FAMILY, 10, "bold"),
    "small":      (FONT_FAMILY, 9),
    "small_bold": (FONT_FAMILY, 9, "bold"),
    "tiny":       (FONT_FAMILY, 8),
    "mono":       ("Consolas", 9),
    "price_big":  (FONT_FAMILY, 26, "bold"),
    "price_med":  (FONT_FAMILY, 18, "bold"),
    "brand":      (FONT_FAMILY, 30, "bold"),
}


# =============================================================================
# Configuración global de estilos ttk
# =============================================================================
def configure_ttk_styles(root: tk.Tk) -> ttk.Style:
    """Configura el tema ttk. Llamar una vez tras crear la ventana."""
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    # ----- Treeview (tablas) -----
    style.configure(
        "Treeview",
        background=COLORS["white"],
        foreground=COLORS["text"],
        fieldbackground=COLORS["white"],
        rowheight=30,
        font=FONTS["body"],
        borderwidth=0,
    )
    style.configure(
        "Treeview.Heading",
        background=COLORS["primary_light"],
        foreground=COLORS["primary_dark"],
        font=FONTS["small_bold"],
        relief="flat",
        padding=(8, 8),
    )
    style.map(
        "Treeview",
        background=[("selected", COLORS["primary"])],
        foreground=[("selected", "white")],
    )
    style.map(
        "Treeview.Heading",
        background=[("active", COLORS["primary_light"])],
    )

    # ----- Notebook (pestañas) -----
    style.configure("TNotebook", background=COLORS["light"], borderwidth=0)
    style.configure(
        "TNotebook.Tab",
        padding=(16, 8),
        font=FONTS["small_bold"],
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", COLORS["white"])],
        foreground=[("selected", COLORS["primary_dark"])],
    )

    # ----- Combobox -----
    style.configure("TCombobox", padding=4, font=FONTS["body"])

    # ----- Scrollbar -----
    style.configure(
        "Vertical.TScrollbar",
        background=COLORS["gray_light"],
        troughcolor=COLORS["light"],
        borderwidth=0,
        arrowsize=12,
    )

    return style


# =============================================================================
# Fábricas de widgets (tk clásico para máximo control visual)
# =============================================================================
_BUTTON_PALETTE = {
    "primary": (COLORS["primary"], "white", COLORS["primary_dark"]),
    "danger":  (COLORS["danger"], "white", COLORS["danger_dark"]),
    "warning": (COLORS["warning"], COLORS["dark"], COLORS["warning_dark"]),
    "accent":  (COLORS["accent"], "white", COLORS["accent_dark"]),
    "info":    (COLORS["info"], "white", "#1D4ED8"),
    "neutral": (COLORS["gray_light"], COLORS["text"], COLORS["border"]),
    "ghost":   (COLORS["white"], COLORS["text"], COLORS["light"]),
    "sidebar": (COLORS["dark"], "white", COLORS["primary"]),
}


def make_button(
    parent,
    text: str,
    command,
    *,
    kind: str = "primary",
    width: int | None = None,
    padx: int = 16,
    pady: int = 8,
    font_key: str = "body_bold",
) -> tk.Button:
    bg, fg, active_bg = _BUTTON_PALETTE.get(kind, _BUTTON_PALETTE["primary"])
    btn = tk.Button(
        parent,
        text=text,
        command=command,
        bg=bg,
        fg=fg,
        activebackground=active_bg,
        activeforeground=fg,
        relief="flat",
        bd=0,
        font=FONTS[font_key],
        padx=padx,
        pady=pady,
        cursor="hand2",
    )
    if width:
        btn.configure(width=width)
    return btn


def make_entry(
    parent,
    *,
    textvariable=None,
    width: int | None = None,
    justify: str = "left",
    font_key: str = "body",
    show: str | None = None,
) -> tk.Entry:
    entry = tk.Entry(
        parent,
        textvariable=textvariable,
        font=FONTS[font_key],
        relief="solid",
        bd=1,
        highlightthickness=0,
        highlightbackground=COLORS["border"],
        highlightcolor=COLORS["primary"],
        justify=justify,
    )
    if width:
        entry.configure(width=width)
    if show:
        entry.configure(show=show)
    return entry


def make_label(
    parent,
    text: str = "",
    *,
    font_key: str = "body",
    fg: str | None = None,
    bg: str | None = None,
    textvariable=None,
    anchor: str = "w",
    justify: str = "left",
    wraplength: int = 0,
) -> tk.Label:
    return tk.Label(
        parent,
        text=text,
        textvariable=textvariable,
        font=FONTS[font_key],
        fg=fg or COLORS["text"],
        bg=bg or COLORS["white"],
        anchor=anchor,
        justify=justify,
        wraplength=wraplength,
    )


def make_card(parent, *, padding: int = 0, bg: str | None = None, **kwargs) -> tk.Frame:
    return tk.Frame(
        parent,
        bg=bg or COLORS["white"],
        highlightthickness=1,
        highlightbackground=COLORS["border"],
        padx=padding,
        pady=padding,
        **kwargs,
    )