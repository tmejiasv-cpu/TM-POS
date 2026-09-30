"""Genera vidpos.ico a partir del isotipo PNG.

Uso:
    python scripts/generar_icono.py

Requiere Pillow.
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("ERROR: se requiere Pillow. Instala con: pip install Pillow")
    sys.exit(1)


ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
SOURCE = ASSETS / "isotipo.png"
TARGET = ASSETS / "vidpos.ico"

# Tamaños estándar para íconos de Windows
SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def main() -> int:
    if not SOURCE.exists():
        print(f"ERROR: no se encontró {SOURCE}")
        print("Coloca el isotipo en assets/isotipo.png")
        return 1

    print(f"Leyendo {SOURCE}...")
    img = Image.open(SOURCE).convert("RGBA")

    # Redimensionar cada tamaño y guardar como .ico multi-resolución
    print(f"Generando {TARGET} con {len(SIZES)} tamaños...")
    img.save(TARGET, format="ICO", sizes=SIZES)

    size_kb = TARGET.stat().st_size / 1024
    print(f"OK · {TARGET.name} creado ({size_kb:.1f} KB)")#Comments
    return 0


if __name__ == "__main__":
    sys.exit(main())