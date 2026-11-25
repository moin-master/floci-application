# ---------- Lambda: hourly price updater ----------
data "archive_file" "updater" {
  type        = "zip"
  source_dir  = "/work/updater/build" # created by scripts/deploy.sh (code + pip deps)
  output_path = "/work/updater/updater.zip"
}

resource "aws_lambda_function" "updater" {
  function_name    = "stock-updater"
  role             = aws_iam_role.lambda.arn
  runtime          = "python3.12"
  handler          = "handler.handler"
  filename         = data.archive_file.updater.output_path
  source_code_hash = data.archive_file.updater.output_base64sha256
  timeout          = 30

  vpc_config {
    subnet_ids         = aws_subnet.private[*].id
    security_group_ids = [aws_security_group.lambda.id]
  }

  environment {
    variables = merge(
      { REDIS_HOST = local.redis_host, REDIS_PORT = local.redis_port },
      { for e in local.aws_env : e.name => e.value if !contains(["AWS_DEFAULT_REGION", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"], e.name) },
    )
  }
  depends_on = [aws_cloudwatch_log_group.updater, aws_iam_role_policy.lambda_dynamodb, aws_dynamodb_table_item.stock]
}

resource "aws_cloudwatch_event_rule" "hourly" {
  name                = "${local.name}-hourly"
  schedule_expression = "rate(1 hour)"
}

resource "aws_cloudwatch_event_target" "updater" {
  rule = aws_cloudwatch_event_rule.hourly.name
  arn  = aws_lambda_function.updater.arn
}

resource "aws_lambda_permission" "events" {
  statement_id  = "AllowEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.updater.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.hourly.arn
}
