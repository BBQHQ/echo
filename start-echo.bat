@echo off
REM Launch Echo on Windows. Expects a .venv created with: python -m venv .venv
cd /d "%~dp0"
if not exist ".venv\Scripts\activate.bat" (
    echo [Echo] No virtual environment found. Create one with:
    echo        python -m venv .venv ^&^& .venv\Scripts\activate ^&^& pip install -r requirements.txt
    exit /b 1
)
call .venv\Scripts\activate.bat
python -m app.main
