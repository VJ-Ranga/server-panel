#!/bin/bash
set -euo pipefail

if (( EUID == 0 )); then
  echo "Run this installer as your normal user, without sudo."
  exit 1
fi

INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_PATH="${SERVER_PANEL_CONFIG:-$INSTALL_DIR/panel_config.json}"
ASSUME_YES=false
for arg in "$@"; do
  case "$arg" in
    --yes|-y) ASSUME_YES=true ;;
    *) echo "Usage: $0 [--yes|-y]"; exit 1 ;;
  esac
done

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3.8 or newer is required. Install it with: sudo apt install python3"
  exit 1
fi
if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)'; then
  echo "Python 3.8 or newer is required. Please upgrade python3 and try again."
  exit 1
fi

ask() {
  local prompt="$1" default="$2" answer
  if "$ASSUME_YES"; then
    [[ "$default" == y ]]
    return
  fi
  read -r -p "$prompt " answer || answer=""
  answer="${answer:-$default}"
  [[ "$answer" == [yY] || "$answer" == [yY][eE][sS] ]]
}

package_found() {
  command -v dpkg-query >/dev/null 2>&1 &&
    dpkg-query -W -f='${db:Status-Status}\n' "$1" 2>/dev/null | grep -qx installed
}

report() {
  local name="$1" found="$2" hint="$3"
  if [[ "$found" == true ]]; then
    printf '  %s: found\n' "$name"
  else
    printf '  %s: not found\n    %s\n' "$name" "$hint"
  fi
}

echo "CloudyCode Server Panel installer"
echo "Checking optional tools (no packages will be installed):"
found=false
if command -v nginx >/dev/null 2>&1 || package_found nginx; then found=true; fi
report nginx "$found" 'Install with: sudo apt install nginx'
found=false
if command -v mysql >/dev/null 2>&1 || command -v mariadb >/dev/null 2>&1 ||
   package_found mysql-server || package_found mariadb-server; then found=true; fi
report 'mysql/mariadb' "$found" 'Install with: sudo apt install mariadb-server'
found=false
if compgen -G '/usr/sbin/php*-fpm' >/dev/null || package_found 'php*-fpm'; then found=true; fi
report php-fpm "$found" 'Install with: sudo apt install php-fpm'
found=false
if [[ -d /usr/share/phpmyadmin ]] || package_found phpmyadmin; then found=true; fi
report phpmyadmin "$found" 'Install with: sudo apt install phpmyadmin'
found=false
if command -v composer >/dev/null 2>&1; then found=true; fi
report composer "$found" 'Install with: sudo apt install composer'
found=false
if command -v wp >/dev/null 2>&1; then found=true; fi
report wp-cli "$found" 'Try: sudo apt install wp-cli (if available in your apt repositories; otherwise use the official WP-CLI installer)'

change_login=true
if [[ -f "$CONFIG_PATH" ]] && ask 'Keep current panel login? [Y/n]' y; then
  change_login=false
fi
if "$change_login"; then
  admin_username=admin
  admin_password=admin
  if ! "$ASSUME_YES"; then
    read -r -p 'Admin username [admin]: ' admin_username
    admin_username="${admin_username:-admin}"
    while true; do
      read -r -s -p 'Admin password [admin]: ' admin_password
      printf '\n'
      read -r -s -p 'Confirm admin password [admin]: ' confirm_password
      printf '\n'
      admin_password="${admin_password:-admin}"
      confirm_password="${confirm_password:-admin}"
      if [[ "$admin_password" == "$confirm_password" ]]; then break; fi
      echo "Passwords do not match. Please try again."
    done
  fi
  # printf is a Bash builtin: the password travels only through stdin, never argv.
  printf '%s\n%s\n' "$admin_username" "$admin_password" | python3 "$INSTALL_DIR/panel.py" --set-login
  unset admin_password confirm_password
fi

echo
echo "Default project location"
echo "  1) ~/local (default)"
echo "  2) /var/www"
echo "  3) /opt"
current_location="$(python3 - "$CONFIG_PATH" <<'PYTHON'
import json
import sys

with open(sys.argv[1]) as config_file:
    location = json.load(config_file).get("default_install_location")
