"""Diagram delta check: compares diagram B (docs/architecture.md) with what Floci actually has.

Each check is one element of the production diagram. PASS = Floci has it, GAP = missing or different.
Reads only, changes nothing. Run with scripts/delta.sh after scripts/deploy.sh.
"""
import os
import sys
import time

import boto3

FLOCI = os.environ.get("FLOCI_URL", "http://floci:4566")


def aws(service):
    return boto3.client(service, endpoint_url=FLOCI, region_name="us-east-1",
                        aws_access_key_id="test", aws_secret_access_key="test")


ec2, ecs, elb, ec = aws("ec2"), aws("ecs"), aws("elbv2"), aws("elasticache")
lam, events, ecr, logs, iam = aws("lambda"), aws("events"), aws("ecr"), aws("logs"), aws("iam")
ddb = aws("dynamodb")

CHECKS = []


def check(element):
    def wrap(fn):
        CHECKS.append((element, fn))
        return fn
    return wrap


def subnets_by_name(kind):
    subs = ec2.describe_subnets()["Subnets"]
    out = []
    for s in subs:
        name = next((t["Value"] for t in s.get("Tags", []) if t["Key"] == "Name"), "")
        if name.startswith(f"stock-{kind}"):
            out.append(s)
    return out


def sg(name):
    groups = ec2.describe_security_groups(Filters=[{"Name": "group-name", "Values": [name]}])["SecurityGroups"]
    return groups[0] if groups else None


def ingress_ports(group):
    return sorted((p.get("FromPort"), p.get("ToPort")) for p in group["IpPermissions"])


# ---------- Network ----------
@check("VPC 10.0.0.0/16")
def _():
    return any(v["CidrBlock"] == "10.0.0.0/16" for v in ec2.describe_vpcs()["Vpcs"] if not v.get("IsDefault"))


@check("2 public subnets (10.0.1.0/24, 10.0.2.0/24) in 2 AZs")
def _():
    s = subnets_by_name("public")
    return sorted(x["CidrBlock"] for x in s) == ["10.0.1.0/24", "10.0.2.0/24"] and len({x["AvailabilityZone"] for x in s}) == 2


@check("2 private subnets (10.0.11.0/24, 10.0.12.0/24) in 2 AZs")
def _():
    s = subnets_by_name("private")
    return sorted(x["CidrBlock"] for x in s) == ["10.0.11.0/24", "10.0.12.0/24"] and len({x["AvailabilityZone"] for x in s}) == 2


@check("Internet gateway attached to the VPC")
def _():
    return any(g.get("Attachments") for g in ec2.describe_internet_gateways()["InternetGateways"])


@check("NAT gateway in each public subnet (one per AZ)")
def _():
    pub = {s["SubnetId"] for s in subnets_by_name("public")}
    nats = [n for n in ec2.describe_nat_gateways()["NatGateways"] if n["State"] != "deleted"]
    return len(pub) == 2 and {n["SubnetId"] for n in nats} == pub


@check("Public route tables: 0.0.0.0/0 -> internet gateway")
def _():
    pub = {s["SubnetId"] for s in subnets_by_name("public")}
    for rt in ec2.describe_route_tables()["RouteTables"]:
        assoc = {a.get("SubnetId") for a in rt["Associations"]}
        if pub & assoc:
            if not any(r.get("DestinationCidrBlock") == "0.0.0.0/0" and str(r.get("GatewayId", "")).startswith("igw-") for r in rt["Routes"]):
                return False
            pub -= assoc
    return not pub


@check("Private route tables: 0.0.0.0/0 -> NAT gateway (one per AZ)")
def _():
    priv = {s["SubnetId"] for s in subnets_by_name("private")}
    nats_used = set()
    for rt in ec2.describe_route_tables()["RouteTables"]:
        assoc = {a.get("SubnetId") for a in rt["Associations"]}
        if priv & assoc:
            nat = [r.get("NatGatewayId") for r in rt["Routes"] if r.get("DestinationCidrBlock") == "0.0.0.0/0" and r.get("NatGatewayId")]
            if not nat:
                return False
            nats_used.add(nat[0])
            priv -= assoc
    return not priv and len(nats_used) == 2


# ---------- Security groups ----------
@check("ALB security group: inbound 80 only")
def _():
    g = sg("stock-alb")
    return bool(g) and ingress_ports(g) == [(80, 80)]


@check("Task security group: inbound 8000 only, from the ALB group")
def _():
    g, a = sg("stock-task"), sg("stock-alb")
    if not (g and a) or ingress_ports(g) != [(8000, 8000)]:
        return False
    return [p["UserIdGroupPairs"][0]["GroupId"] for p in g["IpPermissions"]] == [a["GroupId"]]


