import logging
import datetime
from decimal import Decimal, ROUND_DOWN
from config import settings
from notify import send_slack
from api_client import place_order, get_executions_by_order

logger = logging.getLogger(__name__)


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
def handle_order_result(
    response, order_id, symbol, jpy, amount, current_price, purchase_type, db
):
    executed_price = None
    executed_time = None

    if response.status_code == 200:
        # 約定情報取得を試みる
        if order_id:
            executions = get_executions_by_order(order_id)
            if executions:
                try:
                    total = sum(
                        Decimal(e["price"]) * Decimal(e["size"]) for e in executions
                    )
                    size = sum(Decimal(e["size"]) for e in executions)
                    executed_price = (total / size).quantize(Decimal("0.01"))
                    executed_time = executions[0]["timestamp"]
                except Exception as e:
                    logger.warning(f"約定情報の計算失敗: {e}")

            if executed_price and executed_time:
                log_msg = (
                    f"{symbol} 注文成功 / 数量: {amount} / 約定価格: {executed_price}円"
                )

            else:
                log_msg = f"{symbol} 注文成功 / 数量: {amount}（※約定情報取得失敗）"

        logger.info(log_msg)
        send_slack(log_msg)

        db.record_purchase_history(
            symbol,
            jpy,
            amount,
            purchase_type,
            current_price,
            executed_price=executed_price,
            executed_time=executed_time,
        )
    else:
        error_msg = f"{symbol}注文失敗: {response.status_code} {response.text}"
        logger.error(error_msg)
        send_slack(error_msg)


# --- 基本購入を実行する ---
def execute_base_purchase(current_prices, db, dry_run=False):
    if settings is None:
        logger.error("設定が未設定のため、基本購入をスキップします")
        return

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
        if not last_time or (now.date() - last_time.date()).days >= interval_days:
            min_unit = Decimal(str(conf["min_order_amount"]))
            amount = (Decimal(jpy) / current_price).quantize(
                min_unit, rounding=ROUND_DOWN
            )
            if dry_run:
                logger.info(f"{symbol} テスト注文 / 数量: {amount}")
                send_slack(f"{symbol} テスト注文 / 数量: {amount}")
                continue

            response, order_id = place_order(symbol, amount)
            handle_order_result(
                response, order_id, symbol, jpy, amount, current_price, "base", db
            )
        else:
            logger.info(f"{symbol} 基本購入スキップ（{interval_days}日未満）")


# --- 購入スコアを計算する ---
def calculate_purchase_score(
    symbol, conf, current_price, last_price, avg_price, rsi, db
):
    score = 0
    max_score = 3  # 前回比, SMA乖離, RSI の3項目
    min_score = conf.get("min_score", 2)  # 購入判定に使われるしきい値
    reasons = []

    if last_price:
        change = (current_price - last_price) / last_price * Decimal("100")
        if change <= Decimal(conf.get("price_drop_percent", -3)):
            score += 1
            reasons.append(f"前回比 {change:.2f}% (+1)")
        else:
            reasons.append(f"前回比 {change:.2f}% (±0)")
    else:
        reasons.append("前回価格なし")

    if avg_price:
        sma_dev = (current_price - avg_price) / avg_price * Decimal("100")
        passed = sma_dev <= Decimal(conf.get("sma_deviation", -5))
        reasons.append(f"SMA乖離 {sma_dev:.2f}% ({'+1' if passed else '±0'})")
        if passed:
            score += 1

    if rsi is not None:
        threshold = Decimal(conf.get("rsi_threshold", 30))
        passed = rsi <= threshold
        reasons.append(f"RSI {rsi} ≤ {threshold} ({'+1' if passed else '±0'})")
        if passed:
            score += 1
    else:
        reasons.append("RSI未取得")

    if is_long_term_downtrend(symbol, db):
        score -= 1
        reasons.append("長期トレンド悪化（-1）")
    else:
        reasons.append("長期トレンド良好（±0）")

    reasons.insert(0, f"スコア={score}/{max_score}（条件:{min_score}以上）")

    return score, reasons


def evaluate_add_purchase(symbol, conf, current_price, db, dry_run=False):
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    rows = db.get_purchase_history(symbol, limit=1, before_date=today)
    last_price = Decimal(rows[0][3]) if rows else None

    avg_price = get_30day_average(symbol, db)
    rsi = calculate_rsi(symbol, db)

    score, reasons = calculate_purchase_score(
        symbol, conf, current_price, last_price, avg_price, rsi, db
    )
    should_buy = score >= conf.get("min_score", 2)
    return should_buy, reasons


def perform_add_purchase(symbol, conf, current_price, db, reasons, dry_run=False):
    jpy = conf.get("jpy", 0)
    min_unit = Decimal(str(conf["min_order_amount"]))
    amount = (Decimal(jpy) / current_price).quantize(min_unit, rounding=ROUND_DOWN)

    level = "DRY-RUN" if dry_run else "BUY"
    reason_msg = f"{symbol} 追加購入実行: " + " / ".join(reasons)
    order_msg = (
        f"{symbol} テスト注文: {amount}" if dry_run else f"{symbol} 注文: {amount}"
    )

    logger.info(reason_msg)

    if dry_run:
        logger.info(order_msg)
        send_slack(order_msg, level=level)
        return

    response = place_order(symbol, amount)
    handle_order_result(response, symbol, jpy, amount, current_price, "add", db)


def execute_add_purchase_flow(current_prices, db, dry_run=False):
    if not settings or not settings["add_purchase"].get("enabled", False):
        logger.info("追加購入は設定で無効になっています。")
        return

    logger.info("追加購入を実行します。")

    for symbol, conf in settings["add_purchase"]["settings"].items():
        price = current_prices.get(symbol)
        if price is None:
            logger.info(f"{symbol} の価格取得に失敗したためスキップします。")
            continue

        jpy = conf.get("jpy", 0)
        if jpy <= 0:
            logger.info(f"{symbol} は jpy=0 のためスキップされました。")
            continue

        should_buy, reasons = evaluate_add_purchase(symbol, conf, price, db)
        if should_buy:
            perform_add_purchase(symbol, conf, price, db, reasons, dry_run=dry_run)
        else:
            logger.info(f"{symbol} 追加購入条件を満たしません（{', '.join(reasons)}）")
