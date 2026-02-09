#!/bin/bash

# Quick start script for AI Control Mapping Agent backend
# Assumes dependencies are already installed

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

# Navigate to backend directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Activate virtual environment
source "$SCRIPT_DIR/venv/bin/activate"

echo -e "${BLUE}Starting AI Control Mapping Agent Backend...${NC}\n"
echo -e "${GREEN}Available at:${NC}"
echo -e "  • API: ${BLUE}http://localhost:8000${NC}"
echo -e "  • Swagger UI: ${BLUE}http://localhost:8000/docs${NC}"
echo -e "  • Health Check: ${BLUE}http://localhost:8000/api/v1/health${NC}\n"

# Start server
uvicorn app.main:app --reload --host localhost --port 8000
