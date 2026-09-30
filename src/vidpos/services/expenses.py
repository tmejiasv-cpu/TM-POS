"""Servicio de gastos y movimientos financieros.

Reglas de negocio:
  - Los empleados registran gastos que quedan PENDING.
  - Los gerentes aprueban o rechazan esos gastos.
  - Un gasto aprobado reduce el efectivo esperado de la caja.
  - Un gasto rechazado se conserva en el historial para auditoría.
  - Los gastos de gerencia se aprueban automáticamente.
  - Un empleado ve únicamente sus propios movimientos.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from vidpos.core.database import Database

log = logging.getLogger(__name__)


# =============================================================================
# Excepciones
# =============================================================================
class ExpenseError(Exception):
    """Error de dominio en gastos."""


class ExpenseNotFoundError(ExpenseError):
    """El gasto no existe."""


class ExpenseAlreadyProcessedError(ExpenseError):
    """El gasto ya fue aprobado o rechazado."""


class PermissionDeniedError(ExpenseError):
    """El usuario no tiene permiso para esta acción."""


# =============================================================================
# Estados
# =============================================================================
class ExpenseStatus:
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


# =============================================================================
# Categorías sugeridas (opcional, para la UI)
# =============================================================================
DEFAULT_CATEGORIES = [
    "Insumos",
    "Servicios",
    "Mantenimiento",
    "Transporte",
    "Alimentos",
    "Papelería",
    "Limpieza",
    "Otros",
]


# =============================================================================
# DTOs
# =============================================================================
@dataclass
class Expense:
    """Gasto o movimiento financiero."""
    id: int
    cash_session_id: int | None
    description: str
    amount: float
    category: str
    requested_by: int
    requested_by_name: str
    requested_at: str
    status: str
    approved_by: int | None
    approved_by_name: str | None
    approved_at: str | None
    note: str

    @property
    def is_pending(self) -> bool:
        return self.status == ExpenseStatus.PENDING

    @property
    def is_approved(self) -> bool:
        return self.status == ExpenseStatus.APPROVED

    @property
    def is_rejected(self) -> bool:
        return self.status == ExpenseStatus.REJECTED


# =============================================================================
# Servicio
# =============================================================================
class ExpensesService:
    """Registro, aprobación y consulta de gastos."""

    def __init__(self, db: Database) -> None:
        self.db = db

    # =========================================================================
    # Registro
    # =========================================================================
    def register(
        self,
        *,
        description: str,
        amount: float,
        requested_by: int,
        is_admin: bool,
        cash_session_id: int | None = None,
        category: str = "",
        note: str = "",
    ) -> int:
        """Registra un gasto.

        Si is_admin=True, se aprueba automáticamente.
        Si is_admin=False, queda PENDING esperando aprobación.
        """
        description = (description or "").strip()
        if not description:
            raise ExpenseError("La descripción es obligatoria.")
        if amount <= 0:
            raise ExpenseError("El monto debe ser mayor que cero.")

        if is_admin:
            status = ExpenseStatus.APPROVED
            approved_by = requested_by
            approved_at = self._now()
        else:
            status = ExpenseStatus.PENDING
            approved_by = None
            approved_at = None

        cur = self.db.execute(
            """INSERT INTO expenses(
                   cash_session_id, description, amount, category,
                   requested_by, requested_at, status,
                   approved_by, approved_at, note
               ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (
                cash_session_id, description, amount, category or "",
                requested_by, self._now(), status,
                approved_by, approved_at, note or "",
            ),
        )
        expense_id = int(cur.lastrowid)
        log.info(
            "Gasto #%s registrado: monto=%.2f estado=%s por user=%s",
            expense_id, amount, status, requested_by,
        )
        return expense_id

    # =========================================================================
    # Aprobación / rechazo
    # =========================================================================
    def approve(
        self,
        *,
        expense_id: int,
        approved_by: int,
        is_admin: bool,
    ) -> None:
        """Aprueba un gasto pendiente. Solo gerencia."""
        if not is_admin:
            raise PermissionDeniedError("Solo Gerencia puede aprobar gastos.")

        expense = self.get(expense_id)
        if not expense:
            raise ExpenseNotFoundError(f"Gasto {expense_id} no existe.")
        if expense.status != ExpenseStatus.PENDING:
            raise ExpenseAlreadyProcessedError(
                f"El gasto ya está {expense.status.lower()}."
            )

        self.db.execute(
            """UPDATE expenses
               SET status = ?, approved_by = ?, approved_at = ?
               WHERE id = ? AND status = ?""",
            (ExpenseStatus.APPROVED, approved_by, self._now(),
             expense_id, ExpenseStatus.PENDING),
        )
        log.info("Gasto #%s aprobado por user=%s", expense_id, approved_by)

    def reject(
        self,
        *,
        expense_id: int,
        rejected_by: int,
        is_admin: bool,
        reason: str = "",
    ) -> None:
        """Rechaza un gasto pendiente. Solo gerencia."""
        if not is_admin:
            raise PermissionDeniedError("Solo Gerencia puede rechazar gastos.")

        expense = self.get(expense_id)
        if not expense:
            raise ExpenseNotFoundError(f"Gasto {expense_id} no existe.")
        if expense.status != ExpenseStatus.PENDING:
            raise ExpenseAlreadyProcessedError(
                f"El gasto ya está {expense.status.lower()}."
            )

        # Añadimos el motivo al campo note sin perder el original
        old_note = expense.note or ""
        reason = (reason or "").strip()
        if reason:
            new_note = f"{old_note} · Rechazo: {reason}" if old_note else f"Rechazo: {reason}"
        else:
            new_note = old_note or "Rechazado por Gerencia"

        self.db.execute(
            """UPDATE expenses
               SET status = ?, approved_by = ?, approved_at = ?, note = ?
               WHERE id = ? AND status = ?""",
            (ExpenseStatus.REJECTED, rejected_by, self._now(), new_note,
             expense_id, ExpenseStatus.PENDING),
        )
        log.info(
            "Gasto #%s rechazado por user=%s: %s", expense_id, rejected_by, reason
        )

    # =========================================================================
    # Consultas
    # =========================================================================
    def get(self, expense_id: int) -> Expense | None:
        row = self.db.one(
            """SELECT e.*,
                      ru.full_name AS requested_by_name,
                      au.full_name AS approved_by_name
               FROM expenses e
               JOIN users ru ON ru.id = e.requested_by
               LEFT JOIN users au ON au.id = e.approved_by
               WHERE e.id = ?""",
            (expense_id,),
        )
        return self._row_to_expense(row) if row else None

    def list_expenses(
        self,
        *,
        user_id: int | None = None,
        cash_session_id: int | None = None,
        status: str = "",
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 1000,
    ) -> list[Expense]:
        """Lista gastos con filtros opcionales.

        Si user_id está presente, filtra por solicitante (privacidad empleado).
        """
        clauses = []
        params: list = []

        if user_id is not None:
            clauses.append("e.requested_by = ?")
            params.append(user_id)

        if cash_session_id is not None:
            clauses.append("e.cash_session_id = ?")
            params.append(cash_session_id)

        if status:
            clauses.append("e.status = ?")
            params.append(status)

        if date_from:
            clauses.append("date(e.requested_at) >= date(?)")
            params.append(date_from)

        if date_to:
            clauses.append("date(e.requested_at) <= date(?)")
            params.append(date_to)

        sql = """
            SELECT e.*,
                   ru.full_name AS requested_by_name,
                   au.full_name AS approved_by_name
            FROM expenses e
            JOIN users ru ON ru.id = e.requested_by
            LEFT JOIN users au ON au.id = e.approved_by
        """
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY e.id DESC LIMIT ?"
        params.append(limit)

        rows = self.db.all(sql, tuple(params))
        return [self._row_to_expense(r) for r in rows]

    def count_pending(self, *, cash_session_id: int | None = None) -> int:
        """Cuenta gastos pendientes. Útil antes de cerrar caja."""
        if cash_session_id is not None:
            return int(self.db.scalar(
                """SELECT COUNT(*) FROM expenses
                   WHERE status = ? AND cash_session_id = ?""",
                (ExpenseStatus.PENDING, cash_session_id),
                default=0,
            ) or 0)
        return int(self.db.scalar(
            "SELECT COUNT(*) FROM expenses WHERE status = ?",
            (ExpenseStatus.PENDING,), default=0,
        ) or 0)

    def sum_approved(
        self,
        *,
        cash_session_id: int | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> float:
        """Suma gastos aprobados en un rango."""
        clauses = ["status = ?"]
        params: list = [ExpenseStatus.APPROVED]

        if cash_session_id is not None:
            clauses.append("cash_session_id = ?")
            params.append(cash_session_id)
        if date_from:
            clauses.append("date(requested_at) >= date(?)")
            params.append(date_from)
        if date_to:
            clauses.append("date(requested_at) <= date(?)")
            params.append(date_to)

        sql = f"SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE {' AND '.join(clauses)}"
        return float(self.db.scalar(sql, tuple(params), default=0.0) or 0.0)

    # =========================================================================
    # Helpers
    # =========================================================================
    @staticmethod
    def _row_to_expense(row) -> Expense:
        return Expense(
            id=int(row["id"]),
            cash_session_id=(
                int(row["cash_session_id"]) if row["cash_session_id"] is not None else None
            ),
            description=row["description"],
            amount=float(row["amount"]),
            category=row["category"] or "",
            requested_by=int(row["requested_by"]),
            requested_by_name=row["requested_by_name"],
            requested_at=row["requested_at"],
            status=row["status"],
            approved_by=(
                int(row["approved_by"]) if row["approved_by"] is not None else None
            ),
            approved_by_name=row["approved_by_name"],
            approved_at=row["approved_at"],
            note=row["note"] or "",
        )

    @staticmethod
    def _now() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")