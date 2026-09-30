"""Panel de cobro: forma de pago, efectivo, cambio, botón COBRAR.

Layout con 3 zonas verticales claras para garantizar que todo sea visible
en resoluciones pequeñas (1366x720).
"""
from __future__ import annotations

import tkinter as tk

from vidpos.ui import theme


class PaymentPanelMixin:
    """Mixin: panel derecho con cobro."""

    def _build_payment_panel(self, parent: tk.Frame) -> None:
            right = tk.Frame(
                parent, bg=theme.COLORS["white"], width=360,
                highlightthickness=1, highlightbackground=theme.COLORS["border"],
            )
            right.pack(side="right", fill="y")
            right.pack_propagate(False)

            # Variables compartidas
            self.total_var = tk.StringVar(value="$0.00")
            self.subtotal_var = tk.StringVar(value="$0.00")
            self.payment_method_var = tk.StringVar(value="Efectivo")
            self.received_var = tk.StringVar()
            self.cash_status_var = tk.StringVar(value="Ingrese el efectivo recibido")
            self.change_var = tk.StringVar(value="$0.00")
            self.print_ticket_var = tk.BooleanVar(value=True)
            self.payment_buttons: dict[str, tk.Button] = {}

            # =========================================================
            # ZONA 1 (ARRIBA) — reservada PRIMERO para garantizar visibilidad
            # Contiene: TOTAL + FORMA DE PAGO
            # =========================================================
            top = tk.Frame(right, bg=theme.COLORS["white"])
            top.pack(side="top", fill="x", padx=12, pady=(12, 6))

            # --- Card del TOTAL ---
            total_card = tk.Frame(top, bg=theme.COLORS["primary_light"])
            total_card.pack(fill="x", pady=(0, 10))

            tk.Label(
                total_card, text="TOTAL A COBRAR",
                bg=theme.COLORS["primary_light"], fg=theme.COLORS["primary_dark"],
                font=theme.FONTS["tiny"],
            ).pack(anchor="w", padx=12, pady=(8, 0))

            tk.Label(
                total_card, textvariable=self.total_var,
                bg=theme.COLORS["primary_light"], fg=theme.COLORS["primary_dark"],
                font=theme.FONTS["price_big"],
            ).pack(anchor="w", padx=12, pady=(0, 8))

            # --- Forma de pago ---
            tk.Label(
                top, text="FORMA DE PAGO",
                bg=theme.COLORS["white"], fg=theme.COLORS["gray"],
                font=theme.FONTS["tiny"],
            ).pack(anchor="w", pady=(0, 4))

            payment_bar = tk.Frame(top, bg=theme.COLORS["white"])
            payment_bar.pack(fill="x")

            for method, label in [
                ("Efectivo", "EFECTIVO"),
                ("Transferencia", "TRANSF."),
                ("Otro", "OTRO"),
            ]:
                btn = theme.make_button(
                    payment_bar, label, lambda m=method: self._choose_payment(m),
                    kind="neutral", padx=4, pady=6, font_key="tiny",
                )
                btn.pack(side="left", fill="x", expand=True, padx=2)
                self.payment_buttons[method] = btn

            # =========================================================
            # ZONA 3 (ABAJO) — checkbox + COBRAR
            # =========================================================
            footer = tk.Frame(right, bg=theme.COLORS["white"])
            footer.pack(side="bottom", fill="x", padx=12, pady=(4, 10))

            tk.Checkbutton(
                footer, text="Imprimir ticket al cobrar",
                variable=self.print_ticket_var, bg=theme.COLORS["white"],
                activebackground=theme.COLORS["white"], font=theme.FONTS["tiny"],
            ).pack(anchor="w", pady=(0, 4))

            self.checkout_btn = theme.make_button(
                footer, "COBRAR  ·  F4", self._finalize_sale,
                kind="accent", padx=20, pady=11, font_key="h4",
            )
            self.checkout_btn.pack(fill="x")

            tk.Label(
                footer,
                text="En efectivo: escriba el recibido y presione Enter",
                bg=theme.COLORS["white"], fg=theme.COLORS["gray"],
                font=theme.FONTS["tiny"],
            ).pack(pady=(3, 0))

            # =========================================================
            # ZONA 2 (MEDIA) — efectivo recibido + cambio
            # Se empaqueta después del footer para quedar entre top y footer
            # =========================================================
            middle = tk.Frame(right, bg=theme.COLORS["white"])
            middle.pack(side="bottom", fill="x", padx=12, pady=(0, 6))

            self.cash_frame = tk.Frame(middle, bg=theme.COLORS["white"])
            self.cash_frame.pack(fill="x")

            tk.Label(
                self.cash_frame, text="EFECTIVO RECIBIDO",
                bg=theme.COLORS["white"], fg=theme.COLORS["text"],
                font=theme.FONTS["small_bold"],
            ).pack(anchor="w", pady=(2, 2))

            self.received_entry = theme.make_entry(
                self.cash_frame, textvariable=self.received_var,
                font_key="h3", justify="right",
            )
            self.received_entry.pack(fill="x", ipady=4)

            quick = tk.Frame(self.cash_frame, bg=theme.COLORS["white"])
            quick.pack(fill="x", pady=(5, 3))

            theme.make_button(
                quick, "PAGO EXACTO", self._set_exact_payment,
                kind="accent", padx=6, pady=4, font_key="tiny",
            ).pack(side="left", fill="x", expand=True, padx=2)

            for amount in (5, 10, 20, 50):
                theme.make_button(
                    quick, f"${amount}", lambda a=amount: self._set_received(a),
                    kind="neutral", padx=4, pady=4, font_key="tiny",
                ).pack(side="left", fill="x", expand=True, padx=2)

            status_card = tk.Frame(self.cash_frame, bg=theme.COLORS["gray_light"])
            status_card.pack(fill="x", pady=(4, 2))

            tk.Label(
                status_card, textvariable=self.cash_status_var,
                bg=theme.COLORS["gray_light"], fg=theme.COLORS["gray"],
                font=theme.FONTS["tiny"],
            ).pack(anchor="w", padx=10, pady=(5, 0))

            self.change_label = tk.Label(
                status_card, textvariable=self.change_var,
                bg=theme.COLORS["gray_light"], fg=theme.COLORS["accent"],
                font=theme.FONTS["price_med"],
            )
            self.change_label.pack(anchor="w", padx=10, pady=(0, 5))

            self.noncash_frame = tk.Frame(middle, bg=theme.COLORS["primary_light"])
            tk.Label(
                self.noncash_frame, text="PAGO NO EFECTIVO",
                bg=theme.COLORS["primary_light"], fg=theme.COLORS["primary_dark"],
                font=theme.FONTS["small_bold"],
            ).pack(anchor="w", padx=12, pady=(14, 3))
            tk.Label(
                self.noncash_frame,
                text="No necesita ingresar efectivo.\nPresione COBRAR para registrar la venta.",
                bg=theme.COLORS["primary_light"], fg=theme.COLORS["primary_dark"],
                justify="left", font=theme.FONTS["small"], padx=12, pady=8,
            ).pack(anchor="w")

            # Estado inicial del UI de pago
            self._update_payment_ui()

            # Bindings
            self.received_entry.bind("<KeyRelease>", lambda e: self._calculate_change())
            self.received_entry.bind("<Return>", lambda e: self._finalize_sale())
            self.bind_all("<F4>", lambda e: self._finalize_sale())
            self.bind_all("<F2>", lambda e: self.barcode_entry.focus_set())

    # =========================================================================
    # Forma de pago y cambio
    # =========================================================================
    def _choose_payment(self, method: str) -> None:
        self.payment_method_var.set(method)
        self._update_payment_ui()
        self._calculate_change()
        self._save_draft()

    def _update_payment_ui(self) -> None:
        method = self.payment_method_var.get()
        for m, b in self.payment_buttons.items():
            if m == method:
                b.configure(bg=theme.COLORS["primary"], fg="white",
                            activebackground=theme.COLORS["primary_dark"])
            else:
                b.configure(bg=theme.COLORS["gray_light"], fg=theme.COLORS["text"],
                            activebackground=theme.COLORS["border"])

        self.cash_frame.pack_forget()
        self.noncash_frame.pack_forget()

        if method == "Efectivo":
            self.cash_frame.pack(fill="x")
            self.received_entry.configure(state="normal")
        else:
            self.noncash_frame.pack(fill="x")

    def _set_received(self, value: float) -> None:
        self.received_var.set(f"{value:.2f}")
        self._calculate_change()
        self._save_draft()
        self.received_entry.focus_set()

    def _set_exact_payment(self) -> None:
        self._set_received(self._current_total())

    def _current_total(self) -> float:
        return sum(item.subtotal for item in self.cart)

    def _calculate_change(self, event=None) -> None:
        total = self._current_total()
        if self.payment_method_var.get() != "Efectivo":
            self.change_var.set("$0.00")
            self.cash_status_var.set("Pago no efectivo")
            self.change_label.configure(fg=theme.COLORS["gray"])
            return

        raw = self.received_var.get().strip()
        if not raw:
            self.cash_status_var.set("Ingrese el efectivo recibido")
            self.change_var.set("$0.00")
            self.change_label.configure(fg=theme.COLORS["gray"])
            return

        try:
            received = float(raw)
        except ValueError:
            self.cash_status_var.set("Monto inválido")
            self.change_var.set("$0.00")
            self.change_label.configure(fg=theme.COLORS["danger"])
            return

        if received < total:
            self.cash_status_var.set("FALTA PARA COMPLETAR EL PAGO")
            self.change_var.set(f"${total - received:.2f}")
            self.change_label.configure(fg=theme.COLORS["danger"])
        else:
            self.cash_status_var.set("CAMBIO A ENTREGAR")
            self.change_var.set(f"${received - total:.2f}")
            self.change_label.configure(fg=theme.COLORS["accent"])