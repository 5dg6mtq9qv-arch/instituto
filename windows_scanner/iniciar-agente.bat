@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo No se encontro Python. Instala Python 3 para Windows y vuelve a intentar.
  pause
  exit /b 1
)
py -3 agent.py
if errorlevel 1 pause