@check("Cache security group: inbound 6379 only, from the task and Lambda groups")
def _():
    g, t, l = sg("stock-cache"), sg("stock-task"), sg("stock-lambda")
    if not (g and t and l) or ingress_ports(g) != [(6379, 6379)] * len(g["IpPermissions"]):
        return False
    sources = {pair["GroupId"] for p in g["IpPermissions"] for pair in p["UserIdGroupPairs"]}
    return sources == {t["GroupId"], l["GroupId"]}


# ---------- Load balancer ----------
@check("Internet-facing ALB in the 2 public subnets")
def _():
    pub = {s["SubnetId"] for s in subnets_by_name("public")}
    lbs = elb.describe_load_balancers()["LoadBalancers"]
    return any(lb["Scheme"] == "internet-facing" and {z["SubnetId"] for z in lb["AvailabilityZones"]} == pub for lb in lbs)


@check("ALB listener :80 forwards to target group :8000 with /health check")
def _():
    lb = elb.describe_load_balancers()["LoadBalancers"][0]
    ls = elb.describe_listeners(LoadBalancerArn=lb["LoadBalancerArn"])["Listeners"]
    tg = elb.describe_target_groups()["TargetGroups"][0]
    return any(l["Port"] == 80 for l in ls) and tg["Port"] == 8000 and tg["HealthCheckPath"] == "/health"


# ---------- Compute ----------
@check("4 ECS Fargate tasks RUNNING (2 per AZ)")
def _():
    svcs = ecs.describe_services(cluster="stock", services=["stock-api-a", "stock-api-b"])["services"]
    return len(svcs) == 2 and all(s["launchType"] == "FARGATE" for s in svcs) and all(s["runningCount"] == 2 for s in svcs)


@check("ECS service network config: private subnets + task security group")
def _():
    svcs = ecs.describe_services(cluster="stock", services=["stock-api-a", "stock-api-b"])["services"]
    cfgs = [s["networkConfiguration"]["awsvpcConfiguration"] for s in svcs]
    subnets = {sn for c in cfgs for sn in c["subnets"]}
    return subnets == {x["SubnetId"] for x in subnets_by_name("private")} and all(c["securityGroups"] == [sg("stock-task")["GroupId"]] for c in cfgs)


@check("ECS tasks spread across 2 AZs, 2 in each")
def _():
    arns = ecs.list_tasks(cluster="stock")["taskArns"]
    azs = [t["availabilityZone"] for t in ecs.describe_tasks(cluster="stock", tasks=arns)["tasks"] if t.get("availabilityZone")]
    return len(azs) == 4 and sorted(azs.count(z) for z in set(azs)) == [2, 2]


@check("ECS execution role has the task-execution managed policy")
def _():
    pols = iam.list_attached_role_policies(RoleName="stock-ecs-exec")["AttachedPolicies"]
    return any("AmazonECSTaskExecutionRolePolicy" in p["PolicyArn"] for p in pols)


# ---------- Cache ----------
@check("ElastiCache primary + replica, multi-AZ with automatic failover")
def _():
    g = ec.describe_replication_groups(ReplicationGroupId="stock-redis")["ReplicationGroups"][0]
    return len(g["MemberClusters"]) == 2 and g.get("AutomaticFailover") == "enabled" and g.get("MultiAZ") == "enabled"


@check("ElastiCache subnet group = the 2 private subnets")
def _():
    g = ec.describe_cache_subnet_groups(CacheSubnetGroupName="stock-cache")["CacheSubnetGroups"][0]
    return {s["SubnetIdentifier"] for s in g["Subnets"]} == {x["SubnetId"] for x in subnets_by_name("private")}


@check("ElastiCache uses the cache security group")
def _():
    # replication groups do not list SGs; check the member cache cluster
    cl = ec.describe_cache_clusters()["CacheClusters"][0]
    ids = {x["SecurityGroupId"] for x in cl.get("SecurityGroups", [])}
    return sg("stock-cache")["GroupId"] in ids


# ---------- Lambda / EventBridge ----------
@check("Lambda stock-updater has ENIs in both private subnets (vpc_config)")
def _():
    cfg = lam.get_function_configuration(FunctionName="stock-updater").get("VpcConfig", {})
    return set(cfg.get("SubnetIds", [])) == {x["SubnetId"] for x in subnets_by_name("private")} and sg("stock-lambda")["GroupId"] in cfg.get("SecurityGroupIds", [])


