#!/usr/bin/env bash
# HTTPS を有効にする。root で実行し、ドメインを引数に渡す。
#
#   ssh -t senbun 'sudo bash ~/senbun/deploy/https.sh example.com'
#
# 前提: そのドメインの A レコードが senbun.konh.org を指していること。
#       さくらのコントロールパネルのパケットフィルタで 443 が開いていること。
set -euo pipefail

ドメイン="${1:-}"
if [ -z "$ドメイン" ]; then
  echo "使い方: sudo bash https.sh <ドメイン名>" >&2
  exit 1
fi
APP=/home/ubuntu/senbun

echo "==> DNS の確認"
引いた先=$(getent hosts "$ドメイン" | awk '{print $1}' | head -1 || true)
自分=$(hostname -I | awk '{print $1}')
echo "   $ドメイン → ${引いた先:-引けず}"
if [ -z "$引いた先" ]; then
  echo "   A レコードが引けません。DNS の反映を待ってから再実行してください。" >&2
  exit 1
fi

echo "==> certbot を入れる"
apt-get update -qq
apt-get install -y -qq certbot python3-certbot-nginx

echo "==> nginx にドメインを設定"
sed "s/YOUR_DOMAIN/$ドメイン/" "$APP/deploy/nginx.conf" > /etc/nginx/sites-available/senbun
ln -sf /etc/nginx/sites-available/senbun /etc/nginx/sites-enabled/senbun
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

echo "==> 証明書を取得(80番で認証 → 443を開いてリダイレクトも設定)"
certbot --nginx -d "$ドメイン" --non-interactive --agree-tos --redirect \
        --register-unsafely-without-email
nginx -t
systemctl reload nginx

echo "==> 自動更新の確認"
systemctl list-timers 'certbot*' --no-pager | head -3 || true
certbot renew --dry-run 2>&1 | tail -3

echo "==> 疎通"
curl -sS -o /dev/null -w "   https://$ドメイン/ → HTTP %{http_code}\n" "https://$ドメイン/"
curl -sS -o /dev/null -w "   http:// からの転送 → HTTP %{http_code}\n" "http://$ドメイン/"
echo
echo "完了。443 が外から届かない場合は、さくらのコントロールパネルの"
echo "パケットフィルタで 443 を許可してください。"
