# ---------- IAM ----------
data "aws_iam_policy_document" "assume_lambda" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "assume_ecs" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  name               = "${local.name}-updater"
  assume_role_policy = data.aws_iam_policy_document.assume_lambda.json
}

resource "aws_iam_role" "ecs_exec" {
  name               = "${local.name}-ecs-exec"
  assume_role_policy = data.aws_iam_policy_document.assume_ecs.json
}

# The task role is what the running API code uses (the execution role only pulls the image and writes logs)
resource "aws_iam_role" "ecs_task" {
  name               = "${local.name}-api-task"
  assume_role_policy = data.aws_iam_policy_document.assume_ecs.json
}

data "aws_iam_policy_document" "read_stock_table" {
  statement {
    actions   = ["dynamodb:GetItem", "dynamodb:Scan"]
    resources = [aws_dynamodb_table.stock.arn]
  }
}

resource "aws_iam_role_policy" "ecs_task_dynamodb" {
  name   = "read-stock-table"
  role   = aws_iam_role.ecs_task.id
  policy = data.aws_iam_policy_document.read_stock_table.json
}

resource "aws_iam_role_policy" "lambda_dynamodb" {
  name   = "read-stock-table"
  role   = aws_iam_role.lambda.id
  policy = data.aws_iam_policy_document.read_stock_table.json
}

resource "aws_iam_role_policy_attachment" "ecs_exec" {
  role       = aws_iam_role.ecs_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy_attachment" "lambda_vpc" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}
