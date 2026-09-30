@echo off
title Crear Tienda Mejia POS
cd /d "%~dp0"

echo ==============================================
echo   TIENDA MEJIA POS - CREAR EJECUTABLE
echo ==============================================
echo.
echo Este proceso se realiza una sola vez.
echo.

python -m pip install --upgrade pyinstaller pillow
if errorlevel 1 (
    echo.
    echo ERROR: No fue posible instalar PyInstaller.
    pause
    exit /b 1
)

python -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --windowed ^
  --name "Tienda Mejia POS" ^
  --icon "assets\tienda_mejia.ico" ^
  --add-data "assets\logo_tienda_mejia.jpg;assets" ^
  main.py

if errorlevel 1 (
    echo.
    echo ERROR: No se pudo crear el ejecutable.
    pause
    exit /b 1
)

copy /Y "dist\Tienda Mejia POS.exe" ".\Tienda Mejia POS.exe" >nul

echo.
echo Ejecutable creado correctamente:
echo %CD%\Tienda Mejia POS.exe
echo.
echo Ahora puedes ejecutar CREAR_ACCESO_ESCRITORIO.vbs
echo para colocar el acceso directo en el escritorio.
pause
