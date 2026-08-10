#!/usr/bin/env bash
set -euo pipefail

install -o root -g root -m 640 \
    /opt/qmzg/deploy/qmzg.conf \
    /etc/nginx/conf.d/qmzg.conf

nginx -t
systemctl enable nginx

# Alibaba Cloud's package transaction can leave a one-off nginx master outside
# systemd. Gracefully stop only that newly installed instance before handing
# ownership to the service manager.
if pgrep -x nginx >/dev/null && ! systemctl is-active --quiet nginx; then
    master_pid="$(ps -C nginx -o pid=,ppid= | awk '$2 == 1 {print $1; exit}')"
    test -n "${master_pid}"
    kill -QUIT "${master_pid}"
    for _ in $(seq 1 20); do
        pgrep -x nginx >/dev/null || break
        sleep 1
    done
fi

systemctl restart nginx
test "$(systemctl is-active nginx)" = "active"

echo "NGINX_STATUS=active"
ss -lntp | grep -E '(:80[[:space:]]|127\.0\.0\.1:8000)'
