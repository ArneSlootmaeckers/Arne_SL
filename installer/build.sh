#!/usr/bin/env bash
# Bouwt Toelatingssysteem-Setup.exe: een dubbelklik-installer voor Windows.
# Vereist `makensis` (Ubuntu/Debian/Raspberry Pi OS: `sudo apt install nsis`;
# ook beschikbaar via Homebrew op macOS, of nsis.sourceforge.io op Windows
# zelf), `curl` en `unzip`. Draait op elke ontwikkelmachine
# (Linux/macOS/Windows) -- de uitkomst is een Windows-.exe, ongeacht waar je
# bouwt.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# De installer brengt zijn eigen Python mee: het officiële Windows-pakket van
# de Python Software Foundation op nuget.org (een volledige Python, met pip
# en venv, zonder installatieprogramma). Zo hoeft er op de pc vooraf niets
# geïnstalleerd te zijn. De SHA-256 legt vast welk bestand precies: een
# ander (of aangepast) bestand wordt geweigerd.
PYTHON_VERSION="3.13.17"
PYTHON_SHA256="dce409744b088f94c6e37ba41f8100c384c27e029e843237364c602d30d475e5"
PYTHON_URL="https://api.nuget.org/v3-flatcontainer/python/$PYTHON_VERSION/python.$PYTHON_VERSION.nupkg"
PYTHON_PACKAGE="$SCRIPT_DIR/cache/python.$PYTHON_VERSION.nupkg"

for tool in makensis curl unzip; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "$tool niet gevonden. Installeer het eerst (makensis: bv. 'sudo apt install nsis')." >&2
    exit 1
  fi
done

sha256_of() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | cut -d' ' -f1
  else
    shasum -a 256 "$1" | cut -d' ' -f1
  fi
}

# In cache/ (niet in git) zodat niet elke bouw opnieuw ~15 MB downloadt.
if [ ! -f "$PYTHON_PACKAGE" ]; then
  mkdir -p "$SCRIPT_DIR/cache"
  echo "Python $PYTHON_VERSION downloaden..."
  curl -fsSL -o "$PYTHON_PACKAGE.part" "$PYTHON_URL"
  mv "$PYTHON_PACKAGE.part" "$PYTHON_PACKAGE"
fi
if [ "$(sha256_of "$PYTHON_PACKAGE")" != "$PYTHON_SHA256" ]; then
  echo "Python-pakket heeft niet de verwachte SHA-256; verwijderd. Bouw opnieuw." >&2
  rm -f "$PYTHON_PACKAGE"
  exit 1
fi

rm -rf "$SCRIPT_DIR/build"
mkdir -p "$SCRIPT_DIR/build/payload" "$SCRIPT_DIR/build/nupkg"
git -C "$REPO_ROOT" archive HEAD | tar -x -C "$SCRIPT_DIR/build/payload"
unzip -q "$PYTHON_PACKAGE" "tools/*" -d "$SCRIPT_DIR/build/nupkg"
mv "$SCRIPT_DIR/build/nupkg/tools" "$SCRIPT_DIR/build/python"

makensis "$SCRIPT_DIR/Toelatingssysteem-Setup.nsi"

echo ""
echo "Klaar: $SCRIPT_DIR/Toelatingssysteem-Setup.exe"
