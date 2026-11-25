# Manual testing (plain curl)

Deploy first (`scripts/deploy.sh`). Floci listens on `localhost:4566`. `scripts/try.sh demo` wraps most of these commands.

## 0. Setup (once per terminal)

```bash
# header for the "query style" AWS APIs (EC2, load balancer, ElastiCache). JSON-style APIs (DynamoDB, ECS, Lambda, ...) need none in Floci.
SIG="Authorization: AWS4-HMAC-SHA256 Credential=test/20260101/us-east-1"

# the load balancer name changes on every deploy: ask Floci for it
ALB=$(curl -s "localhost:4566/?Action=DescribeLoadBalancers&Version=2015-12-01" -H "$SIG/elasticloadbalancing/aws4_request" | grep -o "<DNSName>[^<]*" | head -1 | cut -d'>' -f2)
echo $ALB
```

## 1. The API (through the load balancer)

```bash
curl -i -H "Host: $ALB" localhost:8080/health
curl -i -H "Host: $ALB" localhost:8080/stocks             # enabled tickers only
curl -i -H "Host: $ALB" localhost:8080/stocks/AAPL        # 200 {"symbol","price","currency","updated_at"}
curl -i -H "Host: $ALB" localhost:8080/stocks/nope        # 404 unknown ticker
```

## 2. DynamoDB controls the API

```bash
# look at the table: ticker, enabled, cache_minutes
curl -s -X POST localhost:4566/ -H "Content-Type: application/x-amz-json-1.0" \
  -H "X-Amz-Target: DynamoDB_20120810.Scan" -d '{"TableName":"stock"}'

# disable TSLA ...
curl -s -X POST localhost:4566/ -H "Content-Type: application/x-amz-json-1.0" \
  -H "X-Amz-Target: DynamoDB_20120810.UpdateItem" \
  -d '{"TableName":"stock","Key":{"ticker":{"S":"TSLA"}},"UpdateExpression":"SET enabled = :v","ExpressionAttributeValues":{":v":{"BOOL":false}}}'
curl -i -H "Host: $ALB" localhost:8080/stocks/TSLA        # 403 {"detail":"TSLA is disabled"}
curl -s -H "Host: $ALB" localhost:8080/stocks              # TSLA is gone from the list

# ... and enable it again
curl -s -X POST localhost:4566/ -H "Content-Type: application/x-amz-json-1.0" \
  -H "X-Amz-Target: DynamoDB_20120810.UpdateItem" \
  -d '{"TableName":"stock","Key":{"ticker":{"S":"TSLA"}},"UpdateExpression":"SET enabled = :v","ExpressionAttributeValues":{":v":{"BOOL":true}}}'

# change how long AAPL is cached (45 minutes); used the next time the price is cached
curl -s -X POST localhost:4566/ -H "Content-Type: application/x-amz-json-1.0" \
  -H "X-Amz-Target: DynamoDB_20120810.UpdateItem" \
  -d '{"TableName":"stock","Key":{"ticker":{"S":"AAPL"}},"UpdateExpression":"SET cache_minutes = :m","ExpressionAttributeValues":{":m":{"N":"45"}}}'
```

## 3. The cache (Redis)

Redis is not reachable over HTTP, so use the cache container's own client:

```bash
docker exec floci-aws-valkey-stock-redis valkey-cli ttl price:AAPL    # seconds left (at most cache_minutes x 60); -2 = not cached
docker exec floci-aws-valkey-stock-redis valkey-cli del price:AAPL    # force a cache miss
curl -s -H "Host: $ALB" localhost:8080/stocks/AAPL                    # miss: fetched and cached again
docker exec floci-aws-valkey-stock-redis valkey-cli ttl price:AAPL    # now about cache_minutes x 60
```

## 4. The hourly Lambda

```bash
curl -s -X POST -d '{}' localhost:4566/2015-03-31/functions/stock-updater/invocations     # {"updated": 5, "skipped": 0}
```

With TSLA disabled the answer is `{"updated": 4, "skipped": 1}`.

## 5. Check Floci against the diagram

Each line is one element of diagram A in [architecture.md](architecture.md); `scripts/delta.sh` automates this.

```bash
EC2="$SIG/ec2/aws4_request"
curl -s "localhost:4566/?Action=DescribeSubnets&Version=2016-11-15"          -H "$EC2" | grep -o "<cidrBlock>10[^<]*"   # 10.0.1.0/24 10.0.2.0/24 10.0.11.0/24 10.0.12.0/24
curl -s "localhost:4566/?Action=DescribeInternetGateways&Version=2016-11-15" -H "$EC2" | grep -o "<internetGatewayId>[^<]*"   # also lists Floci's own default-VPC gateway
curl -s "localhost:4566/?Action=DescribeNatGateways&Version=2016-11-15"      -H "$EC2" | grep -o "<natGatewayId>[^<]*"   # one per AZ
curl -s "localhost:4566/?Action=DescribeVpcEndpoints&Version=2016-11-15"     -H "$EC2" | grep -o "<serviceName>[^<]*"    # ...dynamodb
curl -s "localhost:4566/?Action=DescribeSecurityGroups&Version=2016-11-15"   -H "$EC2" | grep -o "<groupName>stock-[^<]*" # alb task lambda cache
curl -s "localhost:4566/?Action=DescribeReplicationGroups&Version=2015-02-02" -H "$SIG/elasticache/aws4_request" | grep -o "<MultiAZ>[^<]*\|<AutomaticFailover>[^<]*"

# ECS: 2 services, 2 running tasks each (each count prints twice: once for the service, once for its deployment)
curl -s -X POST localhost:4566/ -H "Content-Type: application/x-amz-json-1.1" \
  -H "X-Amz-Target: AmazonEC2ContainerServiceV20141113.DescribeServices" \
  -d '{"cluster":"stock","services":["stock-api-a","stock-api-b"]}' | grep -o '"serviceName":"[^"]*"\|"runningCount":[0-9]*'

# ECR image, hourly rule, Lambda VPC config, log groups
curl -s -X POST localhost:4566/ -H "Content-Type: application/x-amz-json-1.1" -H "X-Amz-Target: AmazonEC2ContainerRegistry_V20150921.DescribeImages" -d '{"repositoryName":"stock-api"}' | grep -o '"imageTags":\[[^]]*\]'
curl -s -X POST localhost:4566/ -H "Content-Type: application/x-amz-json-1.1" -H "X-Amz-Target: AWSEvents.ListRules" -d '{}' | grep -o '"ScheduleExpression":"[^"]*"'
curl -s localhost:4566/2015-03-31/functions/stock-updater | grep -o '"SubnetIds":\[[^]]*\]'
curl -s -X POST localhost:4566/ -H "Content-Type: application/x-amz-json-1.1" -H "X-Amz-Target: Logs_20140328.DescribeLogGroups" -d '{}' | grep -o '"logGroupName":"[^"]*"'
```

## 6. Floci itself

```bash
curl -s localhost:4566/_floci/health        # is Floci up, which version
docker logs floci --tail 50                 # what Floci is doing
```

Web console: <http://localhost:4566/_floci/ui> (first open takes a few seconds). Browse DynamoDB, Lambda, ECS, ECR, ElastiCache and logs.
