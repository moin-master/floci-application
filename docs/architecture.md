# Architecture

**A** is the production AWS design (the contract). **B** is what is built in Floci from `terraform/*.tf`. **C** lists every element where Floci matches A, and **D** lists what is still different. `scripts/delta.sh` checks A against the running Floci through the AWS APIs (read-only).

## A. AWS (production target)

```
                                   Internet
                                      |
                                      v
 +----------------------------- AWS Region (e.g. us-east-1) --------------------------------+
 |  +----------------------------- VPC 10.0.0.0/16 -------------------------------------+ | |
 |  |        AZ-a                                            AZ-b                         | |
 |  |  +-----------------------------+              +-----------------------------+       | |
 |  |  | Public subnet 10.0.1.0/24   |              | Public subnet 10.0.2.0/24   |       | |
 |  |  |   [ ALB node ]<-------------( Application Load Balancer )------>[ ALB node ]|    | |
 |  |  |   [ NAT GW   ]             |              |   [ NAT GW   ]              |        | |
 |  |  +--------------+--------------+              +--------------+--------------+       | |
 |  |                 | :8000                                      | :8000                | |
 |  |  +--------------v--------------+              +--------------v--------------+       | |
 |  |  | Private subnet 10.0.11.0/24 |              | Private subnet 10.0.12.0/24 |       | |
 |  |  |  [Task] [Task]  FastAPI x2  |              |  [Task] [Task]  FastAPI x2  |       | |
 |  |  |             | 6379          |              |             | 6379          |       | |
 |  |  |  [ElastiCache PRIMARY ]<-----------replication---------->[ElastiCache REPLICA]|  | |
 |  |  |  [Lambda stock-updater, ENIs in both private subnets]   |                  |     | |
 |  |  +-----------------------------+              +-----------------------------+       | |
 |  |  Private route tables: 0.0.0.0/0 -> NAT,  DynamoDB -> [gateway endpoint]            | |
 |  +-------------------------------------------------------------------------------------+ |
 | [ DynamoDB table "stock" key ticker | enabled | cache_minutes 30-60 ]                    |
 |         ^ private path via the VPC gateway endpoint                                      |
 |   EventBridge rate(1 hour) -> Lambda     ECR stock-api:<tag>     CloudWatch Logs         |
 +------------------------------------------------------------------------------------------+
```

Request flow:  Client -> ALB -> FastAPI task -> 1) DynamoDB: is the ticker enabled? (no = 404/403)
                                              2) ElastiCache: price cached? -> yes: return it
                                              3) no: fetch price, cache it for cache_minutes, return it
Update flow:   EventBridge (hourly) -> Lambda -> DynamoDB (enabled tickers) -> ElastiCache (SET, TTL = cache_minutes)
Control:       change enabled / cache_minutes in DynamoDB; the API sees it on the next request

## B. Floci (as built, local)

```
 your machine:  curl localhost:8080  (Host: <alb dns>)         Docker Compose project: floci-application
        |
        v
 +----------------------------- Floci container (:4566 API, :80 ALB listener) -----------------------------+
 |  +------------------------------------- VPC 10.0.0.0/16 (IGW attached) -------------------------------+ |
 |  |        us-east-1a                                              us-east-1b                          | |
 |  |  +-----------------------------+                +-----------------------------+                    | |
 |  |  | Public subnet 10.0.1.0/24   |                | Public subnet 10.0.2.0/24   |                    | |
 |  |  |  ALB node  (SG alb :80)     |<-- ALB stock-alb, internet-facing -->  ALB node                   | |
 |  |  |  NAT GW + EIP               |                |  NAT GW + EIP               |                    | |
 |  |  |  route 0.0.0.0/0 -> IGW     |                |  route 0.0.0.0/0 -> IGW     |                    | |
 |  |  +--------------+--------------+                +--------------+--------------+                    | |
 |  |                 | :8000                                        | :8000                             | |
 |  |  +--------------v--------------+                +--------------v--------------+                    | |
 |  |  | Private subnet 10.0.11.0/24 |                | Private subnet 10.0.12.0/24 |                    | |
 |  |  |  ECS service stock-api-a    |                |  ECS service stock-api-b    |                    | |
 |  |  |   2 Fargate tasks (SG task) |                |   2 Fargate tasks (SG task) |                    | |
 |  |  |  ElastiCache PRIMARY        |<-replication-->|  ElastiCache REPLICA        | (SG cache :6379)   | |
 |  |  |  Lambda stock-updater (SG lambda, vpc_config in both private subnets)       |                   | |
 |  |  |  route 0.0.0.0/0 -> NAT     |                |  route 0.0.0.0/0 -> NAT     |                    | |
 |  |  +-----------------------------+                +-----------------------------+                    | |
 |  |  Private route tables also route DynamoDB -> [VPC gateway endpoint]                                | |
 |  +----------------------------------------------------------------------------------------------------+ |
 | [ DynamoDB table "stock" key ticker | enabled | cache_minutes 30-60 ]                                   |
 |         ^ via the VPC gateway endpoint; seeded with 5 tickers                                           |
 |   EventBridge rate(1 hour) -> Lambda     ECR stock-api:latest     CloudWatch Logs (2 groups)            |
 +--------------------------------------------------------------------------------------------------------+
        ^
        | terraform apply  (hashicorp/terraform container, http://floci:4566)

Request flow:  Client -> ALB -> FastAPI task -> 1) DynamoDB: enabled? (no = 404/403)  2) Redis hit? return  3) miss: fetch, cache for cache_minutes
Update flow:   EventBridge (hourly) -> Lambda -> DynamoDB (enabled tickers) -> mock prices -> ElastiCache (SET, TTL = cache_minutes)
 Deploy flow:   scripts/deploy.sh -> Terraform -> docker build/push to ECR -> Terraform -> smoke test
```

