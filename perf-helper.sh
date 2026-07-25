#!/bin/bash
# Performance config helper — called with sudo by the panel
# Usage: sudo perf-helper.sh <type> <src_file> <dest_file>
# Types: nginx, php, fpm, mysql

TYPE="$1"
SRC="$2"
DEST="$3"

[ -f "$SRC" ] || { echo "Error: $SRC not found"; exit 1; }

case "$TYPE" in
  nginx)
    BACKUP="${DEST}.bak"
    cp "$DEST" "$BACKUP" 2>/dev/null && echo "Backed up to $BACKUP"
    cp "$SRC" "$DEST" || { echo "Error: failed to save $DEST"; exit 1; }
    echo "Saved to $DEST"
    if nginx -t; then
      systemctl reload nginx && echo "Nginx reloaded OK"
    else
      echo "Nginx config test failed — restoring backup"
      cp "$BACKUP" "$DEST" 2>/dev/null
      nginx -t >/dev/null 2>&1 && systemctl reload nginx >/dev/null 2>&1
      exit 1
    fi
    ;;
  php|fpm)
    cp "$DEST" "${DEST}.bak" 2>/dev/null && echo "Backed up to ${DEST}.bak"
    cp "$SRC" "$DEST" && echo "Saved to $DEST"
    PHP_VER=$(php --version 2>/dev/null | grep -oP 'PHP \K[0-9]+\.[0-9]+' | head -1)
    systemctl restart "php${PHP_VER}-fpm" && echo "PHP-FPM restarted OK"
    ;;
  mysql)
    cp "$DEST" "${DEST}.bak" 2>/dev/null && echo "Backed up to ${DEST}.bak"
    cp "$SRC" "$DEST" && echo "Saved to $DEST"
    systemctl restart mysql && echo "MySQL restarted OK"
    ;;
esac
