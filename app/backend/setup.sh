#!/bin/bash

# AI Control Mapping Agent - Backend Setup Script
# This script sets up the development environment and starts the server

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}AI Control Mapping Agent - Backend Setup${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Get the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if virtual environment exists
VENV_PATH="$SCRIPT_DIR/../.venv"

if [ ! -d "$VENV_PATH" ]; then
    echo -e "${YELLOW}⚠ Virtual environment not found. Creating...${NC}"
    python3 -m venv "$VENV_PATH"
fi

echo -e "${GREEN}✓ Found virtual environment${NC}"

# Activate virtual environment
echo -e "${BLUE}→ Activating virtual environment...${NC}"
source "$VENV_PATH/bin/activate"

# Verify Python version
PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
echo -e "${GREEN}✓ Using Python $PYTHON_VERSION${NC}"

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠ .env file not found. Creating from template...${NC}"
    if [ -f ".env.template" ]; then
        cp .env.template .env
        echo -e "${GREEN}✓ Created .env file${NC}"
        echo -e "${YELLOW}⚠ Please edit .env with your Azure OpenAI details before starting the server${NC}"
        echo -e "${YELLOW}  Required: AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_DEPLOYMENT_NAME${NC}\n"
    else
        echo -e "${RED}❌ .env.template not found${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✓ .env file exists${NC}"
fi

# Install/upgrade pip
echo -e "${BLUE}→ Upgrading pip...${NC}"
pip install --upgrade pip --quiet

# Install dependencies
echo -e "${BLUE}→ Installing dependencies from requirements.txt...${NC}"
echo -e "${YELLOW}  (This may take a few minutes on first run)${NC}"
pip install -r requirements.txt

echo -e "${GREEN}✓ Dependencies installed successfully${NC}\n"

# Check Azure CLI authentication
echo -e "${BLUE}→ Checking Azure CLI authentication...${NC}"
if command -v az &> /dev/null; then
    if az account show &> /dev/null; then
        ACCOUNT_NAME=$(az account show --query name -o tsv)
        echo -e "${GREEN}✓ Authenticated with Azure CLI${NC}"
        echo -e "  Account: ${ACCOUNT_NAME}"
    else
        echo -e "${YELLOW}⚠ Not authenticated with Azure CLI${NC}"
        echo -e "${YELLOW}  Run 'az login' to authenticate for DefaultAzureCredential${NC}"
    fi
else
    echo -e "${YELLOW}⚠ Azure CLI not found${NC}"
    echo -e "${YELLOW}  Install from: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli${NC}"
fi

echo -e "\n${BLUE}========================================${NC}"
echo -e "${GREEN}✓ Setup complete!${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Ask if user wants to start the server
read -p "Start the FastAPI server now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${BLUE}→ Starting FastAPI server...${NC}\n"
    echo -e "${GREEN}Server will be available at:${NC}"
    echo -e "  • API: ${BLUE}http://localhost:8000${NC}"
    echo -e "  • Swagger UI: ${BLUE}http://localhost:8000/docs${NC}"
    echo -e "  • ReDoc: ${BLUE}http://localhost:8000/redoc${NC}"
    echo -e "  • Health Check: ${BLUE}http://localhost:8000/api/v1/health${NC}\n"
    echo -e "${YELLOW}Press Ctrl+C to stop the server${NC}\n"

    uvicorn app.main:app --reload --host localhost --port 8000
else
    echo -e "${YELLOW}To start the server later, run:${NC}"
    echo -e "  cd $SCRIPT_DIR"
    echo -e "  source $VENV_PATH/bin/activate"
    echo -e "  uvicorn app.main:app --reload --host localhost --port 8000"
fi
