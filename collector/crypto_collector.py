import logging
from requests import Session
from requests.exceptions import ConnectionError, Timeout, TooManyRedirects
from dotenv import load_dotenv
import schedule
import json
import os
import time
import psycopg2

# ========================
# CONFIG LOGGING
# ========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)

# ========================
# LOAD ENV
# ========================
load_dotenv()

URL = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"

PARAMS = {
    "limit": 100,
    "convert": "USD",
}

HEADERS = {
    "Accepts": "application/json",
    "X-CMC_PRO_API_KEY": os.getenv("CMC_API_KEY"),
}

session = Session()
session.headers.update(HEADERS)

DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")


def get_connection():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
    )


def create_table():
    try:
        logger.info("Creating table if not exists...")

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS crypto_quotes (
                id           SERIAL PRIMARY KEY,
                symbol       VARCHAR(20),
                name         VARCHAR(100),
                cmc_rank     INTEGER,
                price        NUMERIC,
                volume_24h   NUMERIC,
                market_cap   NUMERIC,
                pct_1h       NUMERIC,
                pct_24h      NUMERIC,
                pct_7d       NUMERIC,
                pct_30d      NUMERIC,
                collected_at TIMESTAMP DEFAULT NOW()
            );
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_crypto_symbol_time
            ON crypto_quotes (symbol, collected_at DESC);
        """)

        conn.commit()
        cursor.close()
        conn.close()

        logger.info("Table ready.")

    except Exception as e:
        logger.error(f"Error creating table: {e}")


def save_coins(coins):
    try:
        logger.info(f"Saving {len(coins)} coins...")

        conn = get_connection()
        cursor = conn.cursor()

        query = """
            INSERT INTO crypto_quotes
                (symbol, name, cmc_rank, price, volume_24h, market_cap,
                 pct_1h, pct_24h, pct_7d, pct_30d)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        rows = []
        for coin in coins:
            usd = coin["quote"]["USD"]
            rows.append((
                coin["symbol"],
                coin["name"],
                coin["cmc_rank"],
                usd["price"],
                usd["volume_24h"],
                usd["market_cap"],
                usd.get("percent_change_1h"),
                usd.get("percent_change_24h"),
                usd.get("percent_change_7d"),
                usd.get("percent_change_30d"),
            ))

        cursor.executemany(query, rows)
        conn.commit()

        cursor.close()
        conn.close()

        logger.info(f"{len(rows)} coins saved successfully.")

    except Exception as e:
        logger.error(f"Error saving coins: {e}")


def fetch_and_store():
    try:
        logger.info("Fetching data from CoinMarketCap...")

        response = session.get(URL, params=PARAMS)
        logger.info(f"Status code: {response.status_code}")

        data = json.loads(response.text)

        if data.get("status", {}).get("error_code") != 0:
            logger.error(f"API error: {data['status'].get('error_message')}")
            return

        if "data" in data:
            save_coins(data["data"])
        else:
            logger.error(f"Unexpected response: {data}")

    except (ConnectionError, Timeout, TooManyRedirects) as e:
        logger.error(f"Request error: {e}")


if __name__ == "__main__":
    logger.info("Starting crypto collector...")

    create_table()
    fetch_and_store()

    schedule.every(5).minutes.do(fetch_and_store)

    logger.info("Collector running every 5 minutes...")

    while True:
        schedule.run_pending()
        time.sleep(1)