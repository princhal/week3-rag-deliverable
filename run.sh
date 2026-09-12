#!/usr/bin/env bash
set -e

# ── Kill any processes already using our ports ──────────────────────────────
echo "🧹 Cleaning up any existing servers on ports 8000 & 3000..."
lsof -ti :8000 | xargs kill -9 2>/dev/null || true
lsof -ti :3000 | xargs kill -9 2>/dev/null || true
sleep 1

# ── Backend ──────────────────────────────────────────────────────────────────
echo ""
echo "📦 Installing backend dependencies..."
pip3 install -r backend/requirements.txt -q

echo ""
echo "🚀 Starting FastAPI backend  →  http://localhost:8000"
python3 -m uvicorn backend.main:app --reload --port 8000 &
BACKEND_PID=$!

# ── Frontend ─────────────────────────────────────────────────────────────────
echo "🌐 Starting Next.js frontend  →  http://localhost:3000"
cd frontend && npm run dev &
FRONTEND_PID=$!

echo ""
echo "✅ Both servers are running!"
echo "   Frontend UI  →  http://localhost:3000"
echo "   API Docs     →  http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop."

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo 'Stopped.'" EXIT
wait
