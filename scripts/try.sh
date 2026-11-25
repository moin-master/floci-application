#!/usr/bin/env bash
# Manual try-out helper: each command prints the plain curl it runs, so you can copy it.
# Needs a deployed stack (scripts/deploy.sh). Usage: scripts/try.sh <command> [args]
cd "$(dirname "$0")/.."
E=localhost:4566
ALB=$(scripts/tf.sh output -raw alb_dns 2>/dev/null)
AUTH() { echo "Authorization: AWS4-HMAC-SHA256 Credential=test/20260101/us-east-1/$1/aws4_request"; }
ddb()  { curl -s -X POST $E/ -H "Content-Type: application/x-amz-json-1.0" -H "$(AUTH dynamodb)" -H "X-Amz-Target: DynamoDB_20120810.$1" -d "$2"; }
api()  { echo "\$ curl -i -H \"Host: \$ALB\" localhost:8080$1"; curl -s -i -H "Host: $ALB" "localhost:8080$1" | sed -n '1p;/^{/p;/^\[/p' | tr -d '\r'; echo; }
redis() { docker exec floci-aws-valkey-stock-redis valkey-cli "$@"; }
T=${2:-}; T=$(echo "$T" | tr a-z A-Z)

case "${1:-help}" in
  health)   api /health ;;
  stocks)   api /stocks ;;
  price)    api "/stocks/${T:?usage: try.sh price AAPL}" ;;
  table)    ddb Scan '{"TableName":"stock"}' | python3 -c '
import json,sys
print("%-6s %-8s %s" % ("TICKER","ENABLED","CACHE_MINUTES"))
for i in sorted(json.load(sys.stdin)["Items"], key=lambda i: i["ticker"]["S"]):
    print("%-6s %-8s %s" % (i["ticker"]["S"], i["enabled"]["BOOL"], i["cache_minutes"]["N"]))' ;;
  disable|enable)
    v=true; [ "$1" = disable ] && v=false
    ddb UpdateItem "{\"TableName\":\"stock\",\"Key\":{\"ticker\":{\"S\":\"${T:?usage: try.sh $1 AAPL}\"}},\"UpdateExpression\":\"SET enabled = :v\",\"ExpressionAttributeValues\":{\":v\":{\"BOOL\":$v}}}" >/dev/null
    echo "$T enabled=$v" ;;
  cache-minutes)
    ddb UpdateItem "{\"TableName\":\"stock\",\"Key\":{\"ticker\":{\"S\":\"${T:?usage: try.sh cache-minutes AAPL 45}\"}},\"UpdateExpression\":\"SET cache_minutes = :m\",\"ExpressionAttributeValues\":{\":m\":{\"N\":\"${3:?minutes}\"}}}" >/dev/null
    echo "$T cache_minutes=$3 (applies the next time the price is cached)" ;;
  ttl)      s=$(redis ttl "price:${T:?usage: try.sh ttl AAPL}"); echo "price:$T expires in ${s}s (~$((s/60)) min)  [-2 = not cached]" ;;
  forget)   redis del "price:${T:?usage: try.sh forget AAPL}" >/dev/null; echo "price:$T removed from the cache; the next request is a cache miss" ;;
  updater)  echo "\$ invoke Lambda stock-updater"; curl -s -X POST -H "$(AUTH lambda)" -d '{}' $E/2015-03-31/functions/stock-updater/invocations; echo ;;
  demo)
    echo "== 1. the table (DynamoDB decides first)"; "$0" table
    echo; echo "== 2. disable TSLA -> the API must refuse it"; "$0" disable TSLA; "$0" price TSLA; "$0" stocks
    echo; echo "== 3. enable it again"; "$0" enable TSLA; "$0" price TSLA
    echo; echo "== 4. cache miss then hit, and the cache period"; "$0" forget MSFT; "$0" price MSFT; "$0" ttl MSFT; "$0" price MSFT ;;
  *) cat <<USAGE
Commands (T = ticker such as AAPL):
  health | stocks | price T      call the API through the load balancer
  table                          show the DynamoDB table: ticker, enabled, cache_minutes
  disable T | enable T           flip the enabled flag in DynamoDB
  cache-minutes T N              set the cache period in minutes (N = 30..60 in the seed data)
  ttl T | forget T               show / clear the Redis cache entry for T
  updater                        run the hourly Lambda now
  demo                           run a short guided scenario
USAGE
  ;;
esac
