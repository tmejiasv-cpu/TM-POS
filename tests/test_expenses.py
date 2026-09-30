"""Tests del ExpensesService."""
from __future__ import annotations

import pytest

from vidpos.services.expenses import (
    ExpenseAlreadyProcessedError,
    ExpenseError,
    ExpenseNotFoundError,
    ExpenseStatus,
    ExpensesService,
    PermissionDeniedError,
)


# =============================================================================
# Fixtures
# =============================================================================
@pytest.fixture
def cash_session(db, admin_id):
    cur = db.execute(
        """INSERT INTO cash_sessions(user_id, opened_at, opening_amount, status)
           VALUES(?,?,?,?)""",
        (admin_id, "2026-01-01 08:00:00", 100.0, "OPEN"),
    )
    return int(cur.lastrowid)


@pytest.fixture
def employee_id(db):
    cur = db.execute(
        """INSERT INTO users(full_name, username, password_hash, role, created_at)
           VALUES(?,?,?,?,?)""",
        ("Empleado Test", "empleado", "x$x$x", "employee", "2026-01-01 00:00:00"),
    )
    return int(cur.lastrowid)


@pytest.fixture
def svc(db):
    return ExpensesService(db)


# =============================================================================
# Registro por empleado
# =============================================================================
def test_empleado_registra_gasto_pendiente(svc, employee_id, cash_session):
    eid = svc.register(
        description="Compra de bolsas",
        amount=15.0,
        requested_by=employee_id,
        is_admin=False,
        cash_session_id=cash_session,
    )
    exp = svc.get(eid)
    assert exp is not None
    assert exp.status == ExpenseStatus.PENDING
    assert exp.amount == 15.0
    assert exp.approved_by is None


def test_admin_registra_gasto_aprobado_automaticamente(svc, admin_id, cash_session):
    eid = svc.register(
        description="Gasto de gerencia",
        amount=30.0,
        requested_by=admin_id,
        is_admin=True,
        cash_session_id=cash_session,
    )
    exp = svc.get(eid)
    assert exp.status == ExpenseStatus.APPROVED
    assert exp.approved_by == admin_id
    assert exp.approved_at is not None


def test_rechaza_descripcion_vacia(svc, admin_id):
    with pytest.raises(ExpenseError):
        svc.register(
            description="  ", amount=10.0,
            requested_by=admin_id, is_admin=True,
        )


def test_rechaza_monto_no_positivo(svc, admin_id):
    with pytest.raises(ExpenseError):
        svc.register(
            description="X", amount=0,
            requested_by=admin_id, is_admin=True,
        )
    with pytest.raises(ExpenseError):
        svc.register(
            description="X", amount=-5,
            requested_by=admin_id, is_admin=True,
        )


# =============================================================================
# Aprobación
# =============================================================================
def test_admin_aprueba_gasto_pendiente(svc, admin_id, employee_id, cash_session):
    eid = svc.register(
        description="Compra", amount=20,
        requested_by=employee_id, is_admin=False,
        cash_session_id=cash_session,
    )
    svc.approve(expense_id=eid, approved_by=admin_id, is_admin=True)

    exp = svc.get(eid)
    assert exp.status == ExpenseStatus.APPROVED
    assert exp.approved_by == admin_id


def test_empleado_no_puede_aprobar(svc, employee_id, cash_session):
    eid = svc.register(
        description="X", amount=10,
        requested_by=employee_id, is_admin=False,
        cash_session_id=cash_session,
    )
    with pytest.raises(PermissionDeniedError):
        svc.approve(expense_id=eid, approved_by=employee_id, is_admin=False)


def test_no_aprobar_dos_veces(svc, admin_id, employee_id, cash_session):
    eid = svc.register(
        description="X", amount=10,
        requested_by=employee_id, is_admin=False,
        cash_session_id=cash_session,
    )
    svc.approve(expense_id=eid, approved_by=admin_id, is_admin=True)

    with pytest.raises(ExpenseAlreadyProcessedError):
        svc.approve(expense_id=eid, approved_by=admin_id, is_admin=True)


def test_aprobar_gasto_inexistente(svc, admin_id):
    with pytest.raises(ExpenseNotFoundError):
        svc.approve(expense_id=9999, approved_by=admin_id, is_admin=True)


# =============================================================================
# Rechazo
# =============================================================================
def test_admin_rechaza_gasto(svc, admin_id, employee_id, cash_session):
    eid = svc.register(
        description="Gasto dudoso", amount=100,
        requested_by=employee_id, is_admin=False,
        cash_session_id=cash_session,
    )
    svc.reject(
        expense_id=eid, rejected_by=admin_id, is_admin=True,
        reason="Fuera de política",
    )

    exp = svc.get(eid)
    assert exp.status == ExpenseStatus.REJECTED
    assert "Fuera de política" in exp.note


def test_empleado_no_puede_rechazar(svc, employee_id, cash_session):
    eid = svc.register(
        description="X", amount=10,
        requested_by=employee_id, is_admin=False,
        cash_session_id=cash_session,
    )
    with pytest.raises(PermissionDeniedError):
        svc.reject(
            expense_id=eid, rejected_by=employee_id, is_admin=False,
        )


