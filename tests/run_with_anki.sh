#!/usr/bin/env bash
# Run the integration tests against a real (temporary) Anki collection
# and the GUI wiring tests headlessly.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Find Anki's bundled Python (it ships with the .so modules the tests need).
CANDIDATES=(
  "/Applications/Anki.app/Contents/Frameworks/Python.framework/Versions/3.13/bin/python3"
)
if [ -n "${ANKI_PYTHON:-}" ]; then
  CANDIDATES=("${ANKI_PYTHON}" "${CANDIDATES[@]}")
fi
for candidate in $(ls -d /Applications/Anki.app/Contents/Frameworks/Python.framework/Versions/*/bin/python3 2>/dev/null); do
  CANDIDATES+=("${candidate}")
done

for candidate in "${CANDIDATES[@]}"; do
  if [ -x "${candidate}" ]; then
    "${candidate}" "${HERE}/test_with_anki.py"
    "${candidate}" "${HERE}/test_gui_wiring.py"
    exec "${candidate}" "${HERE}/test_settings_dialog.py"
  fi
done

echo "Anki's bundled Python was not found. Set ANKI_PYTHON to its path." >&2
exit 1
