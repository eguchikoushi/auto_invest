# このスクリプトはGMOコインのAPIを使って自動で暗号資産を積み立て購入する自動化ツールです。
# 以下の主要機能を含みます：価格取得・RSIや移動平均による条件判定・Slackとメール通知・成行注文・ログ管理。

import os
import sys
import time
import json
import hmac
import hashlib
import smtplib
import argparse
import sqlite3
import requests
import datetime
import logging
from email.mime.text import MIMEText
from decimal import Decimal, ROUND_DOWN
from dotenv import load_dotenv
# --- 独自モジュール import ---
from config import settings, BASE_DIR, DATA_DIR, HEADERS, generate_signature
from db_manager import DBManager
from notify import send_email, send_slack
from purchase import execute_base_purchase, execute_add_purchase
from api_client import get_current_prices, get_jpy_balance

# --- 設定読み込みチェック ---
if settings is None:
    logger.critical("設定ファイルの読み込みに失敗しました。")
    sys.exit(1)

# --- Logger初期設定 ---
LOG_DIR = os.path.join(BASE_DIR, "log")
os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger()  # root logger
logger.setLevel(logging.INFO)

log_file_path = os.path.join(LOG_DIR, f"{datetime.datetime.now():%Y-%m}.log")
file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# --- ファイルパス ---
os.makedirs(LOG_DIR, exist_ok=True)

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

def main():
    db = DBManager(data_dir=DATA_DIR)

    db.ensure_initialized()
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["basecheck", "dropcheck"], required=True)
    args = parser.parse_args()

    check_balance()

    symbols = list(settings["base_purchase"]["settings"].keys())
    current_prices = get_current_prices(symbols)

    if args.mode == "basecheck":
        execute_base_purchase(current_prices,db)
    elif args.mode == "dropcheck":
        execute_add_purchase(current_prices,db)

if __name__ == "__main__":
    main()
