#!/bin/zsh
# ============================================================
# run.sh — RAG pipeline launcher
# Usage:
#   ./run.sh                        # full pipeline
#   ./run.sh --stage extract        # single stage
#   ./run.sh --from-stage query     # resume from a stage
# ============================================================

export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"

cd "$(dirname "$0")"

# Check PDF exists
if [ ! -f "data/source.pdf" ]; then
    echo "ERROR: data/source.pdf not found."
    echo "Drop your PDF at: $(pwd)/data/source.pdf"
    exit 1
fi

# Check .env exists
if [ ! -f ".env" ]; then
    echo "ERROR: .env not found. Copy .env.example to .env and fill in your keys."
    exit 1
fi

echo "Starting RAG pipeline..."
python main.py --pdf data/source.pdf "$@"
