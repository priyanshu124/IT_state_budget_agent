#!/bin/bash
# ============================================
# TBM Classification Engine - Setup Script
# ============================================
# Run this once to initialize the project:
#   chmod +x setup.sh && ./setup.sh

set -e

echo "=========================================="
echo "  TBM Classification Engine - Setup"
echo "=========================================="

# 1. Create virtual environment
echo "[1/4] Creating Python virtual environment..."
python3 -m venv .venv
source .venv/bin/activate

# 2. Upgrade pip
echo "[2/4] Upgrading pip..."
pip install --upgrade pip

# 3. Install dependencies
echo "[3/4] Installing dependencies..."
pip install -r requirements.txt

# 4. Setup .env if not exists
echo "[4/4] Setting up environment..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "  -> Created .env from template"
    echo "  -> IMPORTANT: Edit .env and add your ANTHROPIC_API_KEY"
else
    echo "  -> .env already exists, skipping"
fi

echo ""
echo "=========================================="
echo "  Setup complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Activate env:    source .venv/bin/activate"
echo "  2. Add API key:     Edit .env with your ANTHROPIC_API_KEY"
echo "  3. Add data:        Place CSV/Excel files in data/raw/"
echo "  4. Profile data:    python -m src.pipeline.profiler"
echo ""
