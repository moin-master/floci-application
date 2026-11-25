"""End-to-end tests. They run against the DEPLOYED stack in Floci (run scripts/deploy.sh first).

Every test talks to the real thing: the ALB, the ECS tasks, the Lambda, Redis and CloudWatch Logs.
"""
import json
import os
import time

import boto3
import pytest
import redis
import requests

FLOCI = os.environ.get("FLOCI_URL", "http://floci:4566")
ALB_URL = os.environ.get("ALB_URL", "http://floci:80")  # Floci's ALB listener
ALB_HOST = os.environ["ALB_DNS"]  # Floci picks the load balancer by its DNS name (Host header)
SYMBOLS = {"AAPL", "MSFT", "AMZN", "GOOGL", "TSLA"}


def aws(service):
    return boto3.client(service, endpoint_url=FLOCI, region_name="us-east-1",
                        aws_access_key_id="test", aws_secret_access_key="test")


def api(path):
    return requests.get(f"{ALB_URL}{path}", headers={"Host": ALB_HOST}, timeout=5)


def run_updater():
    resp = aws("lambda").invoke(FunctionName="stock-updater", Payload=b"{}")
    body = json.loads(resp["Payload"].read())
    assert "FunctionError" not in resp, body
    return body


def wait_for(check, seconds=90, what="condition"):
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            if check():
                return
        except Exception:
            pass
        time.sleep(2)
    pytest.fail(f"timed out waiting for {what}")


def log_messages(group):
    events = aws("logs").filter_log_events(logGroupName=group, limit=500)["events"]
    return "\n".join(e["message"] for e in events)


@pytest.fixture(scope="session", autouse=True)
def stack_is_ready():
    """Wait until the API answers through the ALB, then seed prices with the Lambda."""
    wait_for(lambda: api("/health").status_code == 200, what="API healthy behind the ALB")
    run_updater()


# ---------- 1. Infrastructure exists ----------
class TestInfrastructure:
    def test_ecr_has_the_api_image(self):
        images = aws("ecr").describe_images(repositoryName="stock-api")["imageDetails"]
        assert any("latest" in i.get("imageTags", []) for i in images)

    def test_ecs_runs_two_tasks_per_az(self):
        svcs = aws("ecs").describe_services(cluster="stock", services=["stock-api-a", "stock-api-b"])["services"]
        assert len(svcs) == 2
        assert all(s["status"] == "ACTIVE" and s["desiredCount"] == 2 and s["runningCount"] == 2 for s in svcs)

    def test_two_subnets_in_two_azs(self):
        subnets = aws("ec2").describe_subnets(
            Filters=[{"Name": "tag:Name", "Values": ["stock-private-us-east-1a", "stock-private-us-east-1b"]}])["Subnets"]
        assert {s["AvailabilityZone"] for s in subnets} == {"us-east-1a", "us-east-1b"}

    def test_redis_has_primary_and_replica(self):
        group = aws("elasticache").describe_replication_groups(
            ReplicationGroupId="stock-redis")["ReplicationGroups"][0]
        assert len(group["MemberClusters"]) == 2
        assert group["MultiAZ"] == "enabled"

    def test_dynamodb_table_has_the_tickers(self):
        items = aws("dynamodb").scan(TableName="stock")["Items"]
        assert {i["ticker"]["S"] for i in items} == SYMBOLS
        for i in items:
            assert i["enabled"]["BOOL"] is True
            assert 30 <= int(i["cache_minutes"]["N"]) <= 60

    def test_lambda_is_scheduled_hourly(self):
        rules = aws("events").list_rules(NamePrefix="stock-hourly")["Rules"]
        assert rules and rules[0]["ScheduleExpression"] == "rate(1 hour)"
        targets = aws("events").list_targets_by_rule(Rule=rules[0]["Name"])["Targets"]
        assert targets and targets[0]["Arn"].endswith(":function:stock-updater")


# ---------- 2. The API behaves correctly ----------
class TestApi:
    def test_health(self):
        r = api("/health")
        assert r.status_code == 200 and r.json() == {"status": "ok"}

    def test_get_price(self):
        r = api("/stocks/AAPL")
        assert r.status_code == 200
        body = r.json()
        assert body["symbol"] == "AAPL"
        assert body["currency"] == "USD"
        assert body["price"] > 0
        assert body["updated_at"]

    def test_symbol_is_case_insensitive(self):
        assert api("/stocks/msft").json()["symbol"] == "MSFT"

    def test_unknown_symbol_is_404(self):
        assert api("/stocks/NOPE").status_code == 404

    def test_list_symbols(self):
        assert set(api("/stocks").json()["symbols"]) == SYMBOLS


