import requests
import time
import json
import logging
from decimal import Decimal
from config import HEADERS, ORDER_URL, generate_signature

logger = logging.getLogger(__name__)


# --- 現在価格の取得（パブリックAPI） ---
def get_current_prices(symbols):
    result = {}
    for symbol in symbols:
        try:
            url = f"https://api.coin.z.com/public/v1/ticker?symbol={symbol}_JPY"
            resp = requests.get(url, timeout=5)
            resp.raise_for_status()
            data = resp.json()
            result[symbol] = Decimal(data["data"][0]["last"])
        except Exception as e:
            logger.error(f"{symbol}価格取得エラー: {e}")
    return result


# --- 日本円残高の取得（プライベートAPI） ---
def get_jpy_balance():
    timestamp = str(int(time.time() * 1000))
    method = "GET"
    endpoint = "/v1/account/assets"
    body = ""

    signature = generate_signature(timestamp, method, endpoint, body)
    headers = HEADERS.copy()
    headers.update({"API-TIMESTAMP": timestamp, "API-SIGN": signature})

    try:
        url = "https://api.coin.z.com/private/v1/account/assets"
        resp = requests.get(url, headers=headers, timeout=5)
        resp.raise_for_status()
        assets = resp.json()["data"]
        for asset in assets:
            if asset.get("symbol") == "JPY":
                return Decimal(asset["amount"])
    except Exception as e:
        logger.error(f"残高取得エラー: {e}")
        return None


# --- 成行注文の実行（プライベートAPI） ---
def place_order(symbol, size: Decimal):
    body = {
        "symbol": symbol,
        "side": "BUY",
        "executionType": "MARKET",
        "size": str(size),
    }
    body_json = json.dumps(body)
    timestamp = str(int(time.time() * 1000))
    signature = generate_signature(timestamp, "POST", "/v1/order", body_json)

    headers = HEADERS.copy()
    headers.update({"API-TIMESTAMP": timestamp, "API-SIGN": signature})

    try:
        response = requests.post(ORDER_URL, headers=headers, data=body_json, timeout=5)
        return response
    except Exception as e:
        logger.error(f"注文送信エラー: {e}")
        raise
