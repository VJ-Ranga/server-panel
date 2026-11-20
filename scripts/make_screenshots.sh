#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
chrome="${CHROME_BIN:-google-chrome}"
command -v "$chrome" >/dev/null
workdir="$(mktemp -d)"
demo_pid=
cleanup() {
  if [[ -n "$demo_pid" ]]; then
    kill "$demo_pid" 2>/dev/null || true
    wait "$demo_pid" 2>/dev/null || true
  fi
  rm -rf -- "$workdir"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

python3 scripts/demo_server.py --port 0 >"$workdir/url" 2>"$workdir/demo.log" &
demo_pid=$!
for ((attempt = 0; attempt < 100; attempt++)); do
  if [[ -s "$workdir/url" ]]; then break; fi
  if ! kill -0 "$demo_pid" 2>/dev/null; then break; fi
  sleep 0.05
done
if ! read -r demo_url <"$workdir/url" || [[ ! "$demo_url" =~ ^http://127\.0\.0\.1:[0-9]+$ ]]; then
  cat "$workdir/demo.log" >&2
  echo "Demo server did not start." >&2
  exit 1
fi

capture() {
  local file="$1" size="$2" theme="$3" page="$4"
  if ! "$chrome" --headless=new --disable-gpu --hide-scrollbars --no-proxy-server \
    --no-first-run --no-default-browser-check --force-device-scale-factor=1 \
    --user-data-dir="$workdir/${file%.png}" --window-size="$size" \
    --virtual-time-budget=5000 --timeout=30000 --screenshot="$workdir/$file" \
    "$demo_url/?theme=$theme#$page" >"$workdir/chrome.log" 2>&1; then
    cat "$workdir/chrome.log" >&2
    return 1
  fi
}

capture dashboard-light.png 1440,900 light dashboard
capture dashboard-dark.png 1440,900 dark dashboard
capture apps-light.png 1440,900 light apps
capture wordpress-light.png 1440,900 light wordpress
capture nginx-dark.png 1440,900 dark nginx
capture mobile-dashboard-light.png 390,844 light dashboard

python3 - "$workdir" <<'PY'
from pathlib import Path
import struct
import sys

for image in Path(sys.argv[1]).glob("*.png"):
    with image.open("rb") as png:
        header = png.read(24)
    expected = (390, 844) if image.name.startswith("mobile-") else (1440, 900)
    if (
        len(header) != 24
        or header[:8] != b"\x89PNG\r\n\x1a\n"
        or struct.unpack(">II", header[16:]) != expected
        or image.stat().st_size <= 20_000
    ):
        raise SystemExit(f"Unexpected dimensions or size for {image.name}")
PY

mkdir -p docs/screenshots
cp -- "$workdir/"*.png docs/screenshots/
