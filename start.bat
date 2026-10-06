@echo off
REM Starts backend (:8000) and frontend (:5173). Install dependencies first (see README).
start "Backend" cmd /k "cd /d %~dp0backend && python -m uvicorn app.main:app --reload --port 8000"
start "Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"
