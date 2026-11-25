variable "floci_endpoint" {
  description = "Where Floci listens, as seen from the Terraform container"
  default     = "http://floci:4566"
}

variable "aws_endpoint_override" {
  description = "Containers must call Floci instead of real AWS for DynamoDB. Set to '' on real AWS."
  default     = "http://floci:4566"
}

variable "redis_host_override" {
  description = "Floci reports ElastiCache as 'localhost', which containers cannot reach. Set to '' on real AWS."
  default     = "floci"
}
