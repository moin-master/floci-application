"""Lambda: runs every hour. Reads the stock table, and for every ENABLED ticker writes a fresh (mock)
price into Redis, kept for that ticker's own cache_minutes. Disabled tickers are skipped."""
import json
import logging
import os
import random
from datetime import datetime, timezone

import boto3
import redis

log = logging.getLogger()
log.setLevel(logging.INFO)

BASE_PRICES = {"AAPL": 190.0, "MSFT": 420.0, "AMZN": 180.0, "GOOGL": 170.0, "TSLA": 250.0}


def fetch_price(symbol):
    """Mock price source. Replace this function to call a real market-data API."""
    return round(BASE_PRICES.get(symbol, 100.0) * random.uniform(0.97, 1.03), 2)


def handler(event, context):
    table = boto3.resource("dynamodb").Table(os.environ.get("DYNAMODB_TABLE", "stock"))
    cache = redis.Redis(
        host=os.environ["REDIS_HOST"],
        port=int(os.environ["REDIS_PORT"]),
        socket_timeout=5,
    )
    now = datetime.now(timezone.utc).isoformat()
    updated = skipped = 0
    for item in table.scan()["Items"]:
        symbol = item["ticker"]
        if not item.get("enabled"):
            skipped += 1
            continue
        doc = {"symbol": symbol, "price": fetch_price(symbol), "currency": "USD", "updated_at": now}
        cache.set(f"price:{symbol}", json.dumps(doc), ex=int(item["cache_minutes"]) * 60)
        updated += 1
    log.info("updated %d prices, skipped %d disabled", updated, skipped)
    return {"updated": updated, "skipped": skipped}
