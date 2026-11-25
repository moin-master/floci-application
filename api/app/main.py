"""Stock Price API.

Every request: 1) DynamoDB says whether the ticker exists and is enabled, and for how long to cache it,
2) Redis (ElastiCache) holds the price, 3) on a cache miss we fetch a price and cache it for that period.
"""
import json
import logging
import os
import random
from datetime import datetime, timezone

import boto3
import redis
from fastapi import FastAPI, HTTPException

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("stock-api")

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
TABLE = os.environ.get("DYNAMODB_TABLE", "stock")
BASE_PRICES = {"AAPL": 190.0, "MSFT": 420.0, "AMZN": 180.0, "GOOGL": 170.0, "TSLA": 250.0}

app = FastAPI(title="Stock Price API")
cache = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True, socket_timeout=3)
table = boto3.resource("dynamodb").Table(TABLE)  # AWS_ENDPOINT_URL points it at Floci locally


def fetch_price(symbol):
    """Mock price source. Replace this function to call a real market-data API."""
    base = BASE_PRICES.get(symbol, 100.0)
    return round(base * random.uniform(0.97, 1.03), 2)


@app.get("/health")
def health():
    """Used by the load balancer. Also checks that the cache is reachable."""
    try:
        cache.ping()
    except redis.RedisError as exc:
        log.error("cache unreachable: %s", exc)
        raise HTTPException(status_code=503, detail="cache unreachable")
    return {"status": "ok"}


@app.get("/stocks")
def list_stocks():
    """Only enabled tickers."""
    items = table.scan()["Items"]
    return {"symbols": sorted(i["ticker"] for i in items if i.get("enabled"))}


@app.get("/stocks/{symbol}")
def get_stock(symbol: str):
    symbol = symbol.upper()
    item = table.get_item(Key={"ticker": symbol}).get("Item")  # 1) the database decides first
    if item is None:
        raise HTTPException(status_code=404, detail=f"unknown ticker {symbol}")
    if not item.get("enabled"):
        log.info("refused %s: disabled", symbol)
        raise HTTPException(status_code=403, detail=f"{symbol} is disabled")

    raw = cache.get(f"price:{symbol}")  # 2) then the cache
    if raw is not None:
        log.info("served price for %s (cache hit)", symbol)
        return json.loads(raw)

    doc = {  # 3) cache miss: fetch and keep it for this ticker's cache period
        "symbol": symbol,
        "price": fetch_price(symbol),
        "currency": "USD",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    cache.set(f"price:{symbol}", json.dumps(doc), ex=int(item["cache_minutes"]) * 60)
    log.info("served price for %s (cache miss, cached %s min)", symbol, item["cache_minutes"])
    return doc
