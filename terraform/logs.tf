# ---------- Logs ----------
resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/stock-api"
  retention_in_days = 7
}

resource "aws_cloudwatch_log_group" "updater" {
  name              = "/aws/lambda/stock-updater"
  retention_in_days = 7
}
