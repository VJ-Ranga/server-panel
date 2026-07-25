#!/bin/bash
PANEL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT=8765

# Kill any existing instance
kill $(lsof -ti:$PORT) 2>/dev/null
sleep 0.5

# Open terminal with panel running
x-terminal-emulator --title="Server Panel" -e bash -c "
  cd '$PANEL_DIR'
  echo '╔══════════════════════════════════════╗'
  echo '║   Server Management Panel            ║'
  echo '║   http://127.0.0.1:$PORT             ║'
  echo '╚══════════════════════════════════════╝'
  python3 panel.py
  echo ''
  echo 'Panel stopped. Press Enter to close.'
  read
" &

# Wait for panel to start then open browser
sleep 1.5
xdg-open "http://127.0.0.1:$PORT" 2>/dev/null &
