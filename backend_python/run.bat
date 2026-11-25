@echo off
title PulseTask FastAPI Backend
cd /d %~dp0
echo ========================================================
echo    PulseTask Python FastAPI Server (Neon PostgreSQL)
echo ========================================================
echo  Web Application UI: http://localhost:8000
echo  Swagger API Docs:   http://localhost:8000/docs
echo  Alternative Docs:   http://localhost:8000/redoc
echo ========================================================
echo.
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
pause
