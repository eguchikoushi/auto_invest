import requests
import time
import json
import logging
import random
from decimal import Decimal
from datetime import datetime, timedelta
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


# --- CoinGeckoから過去価格を取得 ---
def get_historical_price(symbol, date_str):
    coingecko_map = {
        "BTC": "bitcoin",
        "ETH": "ethereum",
        "BCH": "bitcoin-cash",
        "LTC": "litecoin",
        "XRP": "ripple",
        "ADA": "cardano",
        "DOT": "polkadot",
        "SOL": "solana",
        "LINK": "chainlink",
        "DOGE": "dogecoin",
    }
    cg_id = coingecko_map.get(symbol.upper())
    if not cg_id:
        raise ValueError(f"{symbol} はCoinGecko非対応です")

    url = f"https://api.coingecko.com/api/v3/coins/{cg_id}/history?date={datetime.strptime(date_str, '%Y-%m-%d').strftime('%d-%m-%Y')}"  # noqa: E501
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    return Decimal(str(data["market_data"]["current_price"]["jpy"]))


# --- 必要な履歴数に満たない場合、過去の価格を補完 ---
def initialize_price_history_if_needed(symbol, db, required_days=15, force=False):
    existing = db.get_price_history(symbol, required_days)
    if len(existing) >= required_days and not force:
        logger.info(f"{symbol} の履歴が既に {len(existing)} 件あるためスキップします。")
        return

    logger.info(
        f"{symbol} の価格履歴が {required_days} 件未満です。過去価格を取得します。"
    )
    for i in range(required_days):
        target_date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        try:
            price = get_historical_price(symbol, target_date)
            db.record_price_history(symbol, price, date=target_date)
            logger.info(f"{symbol} {target_date} = {price} 円")
            time.sleep(random.uniform(12.0, 15.0))
        except Exception as e:
            logger.warning(f"{target_date} の {symbol} 価格取得失敗: {e}")
