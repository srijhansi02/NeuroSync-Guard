@echo off
cd /d "%~dp0"
echo Building frontend...
call npm run build
start "NeuroSync Backend" cmd /k python app.py
start "NeuroSync Frontend" cmd /k node server.js
echo Started backend and frontend.
echo Backend: http://localhost:5001
echo Frontend: http://localhost:3000
