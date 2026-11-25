# ---------- DynamoDB: table "stock" = which tickers are enabled and how long to cache each ----------
resource "aws_dynamodb_table" "stock" {
  name         = "stock"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "ticker"

  attribute {
    name = "ticker"
    type = "S"
  }
}

# Cache period per ticker: a random whole number of minutes from 30 to 60, picked once and kept in state
resource "random_integer" "cache_minutes" {
  for_each = toset(["AAPL", "MSFT", "AMZN", "GOOGL", "TSLA"])
  min      = 30
  max      = 60
}

resource "aws_dynamodb_table_item" "stock" {
  for_each   = random_integer.cache_minutes
  table_name = aws_dynamodb_table.stock.name
  hash_key   = aws_dynamodb_table.stock.hash_key
  item = jsonencode({
    ticker        = { S = each.key }
    enabled       = { BOOL = true }
    cache_minutes = { N = tostring(each.value.result) }
  })
  # after the first create, people change enabled / cache_minutes in DynamoDB; do not overwrite those edits
  lifecycle { ignore_changes = [item] }
}

# Private path to DynamoDB: tasks and Lambda reach it without going through the NAT gateway
