output "redis_endpoint" { value = "${local.redis_host}:${local.redis_port}" }
output "alb_dns" { value = aws_lb.api.dns_name }
output "ecr_repo_url" { value = aws_ecr_repository.api.repository_url }
output "dynamodb_table" { value = aws_dynamodb_table.stock.name }
