#!/bin/bash
# Called by the panel with sudo. All privileged WordPress install operations in one place.
# Usage: sudo wp-install-helper.sh <install_path> <site_name> <php_ver>
set -e

INSTALL_PATH="$1"
SITE_NAME="$2"
PHP_VER="$3"
PANEL_USER="${SUDO_USER:-$(logname 2>/dev/null || true)}"

is_safe_wp_path() {
    case "$1" in
        *"/../"*|*"/.."|*"//"*) return 1 ;;
    esac
    case "$1" in
        /var/www/*|/opt/*) return 0 ;;
    esac
    if [ -n "$PANEL_USER" ]; then
        case "$1" in
            /home/"$PANEL_USER"/local/*) return 0 ;;
        esac
    fi
    return 1
}

ensure_www_data_home_access() {
    if [ -z "$PANEL_USER" ]; then
        return 0
    fi
    case "$1" in
        /home/"$PANEL_USER"/local/*)
            if command -v setfacl >/dev/null 2>&1; then
                setfacl -m u:www-data:--x "/home/"$PANEL_USER""
                setfacl -m u:www-data:rx "/home/"$PANEL_USER"/local" 2>/dev/null || true
            fi
            ;;
    esac
}

if [ "$INSTALL_PATH" = "--fix-perms" ]; then
    INSTALL_PATH="$SITE_NAME"
    if ! is_safe_wp_path "$INSTALL_PATH" || [ ! -f "$INSTALL_PATH/wp-config.php" ]; then
        echo "Error: unsafe path or wp-config.php not found: $INSTALL_PATH"
        exit 1
    fi
    ensure_www_data_home_access "$INSTALL_PATH"
    if [ -n "$PANEL_USER" ]; then
        chown www-data:"$PANEL_USER" "$INSTALL_PATH/wp-config.php"
    else
        chown www-data:www-data "$INSTALL_PATH/wp-config.php"
    fi
    chmod 660 "$INSTALL_PATH/wp-config.php"
    echo "[helper] Fixed wp-config.php permissions for $INSTALL_PATH"
    exit 0
fi

if [ "$INSTALL_PATH" = "--fix-site-perms" ]; then
    INSTALL_PATH="$SITE_NAME"
    if ! is_safe_wp_path "$INSTALL_PATH" || [ ! -d "$INSTALL_PATH" ]; then
        echo "Error: unsafe path or directory not found: $INSTALL_PATH"
        exit 1
    fi
    ensure_www_data_home_access "$INSTALL_PATH"
    chown -R www-data:www-data "$INSTALL_PATH"
    find "$INSTALL_PATH" -type d -exec chmod 2775 {} \;
    find "$INSTALL_PATH" -type f -exec chmod 664 {} \;
    if [ -f "$INSTALL_PATH/wp-config.php" ]; then
        if [ -n "$PANEL_USER" ]; then
            chown www-data:"$PANEL_USER" "$INSTALL_PATH/wp-config.php"
        fi
        chmod 660 "$INSTALL_PATH/wp-config.php"
    fi
    echo "[helper] Fixed WordPress site permissions for $INSTALL_PATH"
    exit 0
fi

if [ "$INSTALL_PATH" = "--set-port" ]; then
    NGINX_SITE="$SITE_NAME"
    PORT="$PHP_VER"
    case "$NGINX_SITE" in
        *[!A-Za-z0-9._-]*|"") echo "Error: bad nginx site name"; exit 1 ;;
    esac
    case "$PORT" in
        ''|*[!0-9]*) echo "Error: bad port"; exit 1 ;;
    esac
    if [ "$PORT" -lt 1 ] || [ "$PORT" -gt 65535 ]; then
        echo "Error: port must be between 1 and 65535"
        exit 1
    fi

    SITE_CONF="/etc/nginx/sites-available/$NGINX_SITE"
    TMP_CONF="$(mktemp "/tmp/_panel_wp_port_${NGINX_SITE}.XXXXXX")"
    if [ ! -f "$SITE_CONF" ]; then
        echo "Error: nginx site not found: $NGINX_SITE"
        exit 1
    fi

    python3 - "$SITE_CONF" "$TMP_CONF" "$PORT" <<'PY'
import re
import sys

src, dst, port = sys.argv[1:4]
content = open(src).read()
new_content, count = re.subn(
    r'(?m)^(\s*listen\s+)(?:\[::\]:)?\d+((?:\s+[^;]*)?;)',
    rf'\g<1>{port}\2',
    content,
    count=1,
)
if not count:
    raise SystemExit('Error: no listen directive found')
open(dst, 'w').write(new_content)
PY

    cp "$SITE_CONF" "${SITE_CONF}.bak"
    cp "$TMP_CONF" "$SITE_CONF"
    nginx -t
    systemctl reload nginx
    echo "[helper] Changed $NGINX_SITE to port $PORT"
    exit 0
fi

if ! is_safe_wp_path "$INSTALL_PATH"; then
    echo "Error: unsafe install path: $INSTALL_PATH"
    exit 1
fi

ensure_www_data_home_access "$INSTALL_PATH"

echo "[helper] Creating directory $INSTALL_PATH"
mkdir -p "$INSTALL_PATH"

echo "[helper] Copying WordPress files"
cp -r /tmp/_panel_wp_src/. "$INSTALL_PATH/"

echo "[helper] Writing wp-config.php"
cp "/tmp/_panel_wp_config_${SITE_NAME}.php" "$INSTALL_PATH/wp-config.php"

echo "[helper] Setting permissions"
chown -R www-data:www-data "$INSTALL_PATH"
find "$INSTALL_PATH" -type d -exec chmod 2775 {} \;
find "$INSTALL_PATH" -type f -exec chmod 664 {} \;
# Keep wp-config private
if [ -n "$PANEL_USER" ]; then
    chown www-data:"$PANEL_USER" "$INSTALL_PATH/wp-config.php"
fi
chmod 660 "$INSTALL_PATH/wp-config.php"

echo "[helper] Installing Nginx site"
cp "/tmp/_panel_wp_nginx_${SITE_NAME}" "/etc/nginx/sites-available/${SITE_NAME}"
ln -sf "/etc/nginx/sites-available/${SITE_NAME}" "/etc/nginx/sites-enabled/${SITE_NAME}"
nginx -t
systemctl reload nginx

echo "[helper] Done"
