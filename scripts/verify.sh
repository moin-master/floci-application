#!/usr/bin/env bash
# Check that every piece of the infrastructure exists and works. Read-only.
cd "$(dirname "$0")/.."
E=localhost:4566
pass=0; fail=0
ok()   { echo "  PASS  $1"; pass=$((pass+1)); }
bad()  { echo "  FAIL  $1"; fail=$((fail+1)); }
chk()  { if [ "$2" = "1" ]; then ok "$1"; else bad "$1"; fi; }
# call <service> <X-Amz-Target> <json body>   (JSON-protocol AWS APIs)
call() { curl -s -X POST $E/ -H "Content-Type: application/x-amz-json-1.1" \
  -H "Authorization: AWS4-HMAC-SHA256 Credential=test/20260101/us-east-1/$1/aws4_request" \
  -H "X-Amz-Target: $2" -d "$3"; }
# DynamoDB uses JSON protocol 1.0 (the others above use 1.1)
ddb()  { curl -s -X POST $E/ -H "Content-Type: application/x-amz-json-1.0" \
  -H "Authorization: AWS4-HMAC-SHA256 Credential=test/20260101/us-east-1/dynamodb/aws4_request" \
  -H "X-Amz-Target: DynamoDB_20120810.$1" -d "$2"; }
has()  { grep -q "$1" <<<"$2" && echo 1 || echo 0; }

echo "Floci"
chk "Floci is healthy" "$(has '"version"' "$(curl -s $E/_floci/health)")"

echo "ECR"
r=$(call ecr AmazonEC2ContainerRegistry_V20150921.DescribeImages '{"repositoryName":"stock-api"}')
chk "image stock-api:latest is pushed" "$(has '"latest"' "$r")"

echo "ECS"
r=$(call ecs AmazonEC2ContainerServiceV20141113.DescribeServices '{"cluster":"stock","services":["stock-api-a","stock-api-b"]}')
chk "services stock-api-a and stock-api-b are ACTIVE" "$([ "$(grep -o '"status":"ACTIVE"' <<<"$r" | wc -l)" -ge 2 ] && echo 1 || echo 0)"
chk "4 tasks running (2 per AZ)" "$([ "$(grep -o '"runningCount":2' <<<"$r" | wc -l)" -ge 2 ] && echo 1 || echo 0)"

echo "DynamoDB"
r=$(ddb DescribeTable '{"TableName":"stock"}')
chk "table stock is ACTIVE" "$(has '"ACTIVE"' "$r")"
r=$(ddb Scan '{"TableName":"stock"}')
chk "5 tickers with enabled flag and cache_minutes" "$([ "$(grep -o '"cache_minutes"' <<<"$r" | wc -l)" -ge 5 ] && echo 1 || echo 0)"

echo "Lambda"
r=$(curl -s $E/2015-03-31/functions/stock-updater -H "Authorization: AWS4-HMAC-SHA256 Credential=test/20260101/us-east-1/lambda/aws4_request")
chk "function stock-updater exists" "$(has '"FunctionName":"stock-updater"' "$r")"

echo "EventBridge"
r=$(call events AWSEvents.ListRules '{}')
chk "hourly rule rate(1 hour)" "$(has 'rate(1 hour)' "$r")"

echo "CloudWatch Logs"
r=$(call logs Logs_20140328.DescribeLogGroups '{}')
chk "log group /ecs/stock-api" "$(has '/ecs/stock-api' "$r")"
chk "log group /aws/lambda/stock-updater" "$(has '/aws/lambda/stock-updater' "$r")"

echo "End to end"
ALB=$(scripts/tf.sh output -raw alb_dns 2>/dev/null)
chk "GET /health through the ALB" "$(has '"ok"' "$(curl -s -m 5 -H "Host: $ALB" localhost:8080/health)")"
chk "GET /stocks/AAPL returns a price" "$(has '"price"' "$(curl -s -m 5 -H "Host: $ALB" localhost:8080/stocks/AAPL)")"
chk "unknown symbol returns 404" "$([ "$(curl -s -o /dev/null -w '%{http_code}' -m 5 -H "Host: $ALB" localhost:8080/stocks/NOPE)" = 404 ] && echo 1 || echo 0)"

echo; echo "$pass passed, $fail failed"; [ "$fail" = 0 ]
