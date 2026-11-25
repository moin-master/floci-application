terraform {
  required_providers {
    aws     = { source = "hashicorp/aws", version = "~> 6.0" }
    archive = { source = "hashicorp/archive", version = "~> 2.0" }
    random  = { source = "hashicorp/random", version = "~> 3.0" }
  }
}


provider "aws" {
  region     = "us-east-1"
  access_key = "test"
  secret_key = "test"

  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true
  s3_use_path_style           = true

  endpoints {
    ec2            = var.floci_endpoint
    ecr            = var.floci_endpoint
    ecs            = var.floci_endpoint
    elasticache    = var.floci_endpoint
    elbv2          = var.floci_endpoint
    events         = var.floci_endpoint
    iam            = var.floci_endpoint
    lambda         = var.floci_endpoint
    cloudwatchlogs = var.floci_endpoint
    dynamodb       = var.floci_endpoint
    sts            = var.floci_endpoint
  }
}