## C. Match (A vs B, verified by `scripts/delta.sh`: 30/30 = 100%)

| # | Element in diagram A | Floci check | Result |
|---|---|---|---|
| 1 | VPC 10.0.0.0/16 | exists | PASS |
| 2 | 2 public subnets, 2 AZs | 10.0.1.0/24, 10.0.2.0/24 | PASS |
| 3 | 2 private subnets, 2 AZs | 10.0.11.0/24, 10.0.12.0/24 | PASS |
| 4 | Internet gateway | attached | PASS |
| 5 | NAT gateway per AZ | one in each public subnet | PASS |
| 6 | Public route to internet | 0.0.0.0/0 -> IGW | PASS |
| 7 | Private route to NAT | 0.0.0.0/0 -> NAT, one per AZ | PASS |
| 8 | ALB security group | inbound 80 only | PASS |
| 9 | Task security group | inbound 8000 only, from ALB group | PASS |
| 10 | Cache security group | inbound 6379 only, from task + Lambda groups | PASS |
| 11 | Internet-facing ALB in public subnets | scheme and subnets | PASS |
| 12 | Listener :80 to target group :8000 | health check `/health` | PASS |
| 13 | 4 Fargate tasks (2 per AZ) | 4 running, 2 per service | PASS |
| 14 | Tasks in private subnets, task SG | service network config | PASS |
| 15 | Tasks in 2 AZs | 2 in each AZ | PASS |
| 16 | ECS execution role policy | managed policy attached | PASS |
| 17 | ElastiCache primary + replica | multi-AZ, automatic failover | PASS |
| 18 | Cache subnet group | the 2 private subnets | PASS |
| 19 | Cache security group | attached to cache nodes | PASS |
| 20 | Lambda in both private subnets | `vpc_config` + Lambda SG | PASS |
| 21 | Lambda VPC access policy | managed policy attached | PASS |
| 22 | EventBridge rate(1 hour) to Lambda | rule + target | PASS |
| 23 | ECR repository with image | image pushed | PASS |
| 24 | CloudWatch log groups | `/ecs/stock-api`, `/aws/lambda/stock-updater` | PASS |
| 25 | DynamoDB table `stock` | key `ticker`, on-demand, ACTIVE | PASS |
| 26 | Table content | 5 tickers, `enabled` flag, `cache_minutes` between 30 and 60 | PASS |
| 27 | DynamoDB gateway endpoint | on both private route tables | PASS |
| 28 | ECS task role | can only GetItem / Scan on the `stock` table | PASS |
| 29 | Lambda role | can only GetItem / Scan on the `stock` table | PASS |
| 30 | API task and Lambda wiring | `DYNAMODB_TABLE=stock` in both | PASS |

Also verified end to end after a full tear-down and rebuild: `scripts/verify.sh` and `scripts/e2e.sh` (22 tests) pass. The e2e tests also prove the behaviour the delta check cannot: a disabled ticker is refused (403) and hidden from `/stocks`, the Lambda skips it, a cache miss is cached for that ticker's `cache_minutes`, and changing `cache_minutes` changes the next cache period.

## D. Delta (what is still different)

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
