@echo off
echo ============================================================
echo   Financial Audit AI - Starting Application (React + FastAPI)
echo ============================================================
echo.

:: Check if uv is installed
where uv >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] UV package manager not found.
    echo Please install it: https://docs.astral.sh/uv/getting-started/installation/
    echo   Windows: powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    pause
    exit /b 1
)

:: Check if node/npm is installed
where npm >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Node.js / npm not found.
    echo Please install Node.js from https://nodejs.org/
    pause
    exit /b 1
)

:: Copy .env if it doesn't exist
if not exist .env (
    if exist .env.example (
        copy .env.example .env
        echo [INFO] Created .env from .env.example - please add your OPENAI_API_KEY
        echo.
    )
)

:: Sync Python dependencies
echo [1/4] Installing Python dependencies with UV...
uv sync
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install Python dependencies.
    pause
    exit /b 1
)

:: Activate virtual environment
echo.
set VENV_ACTIVATE=.venv\Scripts\activate.bat
if exist %VENV_ACTIVATE% (
    echo [2/4] Activating virtual environment ^(.venv^)...
    call %VENV_ACTIVATE%
    echo       Python: & python --version
) else (
    echo [WARN] Virtual environment not found at .venv
)

:: Install frontend dependencies
echo.
echo [3/4] Installing frontend dependencies...
cd frontend
call npm install --silent
cd ..

:: Launch both servers
echo.
echo [4/4] Launching servers...
echo.
echo   Backend  API  -> http://localhost:8000/api/v1
echo   Frontend UI   -> http://localhost:5173
echo.
echo   (Open http://localhost:5173 in your browser)
echo   Press Ctrl+C to stop
echo.

:: Start FastAPI backend in background
start "FinAudit-Backend" cmd /k "call .venv\Scripts\activate.bat && uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"

:: Start Vite dev server in foreground
cd frontend
npm run dev

:end
pause
