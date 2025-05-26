# terraform/outputs.tf

# API Gateway
output "api_gateway_url" {
  description = "API Gateway endpoint URL"
  value       = aws_api_gateway_deployment.main.invoke_url
}

output "api_gateway_id" {
  description = "API Gateway ID"
  value       = aws_api_gateway_rest_api.main.id
}

# Lambda Functions
output "lambda_function_arns" {
  description = "ARNs of Lambda functions"
  value = {
    auth        = aws_lambda_function.auth.arn
    events      = aws_lambda_function.events.arn
    booking     = aws_lambda_function.booking.arn
    booking_processor = aws_lambda_function.booking_processor.arn
    payment_processor = aws_lambda_function.payment_processor.arn
    notification_sender = aws_lambda_function.notification_sender.arn
  }
}

# DynamoDB Tables
output "dynamodb_table_names" {
  description = "DynamoDB table names"
  value = {
    events    = aws_dynamodb_table.events.name
    bookings  = aws_dynamodb_table.bookings.name
    users     = aws_dynamodb_table.users.name
    tickets   = aws_dynamodb_table.tickets.name
    sessions  = aws_dynamodb_table.sessions.name
    analytics = aws_dynamodb_table.analytics.name
  }
}

output "dynamodb_table_arns" {
  description = "DynamoDB table ARNs"
  value = {
    events    = aws_dynamodb_table.events.arn
    bookings  = aws_dynamodb_table.bookings.arn
    users     = aws_dynamodb_table.users.arn
    tickets   = aws_dynamodb_table.tickets.arn
    sessions  = aws_dynamodb_table.sessions.arn
    analytics = aws_dynamodb_table.analytics.arn
  }
}

# SQS Queues
output "sqs_queue_urls" {
  description = "SQS Queue URLs"
  value = {
    booking_processing       = aws_sqs_queue.booking_processing.url
    payment_processing      = aws_sqs_queue.payment_processing.url
    notification           = aws_sqs_queue.notification.url
    cleanup               = aws_sqs_queue.cleanup.url
    analytics             = aws_sqs_queue.analytics.url
    booking_order_processing = aws_sqs_queue.booking_order_processing.url
  }
}

output "sqs_queue_arns" {
  description = "SQS Queue ARNs"
  value = {
    booking_processing       = aws_sqs_queue.booking_processing.arn
    payment_processing      = aws_sqs_queue.payment_processing.arn
    notification           = aws_sqs_queue.notification.arn
    cleanup               = aws_sqs_queue.cleanup.arn
    analytics             = aws_sqs_queue.analytics.arn
    booking_order_processing = aws_sqs_queue.booking_order_processing.arn
  }
}

# ElastiCache
output "elasticache_endpoint" {
  description = "ElastiCache Redis endpoint"
  value       = aws_elasticache_cluster.redis.cache_nodes[0].address
}

output "elasticache_port" {
  description = "ElastiCache Redis port"
  value       = aws_elasticache_cluster.redis.cache_nodes[0].port
}

# CloudWatch
output "cloudwatch_log_groups" {
  description = "CloudWatch Log Groups"
  value = {
    api_gateway = aws_cloudwatch_log_group.api_gateway.name
    lambda_auth = aws_cloudwatch_log_group.lambda_auth.name
    lambda_events = aws_cloudwatch_log_group.lambda_events.name
    lambda_booking = aws_cloudwatch_log_group.lambda_booking.name
    lambda_payment = aws_cloudwatch_log_group.lambda_payment.name
    lambda_notification = aws_cloudwatch_log_group.lambda_notification.name
  }
}

# IAM Roles
output "iam_role_arns" {
  description = "IAM Role ARNs"
  value = {
    lambda_auth = aws_iam_role.lambda_auth.arn
    lambda_booking = aws_iam_role.lambda_booking.arn
    lambda_booking_processor = aws_iam_role.lambda_booking_processor.arn
    lambda_payment_processor = aws_iam_role.lambda_payment_processor.arn
    lambda_notification_sender = aws_iam_role.lambda_notification_sender.arn
  }
}

# S3 Bucket
output "lambda_artifacts_bucket" {
  description = "S3 bucket for Lambda artifacts"
  value       = aws_s3_bucket.lambda_artifacts.bucket
}

# VPC (if created)
output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.main.id
}

output "private_subnet_ids" {
  description = "Private subnet IDs"
  value       = aws_subnet.private[*].id
}

# SNS Topics
output "sns_topic_arns" {
  description = "SNS Topic ARNs"
  value = {
    alerts = aws_sns_topic.alerts.arn
  }
}

# Environment Information
output "environment_info" {
  description = "Environment information"
  value = {
    project_name = var.project_name
    environment  = var.environment
    region      = var.aws_region
    account_id  = data.aws_caller_identity.current.account_id
  }
}

# Load Testing Information
output "load_testing_info" {
  description = "Information for load testing"
  value = {
    api_base_url = aws_api_gateway_deployment.main.invoke_url
    test_endpoints = {
      auth_register = "${aws_api_gateway_deployment.main.invoke_url}/auth/register"
      auth_login    = "${aws_api_gateway_deployment.main.invoke_url}/auth/login"
      events_list   = "${aws_api_gateway_deployment.main.invoke_url}/events"
      booking_reserve = "${aws_api_gateway_deployment.main.invoke_url}/booking/reserve"
      booking_confirm = "${aws_api_gateway_deployment.main.invoke_url}/booking/confirm"
    }
  }
}

# Monitoring Dashboard URLs
output "monitoring_urls" {
  description = "Monitoring and dashboard URLs"
  value = {
    cloudwatch_dashboard = "https://${var.aws_region}.console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${var.project_name}-${var.environment}"
    api_gateway_console = "https://${var.aws_region}.console.aws.amazon.com/apigateway/home?region=${var.aws_region}#/apis/${aws_api_gateway_rest_api.main.id}"
    dynamodb_console = "https://${var.aws_region}.console.aws.amazon.com/dynamodbv2/home?region=${var.aws_region}#tables"
    lambda_console = "https://${var.aws_region}.console.aws.amazon.com/lambda/home?region=${var.aws_region}#/functions"
    sqs_console = "https://${var.aws_region}.console.aws.amazon.com/sqs/v2/home?region=${var.aws_region}#/queues"
  }
}