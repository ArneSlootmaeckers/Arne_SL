#!/usr/bin/env bash
# Installatiescript zonder Docker: zet een Python virtualenv op in backend/.venv
# en installeert de dependencies. Zie README.md voor het volledige overzicht.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"

cd "$BACKEND_DIR"

if [ ! -d ".venv" ]; then
  echo "Virtualenv aanmaken in backend/.venv..."
  python3 -m venv .venv
fi

# shellcheck source=/dev/null
source .venv/bin/activate
pip install --upgrade pip --quiet
pip install -r requirements.txt

mkdir -p "$SCRIPT_DIR/data"

echo ""
echo "Installatie klaar."
echo "  Server starten:        ./start.sh"
echo "  Eerste admin aanmaken:  cd backend && source .venv/bin/activate && python3 create_admin.py"
echo "  Demo-gegevens seeden:   cd backend && source .venv/bin/activate && python3 seed.py"
