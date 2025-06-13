# Crypto Auto Investment Bot（GMOコイン対応）

GMOコインのAPIを利用し、ビットコインなどの暗号資産を**定期購入・下落時追加購入**するPython製の自動積立ツールです。

---

## 🚀 機能概要

- ✅ 通貨価格の自動取得（GMO API）
- ✅ 定期購入（例：２日置き、週１回など）
- ✅ RSI・平均乖離・価格下落判定による追加購入
- ✅ 購入・エラー時のSlack通知
- ✅ SQLiteによる履歴管理（価格・購入）
- ✅ cron や タスクスケジューラでの定期実行対応

---

## 📦 必要環境

- Python 3.10+
- GMOコインのAPIキー
- VPS（常時稼働が必要）またはローカル実行
- SQLite3（標準装備）

---

# 🛠 セットアップ手順

## 1. リポジトリをクローン

   ```bash
   git clone https://github.com/eguchikoushi/auto_invest.git
   cd auto_invest
   ```

## 2. 仮想環境の作成と依存インストール

   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows の場合: venv\Scripts\activate
   pip install -r requirements.txt
   ```

## 3. `.env` を作成 (機密情報の登録)

リポジトリにある `.env.example` をリネームして `.env` を作成してください。

その後、APIキーやSlackのWebhook URL、メール情報を適切に書き換えて保存してください。

## 4. `settings.json` を設定
### base_purchase
定期的な基本購入に関する設定です。
   ```json
"base_purchase": {
  "settings": {
    "BTC": {
      "jpy": 500,
      "interval_days": 1,
      "min_order_amount": 0.00001
    },
    ...
  }
}
   ```
| キー名                | 説明                                        |
| ------------------ | ----------------------------------------- |
| `jpy`              | 1回あたりの購入金額（日本円）。例：500円分購入。                |
| `interval_days`    | 購入間隔（日数）。例：1なら毎日、7なら週1回購入。                |
| `min_order_amount` | GMOコインでの注文最小数量（通貨単位）。金額が小さすぎる場合はスキップされます。 |

### add_purchase
相場下落時などの条件付き追加購入に関する設定です。

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
    },
    ...
  }
}
   ```
| キー名                  | 説明                                  |
| -------------------- | ----------------------------------- |
| `enabled`            | 追加購入を有効にするか。`true` で有効。             |
| `jpy`                | 追加購入時に使用する金額（日本円）。                  |
| `min_score`          | スコア閾値。指定された複数条件のうち、いくつ満たせば購入するか。    |
| `min_order_amount`   | GMOの注文最小数量（通貨単位）。                   |
| `price_drop_percent` | 前回価格からの下落率（％）。例：`-3` は3%以上の下落で加点。   |
| `sma_deviation`      | 現在価格と移動平均（SMA）の乖離率（％）。割安圏をマイナス値で指定。 |
| `rsi_threshold`      | RSI（相対力指数）がこの値を下回ると加点対象。            |

---

### mail
   ```json
"mail": {
  "enabled": true
}
   ```
| キー名       | 説明                             |
| --------- | ------------------------------ |
| `enabled` | メール通知を有効にするかどうか。`true` で通知を送信。 |

### balance_warning_threshold_jpy
   ```json
   "balance_warning_threshold_jpy": 99999

   ```
| キー名                             | 説明                           |
| ------------------------------- | ---------------------------- |
| `balance_warning_threshold_jpy` | 日本円残高がこの金額を下回った場合、警告通知を行います。 |

## 5. 実行方法

```bash
python main.py --mode=basecheck   # 定期購入
python main.py --mode=dropcheck   # 価格下落時に追加購入
```

---

## 6. 自動実行（VPS）
例：每日朝9時に基本購入し、5分後に追加購入判定。

cron に以下のように登録します。


```
0 9 * * * /home/username/venv/bin/python /home/username/auto_invest/main.py --mode=basecheck >> cron.log 2>&1
5 9 * * * /home/username/venv/bin/python /home/username/auto_invest/main.py --mode=dropcheck >> cron.log 2>&1
```

## 7.  通知について
SlackのWebhook URLを .env に記載すれば通知可能です

失敗時・成功時にSlackにメッセージが送信されます

## 8. 注意点
GMOコインの注文は最小単位があるため、設定金額に注意。

初期14日間はRSIが正しく計算されません。

本番注文が実行されます。自己責任で使用してください。


---

## ライセンス

このプログラムは、クリエイティブ・コモンズ 表示 - 非営利 4.0 国際 ライセンス (CC BY-NC 4.0) のもとで提供されます。

詳細: [https://creativecommons.org/licenses/by-nc/4.0/deed.ja](https://creativecommons.org/licenses/by-nc/4.0/deed.ja)
