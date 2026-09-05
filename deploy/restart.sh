#!/usr/bin/env bash
# ユニットを入れ直して再起動する。root で実行。
#   ssh -t senbun 'sudo bash ~/senbun/deploy/restart.sh'
set -euo pipefail
install -m 644 /home/ubuntu/senbun/deploy/senbun.service /etc/systemd/system/senbun.service
systemctl daemon-reload
systemctl restart senbun
sleep 2
systemctl is-active senbun
curl -sS -o /dev/null -w "  localhost:80 → HTTP %{http_code}\n" http://127.0.0.1/api/health
