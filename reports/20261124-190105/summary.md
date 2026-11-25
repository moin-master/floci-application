# Floci run report

## C. Match: does Floci have every element of the production diagram (A)?

**Diagram match: 30/30 = 100%   gaps: 0**

| # | Element in diagram A | Result |
|---|---|---|
| 1 | VPC 10.0.0.0/16 | PASS |
| 2 | 2 public subnets (10.0.1.0/24, 10.0.2.0/24) in 2 AZs | PASS |
| 3 | 2 private subnets (10.0.11.0/24, 10.0.12.0/24) in 2 AZs | PASS |
| 4 | Internet gateway attached to the VPC | PASS |
| 5 | NAT gateway in each public subnet (one per AZ) | PASS |
| 6 | Public route tables: 0.0.0.0/0 -> internet gateway | PASS |
| 7 | Private route tables: 0.0.0.0/0 -> NAT gateway (one per AZ) | PASS |
| 8 | ALB security group: inbound 80 only | PASS |
| 9 | Task security group: inbound 8000 only, from the ALB group | PASS |
| 10 | Cache security group: inbound 6379 only, from the task and Lambda groups | PASS |
| 11 | Internet-facing ALB in the 2 public subnets | PASS |
| 12 | ALB listener :80 forwards to target group :8000 with /health check | PASS |
| 13 | 4 ECS Fargate tasks RUNNING (2 per AZ) | PASS |
| 14 | ECS service network config: private subnets + task security group | PASS |
| 15 | ECS tasks spread across 2 AZs, 2 in each | PASS |
| 16 | ECS execution role has the task-execution managed policy | PASS |
| 17 | ElastiCache primary + replica, multi-AZ with automatic failover | PASS |
| 18 | ElastiCache subnet group = the 2 private subnets | PASS |
| 19 | ElastiCache uses the cache security group | PASS |
| 20 | Lambda stock-updater has ENIs in both private subnets (vpc_config) | PASS |
| 21 | Lambda role has the VPC-access managed policy | PASS |
| 22 | EventBridge rate(1 hour) -> Lambda stock-updater | PASS |
| 23 | DynamoDB table stock: key ticker, on-demand | PASS |
| 24 | DynamoDB items: 5 tickers, enabled flag, cache_minutes between 30 and 60 | PASS |
| 25 | DynamoDB gateway VPC endpoint on both private route tables | PASS |
| 26 | ECS task role can read the stock table (least privilege) | PASS |
| 27 | Lambda role can read the stock table (least privilege) | PASS |
| 28 | API task and Lambda are wired to the stock table (DYNAMODB_TABLE=stock) | PASS |
| 29 | ECR repository stock-api with an image | PASS |
| 30 | CloudWatch log groups /ecs/stock-api and /aws/lambda/stock-updater | PASS |

A PASS means Floci reports the resource as configured. It does not prove real AWS routing.

## D. Delta: what is still different between AWS (A) and Floci (B)

Nothing is missing from the diagram. These are the known differences that remain:

| Topic | AWS (A) | Floci (B) | Why |
|---|---|---|---|
| ECS service shape | One service, `desired_count = 4`, ECS spreads tasks over both subnets | Two services (`stock-api-a`, `stock-api-b`), one subnet and two tasks each, same target group | Floci puts every task of a service in one subnet. The result (two tasks per AZ) matches; the service count does not |
| ElastiCache address | Real primary endpoint (`redis_host_override = ""`) | `redis_host_override = "floci"` | Floci reports ElastiCache as `localhost`, which containers cannot reach |
| ALB access | Public DNS name | `localhost:8080` with a `Host: <alb dns>` header | Local emulator |
| Lambda networking | ENIs in the private subnets | `vpc_config` is stored and reported, but Floci runs Lambda as a container on the Floci network | Emulator limit |
| NAT / IGW / DynamoDB endpoint traffic | Real routing; DynamoDB reached privately through the gateway endpoint | Resources and routes exist; no traffic actually passes through them | Emulator limit |
| DynamoDB address and credentials | SDK uses the regional endpoint and the task / Lambda role | `aws_endpoint_override = "http://floci:4566"` plus test keys in the container env (`""` on real AWS) | Containers must be pointed at Floci |
| Random cache minutes | Chosen once by Terraform (`random_integer`), then edited in DynamoDB | Same | No difference |
| Fidelity of a PASS | Real AWS behaviour | Floci accepted the resource and reports it back | Checks read configuration, not packet paths |

## E. Behaviour: does the system work? (end-to-end tests)

**22 of 22 tests passed**

**Is everything built?**
- PASS  ECR has the API image (0.1s)
- PASS  ECS runs two tasks per AZ (0.0s)
- PASS  Two subnets in two AZs (0.0s)
- PASS  Redis has primary and replica (0.0s)
- PASS  DynamoDB table has the tickers (0.0s)
- PASS  Lambda is scheduled hourly (0.0s)

**Does the API answer correctly?**
- PASS  Health (0.0s)
- PASS  Get price (0.0s)
- PASS  Symbol is case insensitive (0.0s)
- PASS  Unknown symbol is 404 (0.0s)
- PASS  List symbols (0.0s)

**Do prices flow Lambda -> Redis -> API?**
- PASS  Lambda updates every symbol (0.0s)
- PASS  New Lambda run refreshes the price the API serves (1.1s)
- PASS  Price is stored in Redis with a TTL (0.0s)

**Are logs written?**
- PASS  Lambda logs (0.0s)
- PASS  API logs (0.0s)

**Does DynamoDB control the API (enable, disable, cache time)?**
- PASS  Disabled ticker is refused and hidden (0.0s)
- PASS  Lambda skips disabled tickers (0.0s)
- PASS  Cache miss fills the cache for the ticker period (0.0s)
- PASS  Cache hit returns the cached price (0.0s)
- PASS  Changing cache minutes changes the next cache period (0.0s)

**Does it survive a failure?**
- PASS  API survives losing one task (4.6s)

## Verdict

PASS: the environment matches the diagram and works end to end.