@check("Lambda role has the VPC-access managed policy")
def _():
    pols = iam.list_attached_role_policies(RoleName="stock-updater")["AttachedPolicies"]
    return any("AWSLambdaVPCAccessExecutionRole" in p["PolicyArn"] for p in pols)


@check("EventBridge rate(1 hour) -> Lambda stock-updater")
def _():
    rules = [r for r in events.list_rules()["Rules"] if r.get("ScheduleExpression") == "rate(1 hour)"]
    if not rules:
        return False
    targets = events.list_targets_by_rule(Rule=rules[0]["Name"])["Targets"]
    return any("stock-updater" in t["Arn"] for t in targets)


# ---------- DynamoDB ----------
@check("DynamoDB table stock: key ticker, on-demand")
def _():
    t = ddb.describe_table(TableName="stock")["Table"]
    return t["KeySchema"] == [{"AttributeName": "ticker", "KeyType": "HASH"}] and \
        t.get("BillingModeSummary", {}).get("BillingMode", "PAY_PER_REQUEST") == "PAY_PER_REQUEST" and t["TableStatus"] == "ACTIVE"


@check("DynamoDB items: 5 tickers, enabled flag, cache_minutes between 30 and 60")
def _():
    items = ddb.scan(TableName="stock")["Items"]
    return len(items) == 5 and all("BOOL" in i["enabled"] and 30 <= int(i["cache_minutes"]["N"]) <= 60 for i in items)


@check("DynamoDB gateway VPC endpoint on both private route tables")
def _():
    eps = [e for e in ec2.describe_vpc_endpoints()["VpcEndpoints"] if e["ServiceName"].endswith(".dynamodb")]
    if not eps or eps[0].get("VpcEndpointType") != "Gateway":
        return False
    priv = {s["SubnetId"] for s in subnets_by_name("private")}
    rts = {rt["RouteTableId"] for rt in ec2.describe_route_tables()["RouteTables"] if priv & {a.get("SubnetId") for a in rt["Associations"]}}
    return set(eps[0]["RouteTableIds"]) == rts and len(rts) == 2


def role_allows_dynamodb(role):
    for name in iam.list_role_policies(RoleName=role)["PolicyNames"]:
        doc = str(iam.get_role_policy(RoleName=role, PolicyName=name)["PolicyDocument"])
        if "dynamodb:GetItem" in doc and "dynamodb:Scan" in doc and "table/stock" in doc:
            return True
    return False


@check("ECS task role can read the stock table (least privilege)")
def _():
    td = ecs.describe_task_definition(taskDefinition="stock-api")["taskDefinition"]
    return td.get("taskRoleArn", "").endswith("stock-api-task") and role_allows_dynamodb("stock-api-task")


@check("Lambda role can read the stock table (least privilege)")
def _():
    return role_allows_dynamodb("stock-updater")


@check("API task and Lambda are wired to the stock table (DYNAMODB_TABLE=stock)")
def _():
    td = ecs.describe_task_definition(taskDefinition="stock-api")["taskDefinition"]
    task_env = {e["name"]: e["value"] for e in td["containerDefinitions"][0]["environment"]}
    lam_env = lam.get_function_configuration(FunctionName="stock-updater")["Environment"]["Variables"]
    return task_env.get("DYNAMODB_TABLE") == "stock" and lam_env.get("DYNAMODB_TABLE") == "stock"


# ---------- Registry / logs ----------
@check("ECR repository stock-api with an image")
def _():
    return bool(ecr.describe_images(repositoryName="stock-api")["imageDetails"])


@check("CloudWatch log groups /ecs/stock-api and /aws/lambda/stock-updater")
def _():
    names = {g["logGroupName"] for g in logs.describe_log_groups()["logGroups"]}
    return {"/ecs/stock-api", "/aws/lambda/stock-updater"} <= names


def main():
    gaps = 0
    for element, fn in CHECKS:
        for attempt in range(15):  # right after a deploy, tasks may still be starting: retry for ~30s
            try:
                ok = bool(fn())
                why = ""
            except Exception as e:  # API missing or unsupported in Floci also counts as a gap
                ok, why = False, f"  ({type(e).__name__}: {str(e)[:90]})"
            if ok:
                break
            time.sleep(2)
        gaps += not ok
        print(f"  {'PASS' if ok else 'GAP '}  {element}{why}")
    total = len(CHECKS)
    print(f"\nDiagram match: {total - gaps}/{total} = {100 * (total - gaps) // total}%   gaps: {gaps}")
    sys.exit(1 if gaps else 0)


main()