print(location if location in ("home-local", "/var/www", "/opt") else "home-local")
PYTHON
)"
current_label="$current_location"
if [[ "$current_location" == home-local ]]; then current_label='~/local'; fi
echo "Current location: $current_label"
install_location="$current_location"
if ! "$ASSUME_YES"; then
  while true; do
    read -r -p 'Choose a location [Enter keeps current]: ' location_choice || location_choice=""
    case "$location_choice" in
      '') break ;;
      1) install_location=home-local; break ;;
      2) install_location=/var/www; break ;;
      3) install_location=/opt; break ;;
      *) echo "Choose 1, 2 or 3." ;;
    esac
  done
fi
python3 "$INSTALL_DIR/panel.py" --set-install-location "$install_location"

if ask 'Set up passwordless sudo rules for the panel helpers now? (needs your sudo password) [Y/n]' y; then
  sudo_options=()
  if "$ASSUME_YES"; then sudo_options=(-n); fi
  if ! sudo "${sudo_options[@]}" bash "$INSTALL_DIR/setup-sudo.sh" "$USER" "$INSTALL_DIR"; then
    echo "Sudo setup did not finish. Site and service actions will not work until sudo rules are set up."
    echo "Run this command later:"
    printf 'sudo bash %q %q %q\n' "$INSTALL_DIR/setup-sudo.sh" "$USER" "$INSTALL_DIR"
  fi
else
  echo "To set up sudo rules later, run:"
  printf 'sudo bash %q %q %q\n' "$INSTALL_DIR/setup-sudo.sh" "$USER" "$INSTALL_DIR"
fi

chmod +x "$INSTALL_DIR/"*-helper.sh "$INSTALL_DIR/start-panel.sh" "$INSTALL_DIR/scripts/mcp-setup.sh"
[[ -f "$CONFIG_PATH" ]] && chmod 600 "$CONFIG_PATH"

echo
echo "MCP for AI tools (Claude Code, Codex, OpenCode)"
if ask 'Turn on MCP? [y/N]' n; then
  "$INSTALL_DIR/scripts/mcp-setup.sh" on
fi
echo 'To change MCP later, run scripts/mcp-setup.sh on|off|status from the repository directory.'

# Escape directory text for the desktop entry format and its Exec argument.
desktop_dir="${INSTALL_DIR//\\/\\\\}"
desktop_dir="${desktop_dir//$'\n'/\\n}"
desktop_dir="${desktop_dir//$'\r'/\\r}"
desktop_dir="${desktop_dir//$'\t'/\\t}"
exec_dir="${INSTALL_DIR//\\/\\\\\\\\}"
exec_dir="${exec_dir//\"/\\\\\"}"
exec_dir="${exec_dir//\$/\\\\\$}"
exec_dir="${exec_dir//\`/\\\\\`}"
exec_dir="${exec_dir//%/%%}"
exec_dir="${exec_dir//$'\n'/\\n}"
exec_dir="${exec_dir//$'\r'/\\r}"
exec_dir="${exec_dir//$'\t'/\\t}"

write_launcher() {
  cat > "$1" <<EOF
[Desktop Entry]
Name=CloudyCode Server Panel
Exec="$exec_dir/start-panel.sh"
Icon=$desktop_dir/panel-icon.svg
Terminal=false
Type=Application
Categories=Development;
EOF
}

launcher="$HOME/.local/share/applications/cloudycode-server-panel.desktop"
if ask 'Add desktop launcher? [Y/n]' y; then
  mkdir -p "$(dirname "$launcher")"
  write_launcher "$launcher"
  echo "Desktop launcher saved."
fi
if ask 'Start panel on login? [y/N]' n; then
  mkdir -p "$HOME/.config/autostart"
  # Also works when the applications launcher was declined.
  write_launcher "$HOME/.config/autostart/cloudycode-server-panel.desktop"
  echo "Panel will start on login."
fi

echo
echo "Panel URL: http://127.0.0.1:8765"
printf 'Start with: %q\n' "$INSTALL_DIR/start-panel.sh"
printf 'Or run: python3 %q\n' "$INSTALL_DIR/panel.py"
python3 - "$CONFIG_PATH" <<'PY'
import hashlib
import json
import sys

with open(sys.argv[1]) as config_file:
    cfg = json.load(config_file)
print("Username: " + cfg.get("username", "admin"))
if cfg.get("password_hash") == hashlib.sha256(b"admin").hexdigest():
    print("Reminder: change the default password admin in Settings.")
PY
