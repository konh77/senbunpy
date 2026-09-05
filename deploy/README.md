# デプロイ

## 現状(2026-08-30)

上げられる状態になっています。

- エンジン: 人口 → 所得 → 消費 → 政府 → 指標 が毎月回る。保存則は毎tick検算
- DSL: laws/ の3例文が lexer → parser → validator → compiler → IR まで通る
- テスト 111本 緑(skip 1 = 賃金の出典確認待ち)
- `/api/run` は実データを返す(合成データモードは削除済み)

## ローカルで動かす

```bash
.venv/bin/uvicorn server.app:app --reload --port 8000
```

- `/` … 現行UI(HTML 1枚 8KB、外部アセットなし)
- `/archive/` … 旧UI(ドット絵の街)。凍結してあり更新しない

## 上げる(さくらVPS / Ubuntu)

### OS とバージョン

**Ubuntu 24.04 LTS** を選ぶ。理由は Python のバージョン:

| OS | 既定の Python | numpy 2.5.1 (要 >=3.12) |
|---|---|---|
| Ubuntu 22.04 LTS | 3.10 | ❌ 入らない |
| **Ubuntu 24.04 LTS** | **3.12** | ✅ |
| Ubuntu 26.04 LTS | (※要確認) | おそらく可 |

開発機は Python 3.14 だが、コードは 3.9 の構文でも解析が通る
(PEP695 の `type` 文、`match`、`except*` を使っていない)。
実際の下限を決めているのは **numpy 2.5.1 の `Requires-Python >=3.12`** で、
そこだけが 24.04 を要求している。

numpy 側も `bincount` / `searchsorted` / `maximum.at` / `divide(out=, where=)` しか
使っておらず 2.x 固有の API は無いので、3.10 や 3.11 の環境に落ちるなら
numpy を 1.26 に下げれば動く見込み(未検証)。

### AlmaLinux / Rocky を選んだ場合

`deploy/` の中身は Debian/Ubuntu 専用の形になっている。RHEL系では2か所直す:

- `nginx.conf` の置き場所 — `sites-available` + `sites-enabled` は Debian の流儀。
  RHEL系は `/etc/nginx/conf.d/senbun.conf` に直接置く
- `senbun.service` の `User=www-data` — RHEL系では `nginx` ユーザー

前提は nginx。所要 30分。

### 1. コードを置く

```bash
rsync -av --delete --exclude '.venv' --exclude '.git' --exclude '__pycache__' --exclude '.pytest_cache' ./ USER@HOST:/opt/senbun/
```

### 2. サーバ側で仮想環境

```bash
cd /opt/senbun && python3 -m venv .venv && .venv/bin/pip install -r requirements-server.txt
```

`requirements.txt` ではなく **`requirements-server.txt`** を使うこと。
サーバが実際に import するのは fastapi / uvicorn / pydantic / numpy だけで、
pandas・matplotlib・pillow などは統計の前処理と作図用(tools/ の下)。
16個 対 41個、**インストール容量で 162MB の差**。512MB のVPSでは pandas の
インストール自体がメモリ不足で落ちることがある。

### 3. systemd

```bash
sudo cp /opt/senbun/deploy/senbun.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now senbun
sudo systemctl status senbun
```

### 4. nginx

`deploy/nginx.conf` の `YOUR_DOMAIN` を実際のドメインに変えてから:

```bash
sudo cp /opt/senbun/deploy/nginx.conf /etc/nginx/sites-available/senbun
sudo ln -sf /etc/nginx/sites-available/senbun /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 5. HTTPS

```bash
sudo certbot --nginx -d YOUR_DOMAIN
```

### 6. 動作確認

```bash
curl -s https://YOUR_DOMAIN/api/health
curl -s -X POST https://YOUR_DOMAIN/api/run -H 'Content-Type: application/json' -d '{"months":12,"seed":42}' | head -c 200
```

## 公開前チェック

- [x] 合成データモードを削除(`server/demo_data.py` ごと削除済み)
- [x] `--reload` は付けない(systemd の ExecStart に入れていない)
- [x] 同時実行の上限。`SENBUN_MAX_CONCURRENT`(既定2)を超えたら 503 + `Retry-After`。
      600ヶ月×2本で CPU を約3.3秒占有するため
- [x] CORS。UI は同一オリジン配信なので本番では不要。別オリジンから叩くなら
      `SENBUN_ORIGINS` にカンマ区切りで足す(コードは触らない)
- [ ] `deploy/nginx.conf` の `YOUR_DOMAIN` を置換
- [x] 依存を最小化(`requirements-server.txt`)。統計・作図まわりを禁止しても
      サーバが全機能動くことを確認済み
- [ ] メモリ。実測はプロセス常駐 63MB + 1リクエストあたり最大 13MB。
      512MB なら `SENBUN_MAX_CONCURRENT=1`、1GB なら既定の 2 で余裕

## 必要なVPSの性能(実測ベース)

| | 実測(開発機) |
|---|---|
| 常駐メモリ | 63 MB(numpy + FastAPI + エンジン) |
| 1リクエストの増分 | +1〜13 MB |
| 120ヶ月 × 2本 | 0.79 秒 |
| 600ヶ月 × 2本 | 3.33 秒 |
| 起動 | 0.18 秒 |
| 並列2スレッドの速度比 | **1.40倍**(GIL。コアを増やしても効かない) |

**1コア / 1GB で十分。** コアを増やしても速くならないのは、エンジンが
Python のループ主体で GIL に縛られるため。増やしたければスレッドではなく
`uvicorn --workers N`(別プロセス)にする。1ワーカーあたり約 76MB。

## 環境変数

| 変数 | 既定 | 用途 |
|---|---|---|
| `SENBUN_MAX_CONCURRENT` | 2 | 同時に走らせるシミュレーション本数 |
| `SENBUN_ORIGINS` | (空) | CORS を許可する追加オリジン(カンマ区切り) |
