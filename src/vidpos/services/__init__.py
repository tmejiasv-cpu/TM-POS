"""Servicios de negocio de vidPOS."""
from vidpos.services.cash import (
    CashAlreadyClosedError,
    CashAlreadyOpenError,
    CashCloseResult,
    CashError,
    CashSession,
    CashSessionNotFoundError,
    CashService,
    CashSummary,
    DEFAULT_DENOMINATIONS,
    PendingExpensesError,
)
from vidpos.services.expenses import (
    DEFAULT_CATEGORIES,
    Expense,
    ExpenseAlreadyProcessedError,
    ExpenseError,
    ExpenseNotFoundError,
    ExpenseStatus,
    ExpensesService,
    PermissionDeniedError,
)
from vidpos.services.inventory import (
    FIFOAllocation,
    FIFOConsumption,
    InsufficientStockError,
    InventoryError,
    InventoryService,
    MovementType,
)
from vidpos.services.inventory import ProductNotFoundError as InventoryProductNotFoundError
from vidpos.services.products import (
    AddonDTO,
    DuplicateError,
    PresentationDTO,
    ProductError,
    ProductNotFoundError,
    ProductService,
    ProductType,
)
from vidpos.services.sales import (
    AddonSelection,
    CartEmptyError,
    CartItem,
    InsufficientPaymentError,
    NoCashSessionError,
    ReturnExceedsSaleError,
    ReturnResult,
    SaleAlreadyVoidedError,
    SaleError,
    SaleHasReturnsError,
    SaleResult,
    SalesService,
)

__all__ = [
    # Cash
    "CashAlreadyClosedError", "CashAlreadyOpenError", "CashCloseResult",
    "CashError", "CashSession", "CashSessionNotFoundError", "CashService",
    "CashSummary", "DEFAULT_DENOMINATIONS", "PendingExpensesError",
    # Expenses
    "DEFAULT_CATEGORIES", "Expense", "ExpenseAlreadyProcessedError",
    "ExpenseError", "ExpenseNotFoundError", "ExpenseStatus", "ExpensesService",
    "PermissionDeniedError",
    # Inventory
    "FIFOAllocation", "FIFOConsumption", "InsufficientStockError",
    "InventoryError", "InventoryService", "MovementType",
    "InventoryProductNotFoundError",
    # Products
    "AddonDTO", "DuplicateError", "PresentationDTO", "ProductError",
    "ProductNotFoundError", "ProductService", "ProductType",
    # Sales
    "AddonSelection", "CartEmptyError", "CartItem", "InsufficientPaymentError",
    "NoCashSessionError", "ReturnExceedsSaleError", "ReturnResult",
    "SaleAlreadyVoidedError", "SaleError", "SaleHasReturnsError",
    "SaleResult", "SalesService",
]