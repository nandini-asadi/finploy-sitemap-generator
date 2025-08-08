#!/usr/bin/env bash

#==============================================================================
# Finploy Sitemap Generator - Quick Start Script
#==============================================================================
# Description: Simple script for quick sitemap generation
# Usage: ./quick_start.sh
#==============================================================================

set -euo pipefail

# Colors
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly RED='\033[0;31m'
readonly NC='\033[0m'

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${GREEN}🚀 Finploy Sitemap Generator - Quick Start${NC}"
echo "=============================================="

# Check if virtual environment exists
if [[ ! -d "$SCRIPT_DIR/venv" ]]; then
    echo -e "${YELLOW}⚠️  Virtual environment not found. Setting up...${NC}"
    
    # Create virtual environment
    python3 -m venv "$SCRIPT_DIR/venv"
    
    # Activate and install dependencies
    source "$SCRIPT_DIR/venv/bin/activate"
    pip install -r "$SCRIPT_DIR/requirements.txt"
    playwright install chromium
    
    echo -e "${GREEN}✅ Setup completed!${NC}"
else
    echo -e "${GREEN}✅ Virtual environment found${NC}"
fi

# Run the sitemap generator with default settings
echo -e "${GREEN}🔄 Starting sitemap generation...${NC}"

source "$SCRIPT_DIR/venv/bin/activate"
python3 -m src.sitemap_generator.main \
    --base-urls "https://www.finploy.com,https://finploy.co.uk" \
    --max-depth 5 \
    --max-concurrent 10 \
    --crawl-delay 1.0 \
    --log-level INFO

echo -e "${GREEN}🎉 Quick start completed!${NC}"
echo "Check the 'data/sitemap/' directory for generated files."
