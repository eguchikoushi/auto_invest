# このスクリプトはGMOコインのAPIを使って自動で暗号資産を積み立て購入する自動化ツールです。
# 以下の主要機能を含みます：価格取得・RSIや移動平均による条件判定・Slackとメール通知・成行注文・ログ管理。

import os
import sys
import argparse
import datetime
import logging
from decimal import Decimal

# --- Logger初期設定（モジュールimport前に設定） ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "log")
os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger()  # root logger
logger.setLevel(logging.INFO)

log_file_path = os.path.join(LOG_DIR, f"{datetime.datetime.now():%Y-%m}.log")
file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
formatter = logging.Formatter(
    "[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# --- モジュールimport ---
from config import settings, BASE_DIR, DATA_DIR  # noqa: E402
from db_manager import DBManager  # noqa: E402
from notify import send_email, send_slack  # noqa: E402
from purchase import execute_base_purchase, execute_add_purchase_flow  # noqa: E402 E501
from api_client import (  # noqa: E402
    get_current_prices,
    get_jpy_balance,
    initialize_price_history_if_needed,
)

# --- 設定読み込みチェック ---
if settings is None:
    logger.critical("設定ファイルの読み込みに失敗しました。")
    sys.exit(1)


def check_balance():
    threshold = Decimal(str(settings.get("balance_warning_threshold_jpy", 0)))
    balance = get_jpy_balance()
    if balance is not None and balance < threshold:
        msg = f"日本円残高がしきい値を下回りました: {balance}円（閾値: {threshold}円）"
        logger.warning(msg)
        try:
            send_slack(msg)
        except Exception as e:
            logger.warning(f"Slack通知失敗: {e}")
        try:
            send_email("【自動積立BOT】残高警告", msg)
        except Exception as e:
            logger.warning(f"メール通知失敗: {e}")


def update_all_price_history(db):
    symbols = list(settings["base_purchase"]["settings"].keys())
    current_prices = get_current_prices(symbols)

    for symbol, price in current_prices.items():
        if price is None:
            logger.warning(f"{symbol} の価格取得に失敗しました")
            continue
        db.record_price_history(symbol, price)
        logger.info(f"{symbol} 現在価格を記録: {price} 円")


def save_all_short_term_prices(db):
    symbols = list(settings["base_purchase"]["settings"].keys())
    current_prices = get_current_prices(symbols)

    for symbol, price in current_prices.items():
        if price is None:
            logger.warning(f"{symbol} の価格取得に失敗しました")
            continue
        db.record_short_term_price(symbol, price)
        logger.info(f"{symbol} 短期価格を記録: {price}円")


def check_sudden_price_drop(db):
    alert_cfg = settings.get("alertcheck", {})
    if not alert_cfg.get("enabled", False):
        logger.info("alertcheck は設定で無効化されています。")
        return

    threshold = Decimal(str(alert_cfg.get("threshold_percent", -5)))
    symbols = alert_cfg.get("enabled_symbols") or list(
        settings["base_purchase"]["settings"].keys()
    )

    for symbol in symbols:
        rows = db.get_latest_short_term_prices(symbol, limit=2)

        if len(rows) < 2:
            logger.info(f"{symbol} の比較用データが不足しているためスキップ")
            continue

        old_price = rows[0][1]
        new_price = rows[1][1]
        change = ((new_price - old_price) / old_price) * Decimal("100")

        logger.info(f"{symbol} 急落判定: {change:.2f}%（閾値: {threshold}%）")

        if change <= threshold:
            msg = f"[ALERT] {symbol} が急落: {change:.2f}%（{old_price} → {new_price}）"
            logger.warning(msg)
            try:
                send_slack(msg)
            except Exception as e:
                logger.warning(f"Slack通知失敗: {e}")


def main():
    db = DBManager(data_dir=DATA_DIR)

    db.ensure_initialized()
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=[
            "record-price",
            "record-shortterm",
            "basecheck",
            "dropcheck",
            "init-history",
            "alertcheck",
        ],
        required=True,
    )
    parser.add_argument("--symbol", help="履歴補完する通貨シンボル（例: BTC）")
    parser.add_argument("--force", action="store_true", help="履歴があっても強制再取得")
    parser.add_argument(
        "--dry-run", action="store_true", help="テストモード（注文を送信しない）"
    )
    args = parser.parse_args()

    if args.mode == "basecheck" or args.mode == "dropcheck":
        check_balance()
        symbols = list(settings["base_purchase"]["settings"].keys())
        current_prices = get_current_prices(symbols)

    if args.mode == "basecheck":
        execute_base_purchase(current_prices, db, dry_run=args.dry_run)
    elif args.mode == "dropcheck":
        execute_add_purchase_flow(current_prices, db, dry_run=args.dry_run)
    elif args.mode == "init-history":
        if args.symbol:
            symbol = args.symbol.upper().strip()
            if symbol not in settings["base_purchase"]["settings"]:
                logger.error(f"{symbol} は設定に存在しません。")
                sys.exit(1)
            symbols = [symbol]
        else:
            symbols = list(settings["base_purchase"]["settings"].keys())

        for symbol in symbols:
            initialize_price_history_if_needed(
                symbol, db, required_days=15, force=args.force
            )
    elif args.mode == "record-price":
        update_all_price_history(db)
    elif args.mode == "record-shortterm":
        save_all_short_term_prices(db)
    elif args.mode == "alertcheck":
        check_sudden_price_drop(db)


if __name__ == "__main__":
    main()
