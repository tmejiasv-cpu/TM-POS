# vidPOS

> Punto de venta profesional para tiendas pequeñas y medianas.
> **Vende fácil, controla todo.**

## Características

- Punto de venta rápido con lector de código de barras
- Inventario por lotes con costo real FIFO/PEPS
- Caja con apertura, cierre y arqueo por denominaciones
- Devoluciones y anulaciones auditadas
- Gastos con aprobación de gerencia
- Reportes gerenciales: flujo de caja y estado de resultados
- Historial de actividad por empleado
- Respaldos automáticos
- Funciona sin internet
- Base de datos local (SQLite)

## Instalación (desarrollo)

Requiere **Python 3.11+**.

```bash
git clone <repo>
cd vidpos
python -m venv .venv
.venv\Scripts\activate         # Windows
# source .venv/bin/activate    # Linux/macOS
pip install -e ".[dev]"