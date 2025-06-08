import os
import json
import logging
import hmac
import hashlib
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


# --- 設定ロード ---
settings = load_json(SETTINGS_PATH)

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
