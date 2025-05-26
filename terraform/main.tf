terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# Data sources
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# S3 bucket for Lambda deployment packages
resource "aws_s3_bucket" "lambda_artifacts" {
  bucket = "${var.project_name}-lambda-artifacts-${random_id.bucket_suffix.hex}"
}

resource "aws_s3_bucket_versioning" "lambda_artifacts" {
  bucket = aws_s3_bucket.lambda_artifacts.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "lambda_artifacts" {
  bucket = aws_s3_bucket.lambda_artifacts.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "random_id" "bucket_suffix" {
  byte_length = 8
}

# CloudWatch Log Groups
resource "aws_cloudwatch_log_group" "api_gateway" {
  name              = "/aws/apigateway/${var.project_name}-${var.environment}"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "lambda_auth" {
  name              = "/aws/lambda/${var.project_name}-auth-${var.environment}"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "lambda_events" {
  name              = "/aws/lambda/${var.project_name}-events-${var.environment}"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "lambda_booking" {
  name              = "/aws/lambda/${var.project_name}-booking-${var.environment}"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "lambda_payment" {
  name              = "/aws/lambda/${var.project_name}-payment-${var.environment}"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "lambda_notification" {
  name              = "/aws/lambda/${var.project_name}-notification-${var.environment}"
  retention_in_days = var.log_retention_days
}

# VPC for ElastiCache (optional but recommended)
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "${var.project_name}-vpc-${var.environment}"
  }
}

resource "aws_subnet" "private" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.${count.index + 1}.0/24"
  availability_zone = data.aws_availability_zones.available.names[count.index]

  tags = {
    Name = "${var.project_name}-private-subnet-${count.index + 1}-${var.environment}"
  }
}

data "aws_availability_zones" "available" {
  state = "available"
}