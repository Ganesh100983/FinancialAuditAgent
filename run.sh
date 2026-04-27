#!/usr/bin/env bash
set -e

echo "============================================================"
echo "  Financial Audit AI - Starting Application (React + FastAPI)"
echo "============================================================"
echo

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "[ERROR] UV package manager not found."
    echo "Install it with:"
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Check if npm is installed
if ! command -v npm &> /dev/null; then
    echo "[ERROR] Node.js / npm not found."
    echo "Install Node.js from https://nodejs.org/"
    exit 1
fi

# Create .env if it doesn't exist
if [ ! -f .env ] && [ -f .env.example ]; then
    cp .env.example .env
    echo "[INFO] Created .env from .env.example"
    echo "       Please add your OPENAI_API_KEY to .env"
    echo
fi

# Sync Python dependencies
echo "[1/4] Installing Python dependencies with UV..."
uv sync

# Activate virtual environment
VENV_DIR=".venv"
if [ -f "$VENV_DIR/bin/activate" ]; then
    echo "[2/4] Activating virtual environment ($VENV_DIR)..."
    source "$VENV_DIR/bin/activate"
    echo "      Python: $(python --version)"
    echo "      Venv:   $VIRTUAL_ENV"
elif [ -f "$VENV_DIR/Scripts/activate" ]; then
    # Git Bash / MSYS2 on Windows
    echo "[2/4] Activating virtual environment ($VENV_DIR)..."
    source "$VENV_DIR/Scripts/activate"
    echo "      Python: $(python --version)"
else
    echo "[WARN] Virtual environment not found at $VENV_DIR"
fi

# Install frontend dependencies
echo
echo "[3/4] Installing frontend dependencies..."
cd frontend
npm install --silent
cd ..

echo
echo "[4/4] Launching servers..."
echo
echo "  Backend  API  -> http://localhost:8000/api/v1"
echo "  Frontend UI   -> http://localhost:5173"
echo
echo "  Open http://localhost:5173 in your browser"
echo "  Press Ctrl+C to stop both servers"
echo

# Start FastAPI backend in background
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# Trap Ctrl+C to kill both servers
trap "echo; echo 'Stopping servers...'; kill $BACKEND_PID 2>/dev/null; exit 0" INT TERM

# Start Vite dev server in foreground
cd frontend
npm run dev

# Wait for backend if Vite exits
wait $BACKEND_PID
