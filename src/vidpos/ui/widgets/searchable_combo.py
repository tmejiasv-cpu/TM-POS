"""Combobox editable con filtrado en vivo.

Uso:
    combo = SearchableCombo(parent, on_select=callback, on_enter=callback)
    combo.set_items([("Texto visible", valor), ...])
    combo.get_widget().pack(...)
    valor = combo.get_selected()
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable


class SearchableCombo:
    """Combobox que filtra opciones mientras el usuario escribe."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        on_select: Callable[[Any], None] | None = None,
        on_enter: Callable[[Any], None] | None = None,
        width: int = 45,
    ) -> None:
        self._on_select = on_select
        self._on_enter = on_enter
        self._all_items: list[tuple[str, Any]] = []
        self._filtered: list[tuple[str, Any]] = []
        self._suppress = False

        self.var = tk.StringVar()
        self.combo = ttk.Combobox(
            parent,
            textvariable=self.var,
            state="normal",
            width=width,
        )

        self.combo.bind("<KeyRelease>", self._on_key)
        self.combo.bind("<<ComboboxSelected>>", self._on_selected)
        self.combo.bind("<Return>", self._on_enter_key)
        self.combo.bind("<Escape>", self._on_escape)

    # ------------------------------------------------------------------ API
    def set_items(self, items: list[tuple[str, Any]]) -> None:
        self._all_items = list(items)
        self._filtered = list(items)
        self._refresh_values()

    def get_selected(self) -> Any:
        text = self.var.get().strip()
        if not text:
            return None
        for display, value in self._filtered:
            if display == text:
                return value
        low = text.lower()
        for display, value in self._filtered:
            if display.lower().startswith(low):
                return value
        return None

    def clear(self) -> None:
        self.var.set("")
        self._filtered = list(self._all_items)
        self._refresh_values()

    def focus(self) -> None:
        self.combo.focus_set()

    def get_widget(self) -> ttk.Combobox:
        return self.combo

    # ------------------------------------------------------------- internos
    def _refresh_values(self) -> None:
        self._suppress = True
        self.combo["values"] = [text for text, _ in self._filtered]
        self._suppress = False

    def _on_key(self, event) -> None:
        if self._suppress:
            return
        if event.keysym in (
            "Up", "Down", "Return", "Escape", "Tab",
            "Shift_L", "Shift_R", "Control_L", "Control_R",
            "Alt_L", "Alt_R", "Left", "Right",
            "Home", "End", "Prior", "Next",
        ):
            return

        term = self.var.get().strip().lower()
        if not term:
            self._filtered = list(self._all_items)
        else:
            self._filtered = [
                item for item in self._all_items
                if term in item[0].lower()
            ]
        self._refresh_values()

        # Desplegar el dropdown automáticamente cuando haya resultados
        if self._filtered:
            self.combo.after(10, self._post_dropdown)

    def _post_dropdown(self) -> None:
        """Abre el dropdown del combo de forma confiable (Windows)."""
        if not self._filtered:
            return

        try:
            # Método 1: Comando Tcl nativo — el más confiable
            self.combo.tk.call("ttk::combobox::Post", self.combo._w)
        except Exception:
            try:
                # Método 2: Fallback con evento
                self.combo.focus_set()
                self.combo.event_generate("<Down>")
            except Exception:
                pass

    def _on_selected(self, event=None) -> None:
        if self._on_select:
            self._on_select(self.get_selected())

    def _on_enter_key(self, event) -> str:
        if self._on_enter:
            self._on_enter(self.get_selected())
        return "break"

    def _on_escape(self, event) -> str:
        self.clear()
        return "break"