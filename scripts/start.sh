#!/bin/bash
# CHEMI - Chemistry Chatbot Startup Script
# Runs both FastAPI backend and Gradio frontend in single container

set -e

echo "Starting CHEMI Chemistry Chatbot..."

# Start FastAPI backend on port 8000 (background)
echo "Starting FastAPI backend on port 8000..."
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Wait for backend to be ready
echo "Waiting for backend to start..."
sleep 3

# Check if backend started successfully
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo "ERROR: Backend failed to start"
    exit 1
fi

echo "Backend started successfully (PID: $BACKEND_PID)"

# Start Gradio frontend on port 7860 (foreground)
echo "Starting Gradio frontend on port 7860..."
uv run python gradio/app.py &
FRONTEND_PID=$!

echo "Frontend started (PID: $FRONTEND_PID)"
echo "CHEMI is ready!"
echo "  - Backend:  http://localhost:8000"
echo "  - Frontend: http://localhost:7860"

# Handle shutdown gracefully
cleanup() {
    echo "Shutting down CHEMI..."
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    exit 0
}

trap cleanup SIGTERM SIGINT

# Wait for any process to exit
wait -n

# If we get here, one process died - exit with error
echo "A process exited unexpectedly"
cleanup
exit 1
