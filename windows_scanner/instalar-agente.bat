@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar-agente.ps1"
if errorlevel 1 (
  echo.
  echo La instalacion no se completo. Revisa el mensaje anterior.
  pause
)
