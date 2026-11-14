#!/usr/bin/env bash
# Install / update the add-on into Anki's addons21 folder.
# Re-run this after editing the source. An existing config.json is preserved.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="${HOME}/Library/Application Support/Anki2/addons21/anki_field_exporter"

mkdir -p "${DEST}"

# Code + metadata (not config.json: Anki stores your edited config there).
rsync -a --exclude '__pycache__' \
  "${SRC}/__init__.py" \
  "${SRC}/exporter.py" \
  "${SRC}/settings.py" \
  "${SRC}/manifest.json" \
  "${SRC}/config.md" \
  "${DEST}/"

# Defaults only matter the first time; afterwards the file is yours.
if [ ! -f "${DEST}/config.json" ]; then
  cp "${SRC}/config.json" "${DEST}/config.json"
  echo "Wrote default config.json"
fi

echo "Installed to: ${DEST}"
echo "Restart Anki (or run Tools > Add-ons > Check for Updates / Reload) to pick up changes."