# ---------- 3. Lambda -> Redis -> API data flow ----------
class TestDataFlow:
    def test_lambda_updates_every_symbol(self):
        assert run_updater() == {"updated": 5, "skipped": 0}
        for symbol in SYMBOLS:
            assert api(f"/stocks/{symbol}").status_code == 200

    def test_new_lambda_run_refreshes_the_price_the_api_serves(self):
        before = api("/stocks/TSLA").json()["updated_at"]
        time.sleep(1.1)
        run_updater()
        after = api("/stocks/TSLA").json()["updated_at"]
        assert after > before

    def test_price_is_stored_in_redis_with_a_ttl(self):
        cache = redis.Redis(host="floci", port=6379, decode_responses=True, socket_timeout=5)
        ttl = cache.ttl("price:AAPL")
        assert 0 < ttl <= 60 * 60  # cache_minutes is at most 60
        assert json.loads(cache.get("price:AAPL"))["symbol"] == "AAPL"


# ---------- 4. Logs reach CloudWatch ----------
class TestLogs:
    def test_lambda_logs(self):
        run_updater()
        wait_for(lambda: "updated 5 prices" in log_messages("/aws/lambda/stock-updater"),
                 what="Lambda log line")

    def test_api_logs(self):
        api("/stocks/AMZN")
        wait_for(lambda: "served price for AMZN" in log_messages("/ecs/stock-api"),
                 what="API log line")


# ---------- 4b. DynamoDB controls the API ----------
def set_enabled(ticker, value):
    aws("dynamodb").update_item(TableName="stock", Key={"ticker": {"S": ticker}},
                                UpdateExpression="SET enabled = :v", ExpressionAttributeValues={":v": {"BOOL": value}})


def cache_minutes(ticker):
    item = aws("dynamodb").get_item(TableName="stock", Key={"ticker": {"S": ticker}})["Item"]
    return int(item["cache_minutes"]["N"])


class TestDynamoControl:
    def test_disabled_ticker_is_refused_and_hidden(self):
        set_enabled("TSLA", False)
        try:
            assert api("/stocks/TSLA").status_code == 403
            assert "TSLA" not in api("/stocks").json()["symbols"]
            assert api("/stocks/AAPL").status_code == 200  # others are not affected
        finally:
            set_enabled("TSLA", True)
        assert api("/stocks/TSLA").status_code == 200

    def test_lambda_skips_disabled_tickers(self):
        set_enabled("GOOGL", False)
        try:
            assert run_updater() == {"updated": 4, "skipped": 1}
        finally:
            set_enabled("GOOGL", True)
        assert run_updater() == {"updated": 5, "skipped": 0}

    def test_cache_miss_fills_the_cache_for_the_ticker_period(self):
        cache = redis.Redis(host="floci", port=6379, decode_responses=True, socket_timeout=5)
        cache.delete("price:MSFT")
        assert api("/stocks/MSFT").status_code == 200  # miss: API fetches and caches
        ttl = cache.ttl("price:MSFT")
        minutes = cache_minutes("MSFT")
        assert minutes * 60 - 30 <= ttl <= minutes * 60

    def test_cache_hit_returns_the_cached_price(self):
        first = api("/stocks/AMZN").json()
        assert api("/stocks/AMZN").json() == first

    def test_changing_cache_minutes_changes_the_next_cache_period(self):
        ddb, cache = aws("dynamodb"), redis.Redis(host="floci", port=6379, decode_responses=True, socket_timeout=5)
        old = cache_minutes("AAPL")
        new = 31 if old != 31 else 32
        ddb.update_item(TableName="stock", Key={"ticker": {"S": "AAPL"}}, UpdateExpression="SET cache_minutes = :m",
                        ExpressionAttributeValues={":m": {"N": str(new)}})
        try:
            cache.delete("price:AAPL")
            api("/stocks/AAPL")
            assert new * 60 - 30 <= cache.ttl("price:AAPL") <= new * 60
        finally:
            ddb.update_item(TableName="stock", Key={"ticker": {"S": "AAPL"}}, UpdateExpression="SET cache_minutes = :m",
                            ExpressionAttributeValues={":m": {"N": str(old)}})


# ---------- 5. Resilience ----------
class TestResilience:
    def test_api_survives_losing_one_task(self):
        ecs = aws("ecs")
        task = ecs.list_tasks(cluster="stock")["taskArns"][0]
        ecs.stop_task(cluster="stock", task=task, reason="e2e test")

        # the other task keeps serving...
        for _ in range(5):
            assert api("/stocks/AAPL").status_code == 200
        # ...and ECS replaces the stopped task: it disappears and we are back to 2 running
        def replaced():
            arns = ecs.list_tasks(cluster="stock")["taskArns"]
            if task in arns or len(arns) != 4:
                return False
            tasks = ecs.describe_tasks(cluster="stock", tasks=arns)["tasks"]
            return all(t["lastStatus"] == "RUNNING" for t in tasks)
        wait_for(replaced, what="ECS to replace the stopped task")
        wait_for(lambda: api("/health").status_code == 200, what="API healthy again")
