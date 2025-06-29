# Crypto Auto Investment Bot（GMOコイン対応）

GMOコインのAPIを利用し、ビットコインなどの暗号資産を**定期購入・下落時追加購入**するPython製の自動積立ツールです。

---

## 🚀 機能概要

* ✅ 通貨価格の自動取得（GMO API）
* ✅ 定期購入（例：２日置き、週１回など）
* ✅ RSI・平均乖離・価格下落判定による追加購入
* ✅ 購入・エラー時のSlack通知
* ✅ SQLiteによる履歴管理（価格・購入）
* ✅ cron や タスクスケジューラでの定期実行対応
* ✅ record-priceモードによる価格記録（日足の統一記録に利用）

---

## 📦 必要環境

* Python 3.10+
* GMOコインのAPIキー
* VPS（常時稼働が必要）またはローカル実行
* SQLite3（標準装備）

---

## 🛠 セットアップ

### 1. リポジトリをクローン

```bash
git clone https://github.com/eguchikoushi/auto_invest.git
cd auto_invest
```

### 2. 仮想環境の作成と依存インストール

```bash
python -m venv venv
source venv/bin/activate  # Windows の場合: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. `.env` を作成（機密情報の登録）

リポジトリにある `.env.example` をコピーして `.env` を作成し、以下のように設定してください：

```env
API_KEY=  # GMOコインのAPIキー（現物取引用）
API_SECRET=  # 上記APIキーに対応する秘密鍵
SLACK_WEBHOOK=  # Slack通知用のWebhook URL（省略可）
MAIL_USER=  # Gmailアドレス（SMTP送信用）
MAIL_PASS=  # 上記Gmailのアプリパスワード
MAIL_TO=  # 通知メールの送信先アドレス
```

---

### 4. `settings.json` を設定

#### base\_purchase（定期購入）

```json
"base_purchase": {
  "settings": {
    "BTC": {
      "jpy": 500,
      "interval_days": 1,
      "min_order_amount": 0.00001
    }
  }
}
```

| キー名                | 説明             |
| ------------------ | -------------- |
| `jpy`              | 1回あたりの購入金額（円）  |
| `interval_days`    | 購入間隔（日数）       |
| `min_order_amount` | 注文の最小単位（GMO仕様） |

#### add\_purchase（条件付き追加購入）

```json
"add_purchase": {
  "enabled": true,
  "settings": {
    "BTC": {
      "jpy": 1000,
      "min_score": 2,
      "min_order_amount": 0.00001,
      "price_drop_percent": -3,
      "sma_deviation": -5,
      "rsi_threshold": 30
    }
  }
}
```

| キー名                  | 説明                                                                              |
| -------------------- | ------------------------------------------------------------------------------- |
| `enabled`            | trueで有効化                                                                        |
| `jpy`                | 追加購入に使用する金額（円）                                                                  |
| `min_score`          | 評価条件（価格下落・SMA乖離・RSI）をいくつ満たしたら購入するかを判定するためのスコア閾値。 |
| `price_drop_percent` | 前回価格からの下落率の閾値（%）                                                   |
| `sma_deviation`      | 30日平均とのSMA乖離率の閾値（%）                                                   |
| `rsi_threshold`      | RSIの閾値                                                               |
| `min_order_amount`   | 注文の最小単位（GMO仕様）                                                                  |

#### 通知・残高設定

```json
"mail": {
  "enabled": true
},
"balance_warning_threshold_jpy": 99999
```

| キー名                             | 説明                            |
| ------------------------------- | ----------------------------- |
| `enabled`                       | メール通知を有効にするかどうか（true で通知送信）   |
| `balance_warning_threshold_jpy` | 日本円残高がこの金額を下回るとSlack/メールで警告通知 |

#### alertcheck（急落検知）
```json
"alertcheck": {
  "enabled": true,
  "threshold_percent": -5,
  "enabled_symbols": ["BTC", "ETH"]
}
```
| キー名                 | 説明                                            |
| ------------------- | --------------------------------------------- |
| `enabled`           | `true` で急落検知モードを有効化                           |
| `threshold_percent` | 下落率の閾値（%）。この値以上に下落していればSlack通知を送信             |
| `enabled_symbols`   | 検知対象とする通貨シンボルの配列（省略時は base\_purchase の全通貨が対象） |

---

## ▶️ 実行例

```bash
python main.py --mode=basecheck         # 定期購入
python main.py --mode=dropcheck         # 条件付き追加購入
python main.py --mode=init-history      # すべての通貨の価格履歴を初期化（RSI用）
python main.py --mode=init-history --symbol=BTC  # 指定通貨のみ初期化
python main.py --mode=basecheck --dry-run     # テスト実行：定期購入のシミュレーション（注文なし）
python main.py --mode=dropcheck --dry-run     # テスト実行：条件付き追加購入のシミュレーション（注文なし）
python main.py --mode=record-price            # 現在価格のみを記録（評価用データ）
python main.py --mode=record-shortterm    # 現在価格を短期テーブルに記録（15分間隔などで運用）
python main.py --mode=alertcheck        # 急落検知を実行（Slack通知あり）

```

---

## ⏱ 自動実行（cron 例）

```cron
# --- 日次記録（毎朝9:00） ---
0 9 * * * /home/username/venv/bin/python /home/username/auto_invest/main.py --mode=record-price >> cron_record.log 2>&1

# --- 定期購入（基本購入）9:05に実行 ---
5 9 * * * /home/username/venv/bin/python /home/username/auto_invest/main.py --mode=basecheck >> cron.log 2>&1

# --- 条件付き追加購入（RSIや価格下落による加点）9:10に実行 ---
10 9 * * * /home/username/venv/bin/python /home/username/auto_invest/main.py --mode=dropcheck >> cron.log 2>&1

# --- 短期価格の定期記録（毎15分）---
*/15 * * * * /home/username/venv/bin/python /home/username/auto_invest/main.py --mode=record-shortterm >> cron_shortterm.log 2>&1

# --- 急落検知（record-shorttermの直後）---
1-59/15 * * * * /home/username/venv/bin/python /home/username/auto_invest/main.py --mode=alertcheck >> cron_alert.log 2>&1

```

---

## 🔔 通知について

`.env` に Slack Webhook を設定すると、以下のような通知が届きます：

* 成功時：`[BUY] BTC注文成功: 1000円 = 0.00005BTC`
* 失敗時：`[ERROR] BTC注文失敗: 不正な数量`
* 警告時：`日本円残高がしきい値を下回りました: 1000円`

---

## ⚠️ 注意事項

| 内容         | 説明                                                                                                                                 |
| ---------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| 本番注文       | 実際にGMOコインで注文が発行されます。自己責任でご利用ください                                                                                                   |
| 最小単位       | 設定金額（jpy）が最小注文量に満たない場合はスキップされます                                                                                                    |
| RSI用の履歴初期化 | 初回実行時はRSI計算用の過去14日分の価格履歴が不足しています。`--mode=init-history` を使って補完してください。CoinGeckoから1日ずつ取得するため、**10通貨 × 15日 × 最大15秒 = 約25分**かかることがあります。 |
| 急落検知と記録頻度 | `record-shortterm` で記録される最新2件の価格を使って下落率を評価します。記録間隔（例：15分）に応じた評価になります。 |


---

## 🪪 ライセンス

このプログラムは、クリエイティブ・コモンズ 表示 - 非営利 4.0 国際 ライセンス (CC BY-NC 4.0) のもとで提供されます。

詳細: [https://creativecommons.org/licenses/by-nc/4.0/deed.ja](https://creativecommons.org/licenses/by-nc/4.0/deed.ja)
