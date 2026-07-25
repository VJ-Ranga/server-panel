#!/bin/bash
# Called with sudo by the panel to delete WordPress site files and nginx config.
# Usage: sudo wp-delete-helper.sh <install_path> <nginx_site>
set -e

INSTALL_PATH="$1"
NGINX_SITE="$2"

# Remove nginx site
if [ -n "$NGINX_SITE" ]; then
    rm -f "/etc/nginx/sites-enabled/$NGINX_SITE"
    rm -f "/etc/nginx/sites-available/$NGINX_SITE"
    echo "[helper] Nginx site '$NGINX_SITE' removed"
    nginx -t && systemctl reload nginx && echo "[helper] Nginx reloaded"
fi

# Remove files (guard against dangerous paths)
if [ -n "$INSTALL_PATH" ] && [ "$INSTALL_PATH" != "/" ] && \
   [ "$INSTALL_PATH" != "/var" ] && [ "$INSTALL_PATH" != "/var/www" ] && \
   [ "$INSTALL_PATH" != "/opt" ] && [ "$INSTALL_PATH" != "/usr" ] && \
   [ "$INSTALL_PATH" != "/home" ]; then
    rm -rf "$INSTALL_PATH"
    echo "[helper] Files at '$INSTALL_PATH' removed"
fi

echo "[helper] Done"
