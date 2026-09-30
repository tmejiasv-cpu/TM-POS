"""Servicio de caja: apertura, cierre, arqueo e ingresos.

Reglas de negocio:
  - Solo puede existir UNA caja abierta por usuario a la vez.
  - El fondo inicial queda registrado con el usuario y la hora.
  - El cierre requiere arqueo por denominaciones.
  - No se puede cerrar caja con gastos pendientes de aprobación.
  - Los ingresos de caja afectan el efectivo esperado pero NO las ventas.
  - Las devoluciones en efectivo reducen el efectivo esperado.
  - Los gastos aprobados reducen el efectivo esperado.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime

from vidpos.core.database import Database

log = logging.getLogger(__name__)


# =============================================================================
# Excepciones
# =============================================================================
class CashError(Exception):
    """Error de dominio en caja."""


class CashSessionNotFoundError(CashError):
    """No existe la jornada de caja indicada."""


class CashAlreadyOpenError(CashError):
    """Ya existe una caja abierta para este usuario."""


class CashAlreadyClosedError(CashError):
    """La caja ya está cerrada."""


class PendingExpensesError(CashError):
    """No se puede cerrar caja con gastos pendientes."""

    def __init__(self, count: int):
        self.count = count
        super().__init__(
            f"Hay {count} gasto(s) pendiente(s) de aprobación. "
            "Debe aprobarlos o rechazarlos antes de cerrar la caja."
        )


# =============================================================================
# DTOs
# =============================================================================
@dataclass
class CashSession:
    """Resumen de una jornada de caja."""
    id: int
    user_id: int
    user_name: str
    opened_at: str
    closed_at: str | None
    opening_amount: float
    counted_amount: float | None
    expected_amount: float | None
    difference: float | None
    status: str
    note: str


@dataclass
class CashSummary:
    """Resumen de movimientos de la jornada."""
    opening_amount: float
    sales_cash: float
    sales_transfer: float
    sales_other: float
    cash_inflows: float
    approved_expenses: float
    cash_refunds: float
    pending_expenses_count: int
    expected_cash: float
    total_sales: float


@dataclass
class CashCloseResult:
    """Resultado del cierre de caja."""
    session_id: int
    expected: float
    counted: float
    difference: float
    status: str          # "CUADRADA", "SOBRANTE", "FALTANTE"
    denominations: dict[str, int]


# =============================================================================
# Denominaciones estándar
# =============================================================================
DEFAULT_DENOMINATIONS = [20.0, 10.0, 5.0, 1.0, 0.25, 0.10, 0.05, 0.01]


# =============================================================================
# Servicio
# =============================================================================
class CashService:
    """Apertura, cierre y control del flujo de efectivo."""

    def __init__(self, db: Database) -> None:
        self.db = db

    # =========================================================================
    # Consulta de sesión activa
    # =========================================================================
    def get_open_session(self, user_id: int) -> CashSession | None:
        """Devuelve la sesión abierta del usuario o None."""
        row = self.db.one(
            """SELECT c.*, u.full_name AS user_name
               FROM cash_sessions c
               JOIN users u ON u.id = c.user_id
               WHERE c.user_id = ? AND c.status = 'OPEN'
               ORDER BY c.id DESC
               LIMIT 1""",
            (user_id,),
        )
        if not row:
            return None
        return self._row_to_session(row)

    def get_session(self, session_id: int) -> CashSession | None:
        row = self.db.one(
            """SELECT c.*, u.full_name AS user_name
               FROM cash_sessions c
               JOIN users u ON u.id = c.user_id
               WHERE c.id = ?""",
            (session_id,),
        )
        return self._row_to_session(row) if row else None

    # =========================================================================
    # Apertura
    # =========================================================================
    def open_session(
        self,
        *,
        user_id: int,
        opening_amount: float,
        note: str = "",
    ) -> int:
        """Abre una jornada de caja. Devuelve el id de la sesión."""
        if opening_amount < 0:
            raise CashError("El fondo inicial no puede ser negativo.")

        existing = self.get_open_session(user_id)
        if existing:
            raise CashAlreadyOpenError(
                f"Ya existe una caja abierta (#{existing.id}) para este usuario."
            )

        cur = self.db.execute(
            """INSERT INTO cash_sessions(
                   user_id, opened_at, opening_amount, status, note
               ) VALUES(?,?,?,?,?)""",
            (user_id, self._now(), opening_amount, "OPEN", note or ""),
        )
        session_id = int(cur.lastrowid)
        log.info(
            "Caja abierta #%s por user=%s con fondo=%.2f",
            session_id, user_id, opening_amount,
        )
        return session_id

    # =========================================================================
    # Ingresos de caja
    # =========================================================================
    def register_inflow(
        self,
        *,
        session_id: int,
        concept: str,
        amount: float,
        user_id: int,
        note: str = "",
    ) -> int:
        """Registra un ingreso de efectivo ajeno a ventas.

        Se usa para pagos de cuentas antiguas, reintegros, aportes del dueño, etc.
        Aumenta el efectivo esperado del corte.
        """
        if amount <= 0:
            raise CashError("El monto debe ser mayor que cero.")
        concept = (concept or "").strip()
        if not concept:
            raise CashError("El concepto es obligatorio.")

        session = self.get_session(session_id)
        if not session:
            raise CashSessionNotFoundError(f"Sesión {session_id} no existe.")
        if session.status != "OPEN":
            raise CashAlreadyClosedError(
                f"La sesión #{session_id} ya está cerrada."
            )

        cur = self.db.execute(
            """INSERT INTO cash_inflows(
                   cash_session_id, concept, amount, note, created_by, created_at
               ) VALUES(?,?,?,?,?,?)""",
            (session_id, concept, amount, note or "", user_id, self._now()),
        )
        inflow_id = int(cur.lastrowid)
        log.info(
            "Ingreso caja #%s sesión=%s monto=%.2f concepto=%r",
            inflow_id, session_id, amount, concept,
        )
        return inflow_id

    def list_inflows(self, session_id: int) -> list[dict]:
        rows = self.db.all(
            """SELECT ci.*, u.full_name AS user_name
               FROM cash_inflows ci
               JOIN users u ON u.id = ci.created_by
               WHERE ci.cash_session_id = ?
               ORDER BY ci.id DESC""",
            (session_id,),
        )
        return [dict(r) for r in rows]

    # =========================================================================
    # Cálculo del resumen / efectivo esperado
    # =========================================================================
    def get_summary(self, session_id: int) -> CashSummary:
        """Calcula el resumen financiero de la jornada.

        Fórmula del efectivo esperado:
            efectivo_esperado = fondo_inicial
                              + ventas_en_efectivo
                              + ingresos_de_caja
                              - gastos_aprobados
                              - devoluciones_en_efectivo
        """
        session = self.get_session(session_id)
        if not session:
            raise CashSessionNotFoundError(f"Sesión {session_id} no existe.")

        opening = float(session.opening_amount)

        sales_cash = float(self.db.scalar(
            """SELECT COALESCE(SUM(total), 0) FROM sales
               WHERE cash_session_id = ?
                 AND payment_method = 'Efectivo'
                 AND status = 'COMPLETED'""",
            (session_id,), default=0.0,
        ) or 0.0)

        sales_transfer = float(self.db.scalar(
            """SELECT COALESCE(SUM(total), 0) FROM sales
               WHERE cash_session_id = ?
                 AND payment_method = 'Transferencia'
                 AND status = 'COMPLETED'""",
            (session_id,), default=0.0,
        ) or 0.0)

        sales_other = float(self.db.scalar(
            """SELECT COALESCE(SUM(total), 0) FROM sales
               WHERE cash_session_id = ?
                 AND payment_method NOT IN ('Efectivo','Transferencia')
                 AND status = 'COMPLETED'""",
            (session_id,), default=0.0,
        ) or 0.0)

        cash_inflows = float(self.db.scalar(
            """SELECT COALESCE(SUM(amount), 0) FROM cash_inflows
               WHERE cash_session_id = ?""",
            (session_id,), default=0.0,
        ) or 0.0)

        approved_expenses = float(self.db.scalar(
            """SELECT COALESCE(SUM(amount), 0) FROM expenses
               WHERE cash_session_id = ? AND status = 'APPROVED'""",
            (session_id,), default=0.0,
        ) or 0.0)

        cash_refunds = float(self.db.scalar(
            """SELECT COALESCE(SUM(total_refund), 0) FROM sale_returns
               WHERE cash_session_id = ? AND refund_method = 'Efectivo'""",
            (session_id,), default=0.0,
        ) or 0.0)

        pending_expenses_count = int(self.db.scalar(
            """SELECT COUNT(*) FROM expenses
               WHERE cash_session_id = ? AND status = 'PENDING'""",
            (session_id,), default=0,
        ) or 0)

        expected = (
            opening + sales_cash + cash_inflows
            - approved_expenses - cash_refunds
        )

        total_sales = sales_cash + sales_transfer + sales_other

        return CashSummary(
            opening_amount=opening,
            sales_cash=sales_cash,
            sales_transfer=sales_transfer,
            sales_other=sales_other,
            cash_inflows=cash_inflows,
            approved_expenses=approved_expenses,
            cash_refunds=cash_refunds,
            pending_expenses_count=pending_expenses_count,
            expected_cash=expected,
            total_sales=total_sales,
        )

    # =========================================================================
    # Cierre de caja
    # =========================================================================
    def close_session(
        self,
        *,
        session_id: int,
        denominations: dict[str, int],
        user_id: int,
        allow_pending: bool = False,
        note: str = "",
    ) -> CashCloseResult:
        """Cierra la jornada aplicando arqueo por denominaciones.

        Args:
            denominations: { "20.00": 5, "10.00": 2, ... } cantidad por denominación.
            allow_pending: si False (default), falla si hay gastos pendientes.
        """
        session = self.get_session(session_id)
        if not session:
            raise CashSessionNotFoundError(f"Sesión {session_id} no existe.")
        if session.status == "CLOSED":
            raise CashAlreadyClosedError(f"La sesión #{session_id} ya está cerrada.")

        summary = self.get_summary(session_id)

        if summary.pending_expenses_count > 0 and not allow_pending:
            raise PendingExpensesError(summary.pending_expenses_count)

        counted = self._calculate_counted(denominations)
        expected = summary.expected_cash
        difference = round(counted - expected, 2)

        if abs(difference) < 0.005:
            status = "CUADRADA"
        elif difference > 0:
            status = "SOBRANTE"
        else:
            status = "FALTANTE"

        self.db.execute(
            """UPDATE cash_sessions
               SET closed_at = ?, counted_amount = ?, expected_amount = ?,
                   difference = ?, denominations_json = ?, note = ?, status = 'CLOSED'
               WHERE id = ?""",
            (
                self._now(), counted, expected, difference,
                json.dumps(denominations, ensure_ascii=False),
                note or session.note,
                session_id,
            ),
        )

        log.info(
            "Caja cerrada #%s esperado=%.2f contado=%.2f dif=%.2f (%s)",
            session_id, expected, counted, difference, status,
        )

        return CashCloseResult(
            session_id=session_id,
            expected=expected,
            counted=counted,
            difference=difference,
            status=status,
            denominations=dict(denominations),
        )

    # =========================================================================
    # Historial de cortes
    # =========================================================================
    def list_closed_sessions(
        self,
        *,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 500,
    ) -> list[CashSession]:
        clauses = ["status = 'CLOSED'"]
        params: list = []
        if date_from:
            clauses.append("date(opened_at) >= date(?)")
            params.append(date_from)
        if date_to:
            clauses.append("date(opened_at) <= date(?)")
            params.append(date_to)

        sql = f"""
            SELECT c.*, u.full_name AS user_name
            FROM cash_sessions c
            JOIN users u ON u.id = c.user_id
            WHERE {' AND '.join(clauses)}
            ORDER BY c.id DESC
            LIMIT ?
        """
        params.append(limit)
        rows = self.db.all(sql, tuple(params))
        return [self._row_to_session(r) for r in rows]

    # =========================================================================
    # Helpers
    # =========================================================================
    @staticmethod
    def _calculate_counted(denominations: dict[str, int]) -> float:
        """Suma el efectivo contado a partir del desglose por denominación."""
        total = 0.0
        for denom_str, qty in denominations.items():
            try:
                denom = float(denom_str)
                count = int(qty)
            except (ValueError, TypeError):
                raise CashError(f"Denominación o cantidad inválida: {denom_str}={qty}")
            if denom <= 0 or count < 0:
                raise CashError("Denominaciones y cantidades deben ser positivas.")
            total += denom * count
        return round(total, 2)

    @staticmethod
    def _row_to_session(row) -> CashSession:
        return CashSession(
            id=int(row["id"]),
            user_id=int(row["user_id"]),
            user_name=row["user_name"],
            opened_at=row["opened_at"],
            closed_at=row["closed_at"],
            opening_amount=float(row["opening_amount"]),
            counted_amount=(
                float(row["counted_amount"]) if row["counted_amount"] is not None else None
            ),
            expected_amount=(
                float(row["expected_amount"]) if row["expected_amount"] is not None else None
            ),
            difference=(
                float(row["difference"]) if row["difference"] is not None else None
            ),
            status=row["status"],
            note=row["note"] or "",
        )

    @staticmethod
    def _now() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")