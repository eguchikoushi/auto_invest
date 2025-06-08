import logging
import time
import json
import requests
import datetime
from decimal import Decimal, ROUND_DOWN
from config import settings, API_SECRET, HEADERS
from notify import send_slack, send_email
from config import generate_signature
from api_client import place_order

logger = logging.getLogger(__name__)

ORDER_URL = "https://api.coin.z.com/private/v1/order"

# --- 平均価格の計算 ---
def get_30day_average(symbol, db):
    history = db.get_price_history(symbol, 30)
    if not history:
        return None
    prices = [p for _, p in history]
    return sum(prices) / len(prices)

# --- RSIの計算 ---
def calculate_rsi(symbol, db, period=14):
    history = db.get_price_history(symbol, period + 1)
    if len(history) < period + 1:
        return None

    gains, losses = [], []
    for i in range(1, period + 1):
        prev = history[i - 1][1]
        curr = history[i][1]
        diff = curr - prev
        if diff > 0:
            gains.append(diff)
            losses.append(Decimal("0"))
        else:
            gains.append(Decimal("0"))
            losses.append(-diff)

    avg_gain = sum(gains) / Decimal(period)
    avg_loss = sum(losses) / Decimal(period)

    if avg_loss == 0:
        return Decimal("100")

    rs = avg_gain / avg_loss
    rsi = Decimal("100") - (Decimal("100") / (Decimal("1") + rs))
    return rsi.quantize(Decimal("0.01"))

# --- 長期下落トレンド判定 ---
def is_long_term_downtrend(symbol, db):
    history = db.get_price_history(symbol, 37)
    if len(history) < 37:
        return False

    prices_now = [p for _, p in history[-30:]]
    prices_prev = [p for _, p in history[-37:-7]]

    sma_now = sum(prices_now) / Decimal(30)
    sma_prev = sum(prices_prev) / Decimal(30)

    return sma_now < sma_prev

# --- 購入結果処理 ---
def handle_order_result(response, symbol, jpy, amount, current_price, purchase_type,  db):
    if response.status_code == 200:
        logger.info(f"注文完了: {symbol} {jpy} 円 = {amount}")
        try:
            send_slack(f"[BUY] {symbol}注文成功: {jpy}円 = {amount}")
        except Exception as e:
            logger.warning(f"Slack通知失敗: {e}")
        db.record_purchase_history(symbol, jpy, amount, purchase_type, current_price)
    else:
        logger.error(f"注文失敗: {response.status_code} {response.text}")
        try:
            send_slack(f"[ERROR] {symbol}注文失敗: {response.text}")
        except Exception as e:
            logger.warning(f"Slack通知失敗: {e}")

# --- 基本購入を実行する ---
def execute_base_purchase(current_prices, db):
    now = datetime.datetime.now()
    logger.info("基本購入を開始します。")

    for symbol, conf in settings["base_purchase"]["settings"].items():
        jpy = conf["jpy"]
        interval_days = conf.get("interval_days", 2)

        if jpy <= 0:
            continue

        if symbol not in current_prices:
            logger.warning(f"{symbol} の現在価格が取得できません。")
            continue

        current_price = current_prices[symbol]

        last_row = db.get_last_purchase(symbol)
        last_time = datetime.datetime.fromisoformat(last_row[0]) if last_row else None
        if not last_time or (now - last_time).days >= interval_days:
            min_unit = Decimal(str(conf["min_order_amount"]))
            amount = (Decimal(jpy) / current_price).quantize(min_unit, rounding=ROUND_DOWN)

            response = place_order(symbol, amount)
            handle_order_result(response, symbol, jpy, amount,current_price, "base", db)
            db.record_price_history(symbol, current_price)
        else:
            logger.info(f"{symbol} 基本購入スキップ（{interval_days}日未満）")

# --- 追加購入条件の判定 ---
def check_add_purchase_conditions(symbol, conf, current_price, last_price, avg_price, rsi, db):
    score = 0
    reasons = []

    if last_price:
        change = (current_price - last_price) / last_price * Decimal("100")
        reasons.append(f"前回比={change:.2f}%")
        if change <= Decimal(conf.get("price_drop_percent", -3)):
            score += 1
    else:
        reasons.append("前回価格なし")

    if avg_price:
        sma_dev = (current_price - avg_price) / avg_price * Decimal("100")
        if sma_dev <= Decimal(conf.get("sma_deviation", -5)):
            score += 1
            reasons.append("30日平均より下落")

    if rsi is not None:
        threshold = Decimal(conf.get("rsi_threshold", 30))
        if rsi <= threshold:
            score += 1
            reasons.append(f"RSI={rsi}")
        else:
            reasons.append(f"RSI高={rsi}")
    else:
        reasons.append("RSI未取得")

    if is_long_term_downtrend(symbol, db):
        score -= 1
        reasons.append("長期トレンド悪化")

    return score, reasons

# --- 追加購入の実行 ---
def execute_add_purchase(current_prices, db):
    skipped_symbols = set()

    # --- 価格記録 ---
    for symbol in settings["add_purchase"]["settings"]:
        price = current_prices.get(symbol)
        if price is not None:
            db.record_price_history(symbol, price)
        else:
            skipped_symbols.add(symbol)

    if not settings["add_purchase"].get("enabled", False):
        logger.info("追加購入は設定で無効になっています。")
        return

    # --- 購入判定 ---
    logger.info("追加購入を実行します。")

    for symbol, conf in settings["add_purchase"]["settings"].items():
        jpy = conf.get("jpy", 0)
        if jpy <= 0:
            continue

        if symbol not in current_prices:
            logger.info(f"{symbol} 追加購入をスキップします。（価格取得エラーのため）")
            continue

        current_price = current_prices[symbol]

        last_row = db.get_last_purchase(symbol)

        if last_row and last_row[3] is not None:
            last_price = Decimal(last_row[3])
        else:
            last_price = None

        avg_price = get_30day_average(symbol, db)
        rsi = calculate_rsi(symbol, db)

        score, reasons = check_add_purchase_conditions(symbol, conf, current_price, last_price, avg_price, rsi, db)

        min_score = conf.get("min_score", 2)
        if score >= min_score:
            logger.info(f"{symbol} 条件一致 スコア={score}（{', '.join(reasons)}）")
            try:
                send_slack(f"[BUY] {symbol} 追加購入実行（スコア={score}）: {', '.join(reasons)}")
            except Exception as e:
                logger.warning(f"Slack通知失敗: {e}")

            min_unit = Decimal(str(conf["min_order_amount"]))
            amount = (Decimal(jpy) / current_price).quantize(min_unit, rounding=ROUND_DOWN)
            response = place_order(symbol, amount)
            handle_order_result(response, symbol, jpy, amount, current_price, "add", db)
        else:
            logger.info(f"{symbol} 追加購入条件を満たしません（スコア={score}, 理由: {', '.join(reasons)}）")
