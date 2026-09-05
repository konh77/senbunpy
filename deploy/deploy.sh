#!/usr/bin/env bash
# 千分の一の国 — デプロイ。鍵認証が通っていることが前提(パスワードは扱わない)。
#
#   接続先は ~/.ssh/config の Host senbun。
#   一般ユーザー(ponpon)で入るので、sudo が要る作業は setup-once.sh に分けてある。
#
#   使い方:  bash deploy/deploy.sh
set -euo pipefail

HOST="${SENBUN_HOST:-senbun}"
DEST="${SENBUN_DEST:-/opt/senbun}"

echo "==> 疎通確認 ($HOST)"
ssh -o BatchMode=yes -o ConnectTimeout=8 "$HOST" \
  'echo "  接続OK"; . /etc/os-release && echo "  $PRETTY_NAME"; echo -n "  "; python3 -V'

echo "==> 置き場所の確認"
ssh "$HOST" "[ -w $DEST ] || { echo '  $DEST に書き込めません。先に deploy/setup-once.sh の内容を実行してください'; exit 1; }"

echo "==> コードを転送"
rsync -az --delete \
  --exclude '.venv' --exclude '.git' --exclude '__pycache__' --exclude '.pytest_cache' \
  --exclude '.DS_Store' --exclude 'data/raw' \
  ./ "$HOST:$DEST/"

echo "==> 仮想環境と依存"
ssh "$HOST" "cd $DEST && python3 -m venv .venv 2>/dev/null || true
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q -r requirements-server.txt
  .venv/bin/python -c 'import numpy,fastapi;print(\"  numpy\",numpy.__version__,\"/ fastapi\",fastapi.__version__)'"

echo "==> 試走(サービス登録前に素で動くか)"
ssh "$HOST" "cd $DEST && .venv/bin/python -c 'from engine.engine import run
r = run(12, seed=42)
print(\"  12ヶ月OK  人口\", r[\"series\"][\"population\"][-1], \"/ GDP\", r[\"series\"][\"gdp\"][-1])'"

echo "==> サービス再起動"
if ssh "$HOST" "sudo -n systemctl restart senbun" 2>/dev/null; then
  sleep 2
  ssh "$HOST" "systemctl is-active senbun && curl -sS -m 20 http://127.0.0.1:8000/api/health; echo"
else
  echo "  sudo にパスワードが要るので、ここは手で:"
  echo "    ssh $HOST 'sudo systemctl restart senbun'"
fi
