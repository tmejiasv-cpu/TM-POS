"""Vista de inicio de sesión."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from vidpos.config import APP_NAME, APP_SLOGAN, APP_VERSION, AppConfig
from vidpos.core.auth import AuthResult, AuthService
from vidpos.ui import theme
from vidpos.ui.widgets import modal


class LoginView(tk.Frame):
    """Pantalla de login. Llama a on_success cuando el usuario entra."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        auth: AuthService,
        config: AppConfig,
        on_success: Callable[[AuthResult], None],
    ) -> None:
        super().__init__(parent, bg=theme.COLORS["light"])
        self.auth = auth
        self.config = config
        self.on_success = on_success

        self._build_ui()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        # Contenedor centrado
        outer = tk.Frame(self, bg=theme.COLORS["light"])
        outer.pack(fill="both", expand=True)

        card = tk.Frame(
            outer, bg=theme.COLORS["white"],
            highlightthickness=1, highlightbackground=theme.COLORS["border"],
        )
        card.place(relx=0.5, rely=0.5, anchor="center", width=430, height=520)

        # Marca superior
        brand = tk.Frame(card, bg=theme.COLORS["white"])
        brand.pack(fill="x", pady=(36, 0))

        tk.Label(
            brand, text="vidPOS",
            bg=theme.COLORS["white"], fg=theme.COLORS["primary"],
            font=("Segoe UI", 30, "bold"),
        ).pack()
        tk.Label(
            brand, text=APP_SLOGAN,
            bg=theme.COLORS["white"], fg=theme.COLORS["gray"],
            font=theme.FONTS["small"],
        ).pack(pady=(2, 0))

        # Formulario
        form = tk.Frame(card, bg=theme.COLORS["white"])
        form.pack(fill="x", padx=55, pady=(40, 0))

        tk.Label(
            form, text="Usuario",
            bg=theme.COLORS["white"], fg=theme.COLORS["text"],
            font=theme.FONTS["small_bold"], anchor="w",
        ).pack(fill="x")
        self.username_var = tk.StringVar()
        self.username_entry = theme.make_entry(
            form, textvariable=self.username_var,
            font_key="h4",
        )
        self.username_entry.pack(fill="x", pady=(6, 16), ipady=8)

        tk.Label(
            form, text="Contraseña",
            bg=theme.COLORS["white"], fg=theme.COLORS["text"],
            font=theme.FONTS["small_bold"], anchor="w",
        ).pack(fill="x")
        self.password_var = tk.StringVar()
        self.password_entry = theme.make_entry(
            form, textvariable=self.password_var,
            font_key="h4", show="•",
        )
        self.password_entry.pack(fill="x", pady=(6, 22), ipady=8)

        self.login_btn = theme.make_button(
            form, "INGRESAR", self._attempt_login,
            kind="primary", padx=20, pady=11, font_key="h4",
        )
        self.login_btn.pack(fill="x")

        # Nota inferior
        tk.Label(
            card,
            text=f"vidPOS v{APP_VERSION}",
            bg=theme.COLORS["white"], fg=theme.COLORS["gray"],
            font=theme.FONTS["tiny"],
        ).pack(side="bottom", pady=14)

        # Atajos
        self.username_entry.bind("<Return>", lambda e: self.password_entry.focus_set())
        self.password_entry.bind("<Return>", lambda e: self._attempt_login())
        self.username_entry.focus_set()

    # ------------------------------------------------------------- acciones
    def _attempt_login(self) -> None:
        username = self.username_var.get().strip()
        password = self.password_var.get()

        result = self.auth.login(username, password)
        if not result.ok:
            modal.error(self, "Acceso denegado", result.message)
            self.password_var.set("")
            self.password_entry.focus_set()
            return

        # ¿Debe cambiar contraseña?
        if result.must_change_password:
            changed = self._prompt_change_password(result.user_id or 0, password)
            if not changed:
                # El usuario canceló el cambio: abortamos el login
                self.password_var.set("")
                self.password_entry.focus_set()
                return

        self.on_success(result)

    def _prompt_change_password(self, user_id: int, current_password: str) -> bool:
        """Solicita cambio obligatorio de contraseña. Retorna True si se cambió."""
        win = tk.Toplevel(self)
        win.title("Cambio obligatorio de contraseña")
        win.configure(bg=theme.COLORS["white"])
        win.transient(self.winfo_toplevel())
        win.grab_set()
        win.resizable(False, False)

        box = tk.Frame(win, bg=theme.COLORS["white"], padx=32, pady=28)
        box.pack(fill="both", expand=True)

        tk.Label(
            box, text="Cambio obligatorio",
            bg=theme.COLORS["white"], fg=theme.COLORS["dark"],
            font=theme.FONTS["h2"],
        ).pack(anchor="w")
        tk.Label(
            box,
            text="Por seguridad debe establecer una nueva contraseña antes de continuar.",
            bg=theme.COLORS["white"], fg=theme.COLORS["gray"],
            font=theme.FONTS["small"],
            wraplength=380, justify="left",
        ).pack(anchor="w", pady=(4, 18))

        tk.Label(box, text="Nueva contraseña", bg="white",
                 font=theme.FONTS["small_bold"], anchor="w").pack(fill="x")
        new_var = tk.StringVar()
        theme.make_entry(box, textvariable=new_var, show="•").pack(
            fill="x", pady=(4, 12), ipady=6
        )

        tk.Label(box, text="Confirmar contraseña", bg="white",
                 font=theme.FONTS["small_bold"], anchor="w").pack(fill="x")
        confirm_var = tk.StringVar()
        theme.make_entry(box, textvariable=confirm_var, show="•").pack(
            fill="x", pady=(4, 18), ipady=6
        )

        result = {"ok": False}

        def do_change():
            ok, msg = self.auth.change_password(
                user_id=user_id,
                current_password=current_password,
                new_password=new_var.get(),
                confirm_password=confirm_var.get(),
            )
            if not ok:
                modal.error(win, "No se pudo cambiar", msg)
                return
            modal.success(win, "Contraseña actualizada",
                          "La nueva contraseña quedó guardada. Bienvenido.")
            result["ok"] = True
            win.destroy()

        def cancel():
            result["ok"] = False
            win.destroy()

        btn_row = tk.Frame(box, bg="white")
        btn_row.pack(fill="x", pady=(6, 0))
        theme.make_button(
            btn_row, "CAMBIAR CONTRASEÑA", do_change,
            kind="primary", padx=18, pady=9,
        ).pack(side="left", fill="x", expand=True, padx=(0, 4))
        theme.make_button(
            btn_row, "CANCELAR", cancel,
            kind="neutral", padx=18, pady=9,
        ).pack(side="left", padx=(4, 0))

        win.bind("<Escape>", lambda e: cancel())
        win.bind("<Return>", lambda e: do_change())

        win.update_idletasks()
        # Centrar sobre el padre
        px = self.winfo_toplevel().winfo_rootx()
        py = self.winfo_toplevel().winfo_rooty()
        pw = self.winfo_toplevel().winfo_width()
        ph = self.winfo_toplevel().winfo_height()
        w = win.winfo_width()
        h = win.winfo_height()
        win.geometry(f"+{px + (pw - w) // 2}+{py + (ph - h) // 2}")

        self.wait_window(win)
        return result["ok"]