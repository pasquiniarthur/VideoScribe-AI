@echo off
title VideoScribe AI - Localhost
cd /d "%~dp0"

echo ============================================================
echo   VideoScribe AI - Transcritor de Videos e Audios
echo ============================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Criando ambiente virtual Python...
    python -m venv .venv
    echo [INFO] Instalando dependencias necessarias...
    .\.venv\Scripts\pip install -r requirements.txt
)

echo [INFO] Iniciando aplicacao...
.\.venv\Scripts\python.exe run.py

pause
