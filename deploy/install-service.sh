#!/usr/bin/env bash
# root で実行する。systemd 登録と nginx の設定。
#   ssh -t senbun 'sudo bash ~/senbun/deploy/install-service.sh'
set -euo pipefail
APP=/home/ubuntu/senbun

echo "==> systemd"
install -m 644 "$APP/deploy/senbun.service" /etc/systemd/system/senbun.service
systemctl daemon-reload
systemctl enable --now senbun
sleep 2
systemctl is-active senbun && echo "  senbun: 起動している"

echo "==> nginx"
install -m 644 "$APP/deploy/nginx.conf" /etc/nginx/sites-available/senbun
ln -sf /etc/nginx/sites-available/senbun /etc/nginx/sites-enabled/senbun
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx
echo "  nginx: 設定OK"

echo "==> ファイアウォール"
if command -v ufw >/dev/null && ufw status | grep -q "Status: active"; then
  ufw allow 'Nginx HTTP' >/dev/null && echo "  ufw: 80番を開けた"
else
  echo "  ufw: 無効(何もしない)"
fi

echo "==> 疎通"
curl -sS -o /dev/null -w "  localhost:80 → HTTP %{http_code}\n" http://127.0.0.1/api/health
echo
echo "完了。 https://senbun.konh.org/ が開くはず。"
echo "開かない場合は さくらのコントロールパネル → パケットフィルタ で 80番 を許可。"
