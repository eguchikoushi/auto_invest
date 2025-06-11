import os
import json
import logging
import hmac
import hashlib
import sys
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# --- .env 読み込み ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(dotenv_path=os.path.join(BASE_DIR, ".env"))

# --- パス定義 ---
DATA_DIR = os.path.join(BASE_DIR, "data")
SETTINGS_PATH = os.path.join(DATA_DIR, "settings.json")
os.makedirs(DATA_DIR, exist_ok=True)


# --- JSON読み込み関数 ---
def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"JSON読み込み失敗: {path} - {e}")
        return default


# --- 設定バリデーション関数 ---
def validate_settings(settings):
    logger.info("設定ファイルのバリデーションを開始...")

    base_settings = settings.get("base_purchase", {}).get("settings", {})
    required_keys_base = ["jpy", "interval_days", "min_order_amount"]

    for symbol, cfg in base_settings.items():
        if any(k not in cfg for k in required_keys_base):
            logger.error(f"base_purchase設定に必要な項目が不足 ({symbol}): {cfg}")
            sys.exit(1)
        if (
            cfg["jpy"] < 0 or
            cfg["interval_days"] < 1 or
            cfg["min_order_amount"] <= 0
        ):
            logger.error(f"base_purchase設定エラー ({symbol}): {cfg}")
            sys.exit(1)

    add_settings = settings.get("add_purchase", {}).get("settings", {})
    required_keys_add = [
        "jpy", "min_score", "min_order_amount",
        "price_drop_percent", "sma_deviation", "rsi_threshold"
    ]

    for symbol, cfg in add_settings.items():
        if any(k not in cfg for k in required_keys_add):
            logger.error(f"add_purchase設定に必要な項目が不足 ({symbol}): {cfg}")
            sys.exit(1)
        if (
            cfg["jpy"] < 0 or
            cfg["min_order_amount"] <= 0 or
            cfg["min_score"] < 0
        ):
            logger.error(f"add_purchase設定エラー ({symbol}): {cfg}")
            sys.exit(1)

    if not isinstance(settings.get("mail", {}).get("enabled"), bool):
        logger.error("mail設定の 'enabled' はboolである必要があります")
        sys.exit(1)

    threshold = settings.get("balance_warning_threshold_jpy")
    if not isinstance(threshold, int) or threshold < 0:
        logger.error("balance_warning_threshold_jpy は0以上の整数である必要があります")
        sys.exit(1)

    logger.info("設定ファイルバリデーション完了")


# --- 設定ロード ---
settings = load_json(SETTINGS_PATH)
validate_settings(settings)

# --- API情報 ---
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
ORDER_URL = "https://api.coin.z.com/private/v1/order"
HEADERS = {
    "Content-Type": "application/json",
    "API-KEY": API_KEY,
}


# --- HMAC署名生成 ---
def generate_signature(timestamp, method, endpoint, body):
    if API_SECRET is None:
        raise ValueError("API_SECRET が未設定です")

    message = f"{timestamp}{method}{endpoint}{body}"
    return hmac.new(
        API_SECRET.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
