# ---------- Cache: Redis, primary + replica in different AZs ----------
resource "aws_elasticache_subnet_group" "main" {
  name       = "${local.name}-cache"
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id       = "${local.name}-redis"
  description                = "Stock price cache"
  engine                     = "redis"
  node_type                  = "cache.t3.micro"
  num_cache_clusters         = 2
  automatic_failover_enabled = true
  multi_az_enabled           = true
  subnet_group_name          = aws_elasticache_subnet_group.main.name
  security_group_ids         = [aws_security_group.cache.id]
  port                       = 6379
}

locals {
  redis_host = var.redis_host_override != "" ? var.redis_host_override : aws_elasticache_replication_group.redis.primary_endpoint_address
  redis_port = tostring(aws_elasticache_replication_group.redis.port)
}
