locals {
  name = "stock"
  azs  = ["us-east-1a", "us-east-1b"]

  # AWS SDK settings for the API and the Lambda (boto3 reads AWS_ENDPOINT_URL itself)
  aws_env = concat(
    [{ name = "AWS_DEFAULT_REGION", value = "us-east-1" }, { name = "DYNAMODB_TABLE", value = "stock" }],
    var.aws_endpoint_override == "" ? [] : [
      { name = "AWS_ENDPOINT_URL", value = var.aws_endpoint_override },
      { name = "AWS_ACCESS_KEY_ID", value = "test" },
      { name = "AWS_SECRET_ACCESS_KEY", value = "test" },
    ],
  )
}
