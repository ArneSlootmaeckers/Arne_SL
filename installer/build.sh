#!/usr/bin/env bash
# Bouwt Toelatingssysteem-Setup.exe: een dubbelklik-installer voor Windows.
# Vereist `makensis` (Ubuntu/Debian/Raspberry Pi OS: `sudo apt install nsis`;
# ook beschikbaar via Homebrew op macOS, of nsis.sourceforge.io op Windows
# zelf). Draait op elke ontwikkelmachine (Linux/macOS/Windows) -- de
# uitkomst is een Windows-.exe, ongeacht waar je bouwt.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if ! command -v makensis >/dev/null 2>&1; then
  echo "makensis niet gevonden. Installeer NSIS (bv. 'sudo apt install nsis')." >&2
  exit 1
fi

rm -rf "$SCRIPT_DIR/build"
mkdir -p "$SCRIPT_DIR/build/payload"
git -C "$REPO_ROOT" archive HEAD | tar -x -C "$SCRIPT_DIR/build/payload"

makensis "$SCRIPT_DIR/Toelatingssysteem-Setup.nsi"

echo ""
echo "Klaar: $SCRIPT_DIR/Toelatingssysteem-Setup.exe"
