#!/bin/bash
# Grant passwordless sudo for Server Panel commands
# Run once with:  sudo bash setup-sudo.sh

USER="${1:-$(logname 2>/dev/null || echo $SUDO_USER)}"
if [ -z "$USER" ]; then
  echo "Usage: sudo bash setup-sudo.sh YOUR_USERNAME"
  exit 1
fi

cat > /etc/sudoers.d/server-panel << EOF
# Server Panel — passwordless sudo rules for $USER
$USER ALL=(ALL) NOPASSWD: /usr/bin/systemctl start nginx
$USER ALL=(ALL) NOPASSWD: /usr/bin/systemctl stop nginx
$USER ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart nginx
$USER ALL=(ALL) NOPASSWD: /usr/bin/systemctl reload nginx
$USER ALL=(ALL) NOPASSWD: /usr/bin/systemctl start mysql
$USER ALL=(ALL) NOPASSWD: /usr/bin/systemctl stop mysql
$USER ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart mysql
$USER ALL=(ALL) NOPASSWD: /usr/bin/nginx -t *
$USER ALL=(ALL) NOPASSWD: /bin/cp /tmp/_panel_* /etc/nginx/*
$USER ALL=(ALL) NOPASSWD: /bin/cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.bak
$USER ALL=(ALL) NOPASSWD: /bin/ln -sf /etc/nginx/sites-available/* /etc/nginx/sites-enabled/*
$USER ALL=(ALL) NOPASSWD: /bin/rm -f /etc/nginx/sites-enabled/*
$USER ALL=(ALL) NOPASSWD: /usr/bin/tail * /var/log/nginx/*
$USER ALL=(ALL) NOPASSWD: /usr/bin/mysql *
$USER ALL=(ALL) NOPASSWD: /usr/bin/systemctl start php*-fpm
$USER ALL=(ALL) NOPASSWD: /usr/bin/systemctl stop php*-fpm
$USER ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart php*-fpm
$USER ALL=(ALL) NOPASSWD: /bin/cp /tmp/_panel_pma_* /etc/phpmyadmin/*
$USER ALL=(ALL) NOPASSWD: /bin/cp /tmp/_panel_pma_nginx /etc/nginx/sites-available/phpmyadmin
$USER ALL=(ALL) NOPASSWD: /usr/bin/apt-get install -y phpmyadmin *
$USER ALL=(ALL) NOPASSWD: /home/$USER/Documents/server-panel/wp-install-helper.sh *
$USER ALL=(ALL) NOPASSWD: /home/$USER/Documents/server-panel/wp-delete-helper.sh *
$USER ALL=(ALL) NOPASSWD: /home/$USER/Documents/server-panel/laravel-helper.sh *
$USER ALL=(ALL) NOPASSWD: /home/$USER/Documents/server-panel/codeigniter-helper.sh *
$USER ALL=(ALL) NOPASSWD: /home/$USER/Documents/server-panel/perf-helper.sh *
EOF

chmod 440 /etc/sudoers.d/server-panel
echo "Done! Sudo rules installed for user: $USER"
echo "Now run:  python3 panel.py"
