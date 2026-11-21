#!/bin/bash
set -euo pipefail

if (( EUID == 0 )); then
  echo "Run this script as your normal user, without sudo." >&2
  exit 1
fi

usage() {
  echo "Usage: $0 on [--force] | off [--yes] [--remove-clients] | status" >&2
  exit 1
}

action="${1:-}"
case "$action" in on|off|status) shift ;; *) usage ;; esac
force=false
assume_yes=false
remove_clients=false
for arg in "$@"; do
  case "$action:$arg" in
    on:--force) force=true ;;
    off:--yes|off:-y) assume_yes=true ;;
    off:--remove-clients) remove_clients=true ;;
    *) usage ;;
  esac
done

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BRIDGE="$REPO_DIR/mcp/server_panel_mcp.py"

registration_status() {
  local output
  # Client output can contain legacy environment credentials.
  if output="$("$1" mcp get server-panel 2>&1)"; then
    echo registered
  else
    case "$output" in
      *"No MCP server found with name: server-panel"*|*'No MCP server found with name: "server-panel"'*|*"No MCP server named 'server-panel' found"*)
        echo missing ;;
      *) echo unknown ;;
    esac
  fi
}

remove_registration() {
  if "$1" mcp remove server-panel >/dev/null 2>&1; then
    echo "$1: removed server-panel."
  else
    echo "$1: could not remove server-panel." >&2
    return 1
  fi
}

register_client() {
  local client="$1" status
  status="$(registration_status "$client")"
  case "$status" in
    registered)
      if ! "$force"; then
        echo "$client: server-panel is already registered."
        return
      fi
      remove_registration "$client" || return 0
      ;;
    unknown)
      echo "$client: could not check registration. Existing entries were kept." >&2
      return
      ;;
  esac
  local scope=()
  if [[ "$client" == claude ]]; then scope=(-s user); fi
  if "$client" mcp add server-panel "${scope[@]}" -- python3 "$BRIDGE" >/dev/null 2>&1; then
    echo "$client: registered server-panel."
  else
    echo "$client: could not register server-panel. See mcp/README.md for manual setup." >&2
  fi
}

case "$action" in
  on)
    python3 "$REPO_DIR/panel.py" --mcp-key on
    for client in claude codex; do
      if command -v "$client" >/dev/null 2>&1; then
        register_client "$client"
      else
        echo "$client: CLI unavailable. See mcp/README.md for manual setup."
      fi
    done
    if command -v opencode >/dev/null 2>&1 || [[ -d "$HOME/.config/opencode" ]]; then
      echo "OpenCode: merge this entry into opencode.json."
      python3 - "$BRIDGE" <<'PY'
import json
import sys

print(json.dumps({"mcp": {"server-panel": {
    "type": "local",
    "command": ["python3", sys.argv[1]],
    "enabled": True,
}}}, indent=2))
PY
    fi
    echo "MCP key access is on. Restart your AI tool to load the registration."
    ;;
  off)
    python3 "$REPO_DIR/panel.py" --mcp-key off
    echo "MCP key access is off. Registrations using a password environment variable keep working until removed."
    if ! "$assume_yes" && ! "$remove_clients"; then
      printf 'Also remove the server-panel entry from Claude Code / Codex? [y/N] '
      read -r answer || answer=""
      if [[ "$answer" == [yY] || "$answer" == [yY][eE][sS] ]]; then
        remove_clients=true
      fi
    fi
    if "$remove_clients"; then
      for client in claude codex; do
        if command -v "$client" >/dev/null 2>&1; then
          case "$(registration_status "$client")" in
            registered) remove_registration "$client" || true ;;
            missing) echo "$client: server-panel is not registered." ;;
            unknown) echo "$client: could not check registration." >&2 ;;
          esac
        fi
      done
    fi
    ;;
  status)
    key_status="$(python3 "$REPO_DIR/panel.py" --mcp-key status)"
    printf 'MCP key: %s\n' "$key_status"
    for client in claude codex; do
      if command -v "$client" >/dev/null 2>&1; then
        case "$(registration_status "$client")" in
          registered) echo "$client: server-panel is registered." ;;
          missing) echo "$client: server-panel is not registered." ;;
          unknown) echo "$client: could not check registration." >&2 ;;
        esac
      fi
    done
    ;;
esac