def test_no_rechazar_gasto_ya_aprobado(svc, admin_id, employee_id, cash_session):
    eid = svc.register(
        description="X", amount=10,
        requested_by=employee_id, is_admin=False,
        cash_session_id=cash_session,
    )
    svc.approve(expense_id=eid, approved_by=admin_id, is_admin=True)
    with pytest.raises(ExpenseAlreadyProcessedError):
        svc.reject(expense_id=eid, rejected_by=admin_id, is_admin=True)


# =============================================================================
# Consultas y filtros
# =============================================================================
def test_listar_gastos_por_usuario(svc, admin_id, employee_id, cash_session):
    svc.register(description="Admin", amount=10,
                 requested_by=admin_id, is_admin=True,
                 cash_session_id=cash_session)
    svc.register(description="Emp", amount=20,
                 requested_by=employee_id, is_admin=False,
                 cash_session_id=cash_session)

    admin_expenses = svc.list_expenses(user_id=admin_id)
    assert len(admin_expenses) == 1
    assert admin_expenses[0].description == "Admin"

    emp_expenses = svc.list_expenses(user_id=employee_id)
    assert len(emp_expenses) == 1
    assert emp_expenses[0].description == "Emp"


def test_listar_por_estado(svc, admin_id, employee_id, cash_session):
    eid1 = svc.register(description="A", amount=10,
                        requested_by=employee_id, is_admin=False,
                        cash_session_id=cash_session)
    eid2 = svc.register(description="B", amount=20,
                        requested_by=employee_id, is_admin=False,
                        cash_session_id=cash_session)
    svc.approve(expense_id=eid2, approved_by=admin_id, is_admin=True)

    pending = svc.list_expenses(status=ExpenseStatus.PENDING)
    assert len(pending) == 1
    assert pending[0].id == eid1

    approved = svc.list_expenses(status=ExpenseStatus.APPROVED)
    assert len(approved) == 1
    assert approved[0].id == eid2


def test_listar_por_sesion_caja(svc, admin_id, db, cash_session):
    # Segunda sesión de caja
    cur = db.execute(
        """INSERT INTO cash_sessions(user_id, opened_at, opening_amount, status)
           VALUES(?,?,?,?)""",
        (admin_id, "2026-01-02 08:00:00", 50.0, "OPEN"),
    )
    other_session = int(cur.lastrowid)

    svc.register(description="S1", amount=10,
                 requested_by=admin_id, is_admin=True,
                 cash_session_id=cash_session)
    svc.register(description="S2", amount=20,
                 requested_by=admin_id, is_admin=True,
                 cash_session_id=other_session)

    s1_expenses = svc.list_expenses(cash_session_id=cash_session)
    assert len(s1_expenses) == 1
    assert s1_expenses[0].description == "S1"


# =============================================================================
# Conteos y sumas
# =============================================================================
def test_count_pending(svc, admin_id, employee_id, cash_session):
    assert svc.count_pending() == 0

    svc.register(description="A", amount=10,
                 requested_by=employee_id, is_admin=False,
                 cash_session_id=cash_session)
    svc.register(description="B", amount=20,
                 requested_by=employee_id, is_admin=False,
                 cash_session_id=cash_session)
    svc.register(description="C", amount=30,
                 requested_by=admin_id, is_admin=True,
                 cash_session_id=cash_session)  # aprobado auto

    assert svc.count_pending() == 2
    assert svc.count_pending(cash_session_id=cash_session) == 2


def test_sum_approved(svc, admin_id, employee_id, cash_session):
    svc.register(description="A", amount=15, requested_by=admin_id,
                 is_admin=True, cash_session_id=cash_session)
    svc.register(description="B", amount=25, requested_by=admin_id,
                 is_admin=True, cash_session_id=cash_session)
    svc.register(description="C", amount=10, requested_by=employee_id,
                 is_admin=False, cash_session_id=cash_session)  # pendiente

    total = svc.sum_approved(cash_session_id=cash_session)
    assert total == 40.0


# =============================================================================
# Integración con CashService
# =============================================================================
def test_gasto_pendiente_bloquea_cierre_caja(db, admin_id, employee_id):
    """Un gasto pendiente impide cerrar la caja."""
    from vidpos.services.cash import CashService, PendingExpensesError

    cash = CashService(db)
    exp_svc = ExpensesService(db)

    sid = cash.open_session(user_id=admin_id, opening_amount=100)
    exp_svc.register(
        description="Pendiente", amount=20,
        requested_by=employee_id, is_admin=False,
        cash_session_id=sid,
    )

    with pytest.raises(PendingExpensesError):
        cash.close_session(
            session_id=sid, user_id=admin_id,
            denominations={"20.00": 5},
        )

    # Al aprobarlo, ya se puede cerrar
    pending = exp_svc.list_expenses(status=ExpenseStatus.PENDING)
    exp_svc.approve(
        expense_id=pending[0].id, approved_by=admin_id, is_admin=True,
    )

    # Después de aprobarlo, el efectivo esperado cambia (baja $20)
    # Cerramos con lo que realmente hay: 100 - 20 = 80
    result = cash.close_session(
        session_id=sid, user_id=admin_id,
        denominations={"20.00": 4},  # 80
    )
    assert result.expected == 80
    assert result.status == "CUADRADA"