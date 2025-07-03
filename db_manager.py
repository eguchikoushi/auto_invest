# DB処理モジュール

import os
import sqlite3
import datetime
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

DB_FILENAME = "history.db"


class DBManager:
    def __init__(self, data_dir):
        self.db_path = os.path.join(data_dir, DB_FILENAME)

    # --- DB初期化 ---
    def ensure_initialized(self):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS price_history (
                    symbol TEXT NOT NULL,
                    date TEXT NOT NULL,
                    price TEXT NOT NULL,
                    PRIMARY KEY (symbol, date)
                )
            """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS purchase_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    purchase_type TEXT NOT NULL,
                    date TEXT NOT NULL,
                    jpy_amount TEXT NOT NULL,
                    crypto_amount TEXT NOT NULL,
                    price TEXT NOT NULL,
                    executed_price TEXT NOT NULL,
                    executed_time TEXT NOT NULL
                )
            """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS short_term_price (
                    symbol TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    price TEXT NOT NULL,
                    PRIMARY KEY (symbol, timestamp)
                )
                """
            )

            conn.commit()
        except Exception as e:
            handle_db_error(e, context="DB初期化処理")
        finally:
            if conn:
                conn.close()

    # --- 指定通貨の評価額推移を記録する ---
    def record_price_history(self, symbol, current_price, date=None):
        date_str = date or datetime.datetime.now().strftime("%Y-%m-%d")
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute(
                """
                INSERT OR REPLACE INTO price_history (symbol, date, price)
                VALUES (?, ?, ?)
            """,
                (symbol, date_str, str(current_price)),
            )
            conn.commit()
        except Exception as e:
            handle_db_error(e, context="評価額推移記録処理")
        finally:
            if conn:
                conn.close()

    # --- 指定通貨の評価額推移を取得する ---
    def get_price_history(self, symbol, days):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute(
                """
                SELECT date, price FROM price_history
                WHERE symbol = ? ORDER BY date DESC LIMIT ?
            """,
                (symbol, days),
            )
            rows = cur.fetchall()
            return [(r[0], Decimal(r[1])) for r in reversed(rows)]
        except Exception as e:
            handle_db_error(e, context="評価額推移取得処理")
            return []
        finally:
            if conn:
                conn.close()

    def record_short_term_price(self, symbol, price, timestamp=None):
        timestamp = timestamp or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute(
                """
                INSERT OR REPLACE INTO short_term_price (symbol, timestamp, price)
                VALUES (?, ?, ?)
                """,
                (symbol, timestamp, str(price)),
            )
            conn.commit()
        except Exception as e:
            handle_db_error(e, context="短期価格記録処理")
        finally:
            if conn:
                conn.close()

    # --- 指定通貨の購入履歴を記録する ---
    def record_purchase_history(
        self,
        symbol,
        jpy_amount,
        crypto_amount,
        purchase_type,
        current_price,
        executed_price=None,
        executed_time=None,
    ):
        date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO purchase_history (
                    symbol,
                    purchase_type,
                    date,
                    jpy_amount,
                    crypto_amount,
                    price,
                    executed_price,
                    executed_time
                )VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    symbol,
                    purchase_type,
                    date,
                    str(jpy_amount),
                    str(crypto_amount),
                    str(current_price),
                    str(executed_price),
                    str(executed_time),
                ),
            )
            conn.commit()
        except Exception as e:
            handle_db_error(e, context="購入履歴記録処理")
        finally:
            if conn:
                conn.close()

    # --- 指定通貨の購入履歴を取得する ---
    def get_purchase_history(
        self, symbol, limit=30, before_date=None, purchase_type=None
    ):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()

            query = """
                SELECT date, crypto_amount, jpy_amount, price
                FROM purchase_history
                WHERE symbol = ?
            """
            params = [symbol]

            if purchase_type:
                query += " AND purchase_type = ?"
                params.append(purchase_type)

            if before_date:
                query += " AND date < ?"
                params.append(before_date)

            query += " ORDER BY date DESC LIMIT ?"
            params.append(limit)

            cur.execute(query, params)
            return cur.fetchall()
        except Exception as e:
            handle_db_error(e, context="購入履歴取得処理")
            return []
        finally:
            if conn:
                conn.close()

    # --- 最新の購入レコードを取得 ---
    def get_last_purchase(self, symbol, purchase_type=None):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()

            query = """
                SELECT date, crypto_amount, jpy_amount, price
                FROM purchase_history
                WHERE symbol = ?
            """
            params = [symbol]

            if purchase_type:
                query += " AND purchase_type = ?"
                params.append(purchase_type)

            query += " ORDER BY date DESC LIMIT 1"

            cur.execute(query, params)
            return cur.fetchone()
        except Exception as e:
            handle_db_error(e, context="最新購入取得処理")
            return None
        finally:
            if conn:
                conn.close()

    # --- 最新の短期価格レコードを取得 ---
    def get_latest_short_term_prices(self, symbol, limit=2):
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute(
                """
                SELECT timestamp, price FROM short_term_price
                WHERE symbol = ?
                ORDER BY timestamp DESC LIMIT ?
                """,
                (symbol, limit),
            )
            rows = cur.fetchall()
            return [(r[0], Decimal(r[1])) for r in reversed(rows)]
        except Exception as e:
            handle_db_error(e, context="短期価格（最新）取得処理")
            return []
        finally:
            if conn:
                conn.close()


# --- エラーハンドラ ---
def handle_db_error(e, context=""):
    if isinstance(e, sqlite3.OperationalError):
        logger.error(f"[OperationalError] {context}: {e}")
    elif isinstance(e, sqlite3.IntegrityError):
        logger.error(f"[IntegrityError] {context}: {e}")
    elif isinstance(e, sqlite3.DatabaseError):
        logger.error(f"[DatabaseError] {context}: {e}")
    else:
        logger.error(f"[UnexpectedError] {context}: {e}")
