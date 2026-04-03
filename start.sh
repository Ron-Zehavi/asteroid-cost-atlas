#!/bin/bash
# Start Asteroid Cost Atlas — backend + frontend, open browser
set -e
cd "$(dirname "$0")"

# Ensure Python 3.11+ venv exists
VENV=".venv"
if [ ! -d "$VENV" ]; then
  echo "Creating Python venv..."
  python3.11 -m venv "$VENV"
fi

# Always ensure deps are current
echo "Installing Python deps..."
"$VENV/bin/pip" install -e ".[web]" --quiet 2>/dev/null

# Ensure frontend deps installed
if [ ! -d "web/node_modules" ]; then
  echo "Installing frontend deps..."
  (cd web && npm install --silent)
fi

# Kill any existing servers
pkill -f "uvicorn asteroid_cost_atlas" 2>/dev/null || true
pkill -f "node.*vite" 2>/dev/null || true
sleep 1

# Start backend
echo "Starting API on :8000..."
"$VENV/bin/uvicorn" asteroid_cost_atlas.api.app:app --port 8000 &
BACKEND_PID=$!

# Wait for backend to be ready
echo "Waiting for API..."
for i in $(seq 1 30); do
  if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
    echo "API ready."
    break
  fi
  sleep 1
done

# Start frontend and open browser
echo "Starting frontend on :5173..."
(cd web && npx vite --open) &
FRONTEND_PID=$!

echo ""
echo "  Asteroid Cost Atlas running at http://localhost:5173"
echo "  Press Ctrl+C to stop"
echo ""

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
