#!/bin/bash
# Called by the panel with sudo. Handles privileged Laravel file/nginx operations.
# Usage:
#   sudo laravel-helper.sh install <src_path> <install_path> <site_name> <php_ver> <port>
#   sudo laravel-helper.sh delete <install_path> <site_name>
#   sudo laravel-helper.sh set-port <site_name> <port>
set -e

ACTION="$1"
ARG2="$2"
ARG3="$3"
ARG4="$4"
ARG5="$5"
ARG6="$6"

is_safe_path() {
    case "$1" in
        /var/www/*|/opt/*) return 0 ;;
        *) return 1 ;;
    esac
}

is_safe_site() {
    case "$1" in
        *[!A-Za-z0-9._-]*|"") return 1 ;;
        *) return 0 ;;
    esac
}

set_laravel_perms() {
    APP_PATH="$1"
    chown -R www-data:www-data "$APP_PATH"
    find "$APP_PATH" -type d -exec chmod 2775 {} \;
    find "$APP_PATH" -type f -exec chmod 664 {} \;
    if [ -d "$APP_PATH/storage" ]; then chmod -R 2775 "$APP_PATH/storage"; fi
    if [ -d "$APP_PATH/bootstrap/cache" ]; then chmod -R 2775 "$APP_PATH/bootstrap/cache"; fi
    if [ -f "$APP_PATH/.env" ]; then chmod 660 "$APP_PATH/.env"; fi
}

reload_or_start_nginx() {
    if systemctl is-active --quiet nginx; then
        systemctl reload nginx
    else
        systemctl start nginx
    fi
}

case "$ACTION" in
  install)
    SRC_PATH="$ARG2"
    INSTALL_PATH="$ARG3"
    SITE_NAME="$ARG4"
    PHP_VER="$ARG5"
    PORT="$ARG6"

    is_safe_path "$INSTALL_PATH" || { echo "Error: unsafe install path"; exit 1; }
    is_safe_site "$SITE_NAME" || { echo "Error: bad site name"; exit 1; }
    [ -d "$SRC_PATH" ] || { echo "Error: source path not found"; exit 1; }

    mkdir -p "$INSTALL_PATH"
    cp -a "$SRC_PATH/." "$INSTALL_PATH/"
    set_laravel_perms "$INSTALL_PATH"

    cat > "/etc/nginx/sites-available/$SITE_NAME" <<EOF
server {
    listen $PORT;
    server_name localhost;
    root $INSTALL_PATH/public;
    index index.php index.html;

    location / {
        try_files \$uri \$uri/ /index.php?\$query_string;
    }

    location ~ \.php$ {
        include snippets/fastcgi-php.conf;
        fastcgi_pass unix:/run/php/php$PHP_VER-fpm.sock;
    }

    location ~ /\.ht {
        deny all;
    }
}
EOF
    ln -sf "/etc/nginx/sites-available/$SITE_NAME" "/etc/nginx/sites-enabled/$SITE_NAME"
    nginx -t
    reload_or_start_nginx
    echo "[helper] Laravel installed at $INSTALL_PATH"
    ;;

  delete)
    INSTALL_PATH="$ARG2"
    SITE_NAME="$ARG3"
    is_safe_path "$INSTALL_PATH" || { echo "Error: unsafe install path"; exit 1; }
    is_safe_site "$SITE_NAME" || { echo "Error: bad site name"; exit 1; }
    rm -f "/etc/nginx/sites-enabled/$SITE_NAME" "/etc/nginx/sites-available/$SITE_NAME"
    rm -rf "$INSTALL_PATH"
    nginx -t
    reload_or_start_nginx
    echo "[helper] Laravel deleted: $INSTALL_PATH"
    ;;

  set-port)
    SITE_NAME="$ARG2"
    PORT="$ARG3"
    is_safe_site "$SITE_NAME" || { echo "Error: bad site name"; exit 1; }
    case "$PORT" in ''|*[!0-9]*) echo "Error: bad port"; exit 1 ;; esac
    SITE_CONF="/etc/nginx/sites-available/$SITE_NAME"
    [ -f "$SITE_CONF" ] || { echo "Error: nginx site not found"; exit 1; }
    python3 - "$SITE_CONF" "$PORT" <<'PY'
import re, sys
path, port = sys.argv[1:3]
content = open(path).read()
content, count = re.subn(r'(?m)^(\s*listen\s+)(?:\[::\]:)?\d+((?:\s+[^;]*)?;)', rf'\g<1>{port}\2', content, count=1)
if not count:
    raise SystemExit('Error: no listen directive found')
open(path, 'w').write(content)
PY
    nginx -t
    reload_or_start_nginx
    echo "[helper] Changed $SITE_NAME to port $PORT"
    ;;

  *)
    echo "Usage: laravel-helper.sh install|delete|set-port ..."
    exit 1
    ;;
esac
