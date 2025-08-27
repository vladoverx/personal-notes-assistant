#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to cleanup background processes on exit
cleanup() {
    echo -e "\n${YELLOW}Shutting down services...${NC}"
    if [ ! -z "$BACKEND_PID" ]; then
        echo -e "${BLUE}Stopping backend (PID: $BACKEND_PID)${NC}"
        kill $BACKEND_PID 2>/dev/null
    fi
    if [ ! -z "$FRONTEND_PID" ]; then
        echo -e "${BLUE}Stopping frontend (PID: $FRONTEND_PID)${NC}"
        kill $FRONTEND_PID 2>/dev/null
    fi
    echo -e "${GREEN}All services stopped.${NC}"
    exit 0
}

# Set up signal handlers for cleanup
trap cleanup SIGINT SIGTERM

echo -e "${GREEN}Starting Personal Notes Assistant (FastAPI + Frontend)...${NC}"

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo -e "${RED}Error: uv is not installed. Please install uv first.${NC}"
    exit 1
fi

free_port() {
    local port="$1"
    if ss -ltn "sport = :$port" | grep -q ":$port\b"; then
        echo -e "${YELLOW}Port $port is in use; freeing it...${NC}"
        fuser -k ${port}/tcp 2>/dev/null || true
        # Give the OS a moment to release the port
        sleep 0.5
    fi
}

# Frontend will be served as static files via Python's http.server using uv

# Start backend (FastAPI via uvicorn, managed by uv)
echo -e "${BLUE}Starting backend server...${NC}"
cd backend
free_port 8000
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload &
BACKEND_PID=$!
cd ..

# Wait a moment for backend to start
sleep 2

# Check if backend started successfully
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo -e "${RED}Error: Backend failed to start${NC}"
    exit 1
fi

echo -e "${GREEN}Backend started successfully (PID: $BACKEND_PID)${NC}"
echo -e "${BLUE}Backend running on: http://localhost:8000${NC}"

# Start frontend
echo -e "${BLUE}Starting frontend server (static)...${NC}"
FRONTEND_PORT=3000
cd frontend
free_port ${FRONTEND_PORT}
uv run python -m http.server ${FRONTEND_PORT} --bind 127.0.0.1 &
FRONTEND_PID=$!
cd ..

# Wait a moment for frontend to start
sleep 1

# Check if frontend started successfully
if ! kill -0 $FRONTEND_PID 2>/dev/null; then
    echo -e "${RED}Error: Frontend failed to start${NC}"
    cleanup
    exit 1
fi

echo -e "${GREEN}Frontend started successfully (PID: $FRONTEND_PID)${NC}"
echo -e "${BLUE}Frontend running on: http://localhost:${FRONTEND_PORT}${NC}"

echo -e "\n${GREEN}🎉 Personal Notes Assistant is running!${NC}"
echo -e "${YELLOW}Frontend: http://localhost:${FRONTEND_PORT}${NC}"
echo -e "${YELLOW}Backend API: http://localhost:8000${NC}"
echo -e "\n${BLUE}Press Ctrl+C to stop all services${NC}"

# Wait for user to stop the services
wait
