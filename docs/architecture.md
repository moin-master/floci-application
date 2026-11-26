# Architecture

**A** is the production AWS design (the contract). **B** is what is built in Floci from `terraform/*.tf`.

- How B runs on your machine (Docker containers, web console): [floci-runtime.md](floci-runtime.md)
- Where B matches A and where it differs (sections C and D): [match-delta.md](match-delta.md)

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
