@echo off
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Python was not found on PATH.
    exit /b 1
)

where npm >nul 2>nul
if errorlevel 1 (
    echo Node.js/npm was not found on PATH.
    exit /b 1
)

if not exist ".venv" (
    echo Creating Python virtual environment...
    python -m venv .venv
)

call .venv\Scripts\python.exe -m pip install --upgrade pip
call .venv\Scripts\python.exe -m pip install -r requirements.txt
call npm install
call npm run build

start "NeuroSync Backend" cmd /k ".venv\Scripts\python.exe app.py"
start "NeuroSync Frontend" cmd /k "npm start"

echo Started backend and frontend.
echo Backend: http://localhost:5001
echo Frontend: http://localhost:3000
