# terraform/lambda.tf

# Lambda Layers

# Common utilities layer
resource "aws_lambda_layer_version" "common" {
  filename            = "../layers/common-layer.zip"
  layer_name          = "${var.project_name}-common-${var.environment}"
  compatible_runtimes = ["python3.11"]
  description         = "Common utilities for ticket booking system"

  depends_on = [
    null_resource.build_common_layer
  ]
}

# External libraries layer
resource "aws_lambda_layer_version" "external_libs" {
  filename            = "../layers/external-libs-layer.zip"
  layer_name          = "${var.project_name}-external-libs-${var.environment}"
  compatible_runtimes = ["python3.11"]
  description         = "External libraries for ticket booking system"

  depends_on = [
    null_resource.build_external_libs_layer
  ]
}

# Build layers
resource "null_resource" "build_common_layer" {
  triggers = {
    requirements = filemd5("../layers/common/requirements.txt")
    code_hash    = md5(join("", [for f in fileset("../layers/common/python/lib", "**") : filemd5("../layers/common/python/lib/${f}")]))
  }

  provisioner "local-exec" {
    command = <<-EOT
      cd ../layers/common
      pip install -r requirements.txt -t python/lib/
      zip -r ../common-layer.zip python/
    EOT
  }
}

resource "null_resource" "build_external_libs_layer" {
  triggers = {
    requirements = filemd5("../layers/external-libs/requirements.txt")
  }

  provisioner "local-exec" {
    command = <<-EOT
      cd ../layers/external-libs
      pip install -r requirements.txt -t python/lib/
      zip -r ../external-libs-layer.zip python/
    EOT
  }
}

# Lambda Functions

# Auth Lambda
resource "aws_lambda_function" "auth" {
  filename         = "../dist/auth.zip"
  function_name    = "${var.project_name}-auth-${var.environment}"
  role            = aws_iam_role.lambda_auth.arn
  handler         = "handler.lambda_handler"
  runtime         = "python3.11"
  timeout         = var.lambda_timeout
  memory_size     = var.lambda_memory_size

  layers = [
    aws_lambda_layer_version.common.arn,
    aws_lambda_layer_version.external_libs.arn
  ]

  environment {
    variables = {
      ENVIRONMENT      = var.environment
      PROJECT_NAME     = var.project_name
      AWS_REGION       = var.aws_region
      USERS_TABLE      = aws_dynamodb_table.users.name
      SESSIONS_TABLE   = aws_dynamodb_table.sessions.name
      REDIS_ENDPOINT   = aws_elasticache_cluster.redis.cache_nodes[0].address
      JWT_SECRET       = var.jwt_secret
    }
  }

  vpc_config {
    subnet_ids         = aws_subnet.private[*].id
    security_group_ids = [aws_security_group.lambda.id]
  }

  tracing_config {
    mode = var.enable_xray_tracing ? "Active" : "PassThrough"
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_auth_policy,
    aws_cloudwatch_log_group.lambda_auth,
    null_resource.build_auth_lambda
  ]

  tags = {
    Name = "${var.project_name}-auth-${var.environment}"
  }
}

# Events Lambda
resource "aws_lambda_function" "events" {
  filename         = "../dist/events.zip"
  function_name    = "${var.project_name}-events-${var.environment}"
  role            = aws_iam_role.lambda_events.arn
  handler         = "handler.lambda_handler"
  runtime         = "python3.11"
  timeout         = var.lambda_timeout
  memory_size     = var.lambda_memory_size

  layers = [
    aws_lambda_layer_version.common.arn
  ]

  environment {
    variables = {
      ENVIRONMENT    = var.environment
      PROJECT_NAME   = var.project_name
      AWS_REGION     = var.aws_region
      EVENTS_TABLE   = aws_dynamodb_table.events.name
      TICKETS_TABLE  = aws_dynamodb_table.tickets.name
      REDIS_ENDPOINT = aws_elasticache_cluster.redis.cache_nodes[0].address
    }
  }

  vpc_config {
    subnet_ids         = aws_subnet.private[*].id
    security_group_ids = [aws_security_group.lambda.id]
  }

  tracing_config {
    mode = var.enable_xray_tracing ? "Active" : "PassThrough"
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_events_policy,
    aws_cloudwatch_log_group.lambda_events,
    null_resource.build_events_lambda
  ]

  tags = {
    Name = "${var.project_name}-events-${var.environment}"
  }
}

# Booking Lambda
resource "aws_lambda_function" "booking" {
  filename         = "../dist/booking.zip"
  function_name    = "${var.project_name}-booking-${var.environment}"
  role            = aws_iam_role.lambda_booking.arn
  handler         = "handler.lambda_handler"
  runtime         = "python3.11"
  timeout         = var.lambda_timeout
  memory_size     = var.lambda_memory_size * 2  # More memory for booking logic

  layers = [
    aws_lambda_layer_version.common.arn
  ]

  environment {
    variables = {
      ENVIRONMENT               = var.environment
      PROJECT_NAME              = var.project_name
      AWS_REGION                = var.aws_region
      EVENTS_TABLE              = aws_dynamodb_table.events.name
      BOOKINGS_TABLE            = aws_dynamodb_table.bookings.name
      TICKETS_TABLE             = aws_dynamodb_table.tickets.name
      USERS_TABLE               = aws_dynamodb_table.users.name
      REDIS_ENDPOINT            = aws_elasticache_cluster.redis.cache_nodes[0].address
      BOOKING_QUEUE_URL         = aws_sqs_queue.booking_processing.url
      PAYMENT_QUEUE_URL         = aws_sqs_queue.payment_processing.url
      NOTIFICATION_QUEUE_URL    = aws_sqs_queue.notification.url
    }
  }

  vpc_config {
    subnet_ids         = aws_subnet.private[*].id
    security_group_ids = [aws_security_group.lambda.id]
  }

  tracing_config {
    mode = var.enable_xray_tracing ? "Active" : "PassThrough"
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_booking_policy,
    aws_cloudwatch_log_group.lambda_booking,
    null_resource.build_booking_lambda
  ]

  tags = {
    Name = "${var.project_name}-booking-${var.environment}"
  }
}

# Provisioned Concurrency for critical functions
resource "aws_lambda_provisioned_concurrency_config" "booking" {
  count                             = var.lambda_provisioned_concurrency > 0 ? 1 : 0
  function_name                     = aws_lambda_function.booking.function_name
  provisioned_concurrent_executions = var.lambda_provisioned_concurrency
  qualifier                         = aws_lambda_function.booking.version
}

# Booking Processor Lambda (SQS triggered)
resource "aws_lambda_function" "booking_processor" {
  filename         = "../dist/booking_processor.zip"
  function_name    = "${var.project_name}-booking-processor-${var.environment}"
  role            = aws_iam_role.lambda_booking_processor.arn
  handler         = "handler.lambda_handler"
  runtime         = "python3.11"
  timeout         = 60  # Longer timeout for processing
  memory_size     = var.lambda_memory_size

  layers = [
    aws_lambda_layer_version.common.arn
  ]

  environment {
    variables = {
      ENVIRONMENT            = var.environment
      PROJECT_NAME           = var.project_name
      AWS_REGION             = var.aws_region
      EVENTS_TABLE           = aws_dynamodb_table.events.name
      BOOKINGS_TABLE         = aws_dynamodb_table.bookings.name
      TICKETS_TABLE          = aws_dynamodb_table.tickets.name
      REDIS_ENDPOINT         = aws_elasticache_cluster.redis.cache_nodes[0].address
      NOTIFICATION_QUEUE_URL = aws_sqs_queue.notification.url
      ANALYTICS_QUEUE_URL    = aws_sqs_queue.analytics.url
    }
  }

  vpc_config {
    subnet_ids         = aws_subnet.private[*].id
    security_group_ids = [aws_security_group.lambda.id]
  }

  tracing_config {
    mode = var.enable_xray_tracing ? "Active" : "PassThrough"
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_booking_processor_policy,
    null_resource.build_booking_processor_lambda
  ]

  tags = {
    Name = "${var.project_name}-booking-processor-${var.environment}"
  }
}

# Payment Processor Lambda
resource "aws_lambda_function" "payment_processor" {
  filename         = "../dist/payment.zip"
  function_name    = "${var.project_name}-payment-processor-${var.environment}"
  role            = aws_iam_role.lambda_payment_processor.arn
  handler         = "handler.lambda_handler"
  runtime         = "python3.11"
  timeout         = 60
  memory_size     = var.lambda_memory_size

  layers = [
    aws_lambda_layer_version.common.arn,
    aws_lambda_layer_version.external_libs.arn
  ]

  environment {
    variables = {
      ENVIRONMENT            = var.environment
      PROJECT_NAME           = var.project_name
      AWS_REGION             = var.aws_region
      BOOKINGS_TABLE         = aws_dynamodb_table.bookings.name
      REDIS_ENDPOINT         = aws_elasticache_cluster.redis.cache_nodes[0].address
      NOTIFICATION_QUEUE_URL = aws_sqs_queue.notification.url
      ANALYTICS_QUEUE_URL    = aws_sqs_queue.analytics.url
      STRIPE_SECRET_KEY      = var.stripe_secret_key
    }
  }

  vpc_config {
    subnet_ids         = aws_subnet.private[*].id
    security_group_ids = [aws_security_group.lambda.id]
  }

  tracing_config {
    mode = var.enable_xray_tracing ? "Active" : "PassThrough"
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_payment_processor_policy,
    null_resource.build_payment_lambda
  ]

  tags = {
    Name = "${var.project_name}-payment-processor-${var.environment}"
  }
}

# Notification Sender Lambda
resource "aws_lambda_function" "notification_sender" {
  filename         = "../dist/notifications.zip"
  function_name    = "${var.project_name}-notification-sender-${var.environment}"
  role            = aws_iam_role.lambda_notification_sender.arn
  handler         = "handler.lambda_handler"
  runtime         = "python3.11"
  timeout         = 30
  memory_size     = var.lambda_memory_size

  layers = [
    aws_lambda_layer_version.common.arn,
    aws_lambda_layer_version.external_libs.arn
  ]

  environment {
    variables = {
      ENVIRONMENT      = var.environment
      PROJECT_NAME     = var.project_name
      AWS_REGION       = var.aws_region
      USERS_TABLE      = aws_dynamodb_table.users.name
      SENDGRID_API_KEY = var.sendgrid_api_key
      TWILIO_SID       = var.twilio_account_sid
      TWILIO_TOKEN     = var.twilio_auth_token
    }
  }

  tracing_config {
    mode = var.enable_xray_tracing ? "Active" : "PassThrough"
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_notification_sender_policy,
    null_resource.build_notifications_lambda
  ]

  tags = {
    Name = "${var.project_name}-notification-sender-${var.environment}"
  }
}

# Build Lambda deployment packages
resource "null_resource" "build_auth_lambda" {
  triggers = {
    code_hash = md5(join("", [for f in fileset("../lambdas/auth", "**") : filemd5("../lambdas/auth/${f}")]))
  }

  provisioner "local-exec" {
    command = "cd ../lambdas/auth && zip -r ../../dist/auth.zip ."
  }
}

resource "null_resource" "build_events_lambda" {
  triggers = {
    code_hash = md5(join("", [for f in fileset("../lambdas/events", "**") : filemd5("../lambdas/events/${f}")]))
  }

  provisioner "local-exec" {
    command = "cd ../lambdas/events && zip -r ../../dist/events.zip ."
  }
}

resource "null_resource" "build_booking_lambda" {
  triggers = {
    code_hash = md5(join("", [for f in fileset("../lambdas/booking", "**") : filemd5("../lambdas/booking/${f}")]))
  }

  provisioner "local-exec" {
    command = "cd ../lambdas/booking && zip -r ../../dist/booking.zip ."
  }
}

resource "null_resource" "build_booking_processor_lambda" {
  triggers = {
    code_hash = md5(join("", [for f in fileset("../lambdas/booking_processor", "**") : filemd5("../lambdas/booking_processor/${f}")]))
  }

  provisioner "local-exec" {
    command = "cd ../lambdas/booking_processor && zip -r ../../dist/booking_processor.zip ."
  }
}

resource "null_resource" "build_payment_lambda" {
  triggers = {
    code_hash = md5(join("", [for f in fileset("../lambdas/payment", "**") : filemd5("../lambdas/payment/${f}")]))
  }

  provisioner "local-exec" {
    command = "cd ../lambdas/payment && zip -r ../../dist/payment.zip ."
  }
}

resource "null_resource" "build_notifications_lambda" {
  triggers = {
    code_hash = md5(join("", [for f in fileset("../lambdas/notifications", "**") : filemd5("../lambdas/notifications/${f}")]))
  }

  provisioner "local-exec" {
    command = "cd ../lambdas/notifications && zip -r ../../dist/notifications.zip ."
  }
}

# Event Source Mappings for SQS

# Booking processing queue
resource "aws_lambda_event_source_mapping" "booking_processing" {
  event_source_arn = aws_sqs_queue.booking_processing.arn
  function_name    = aws_lambda_function.booking_processor.arn
  batch_size       = 10
  maximum_batching_window_in_seconds = 5

  depends_on = [
    aws_iam_role_policy_attachment.lambda_booking_processor_policy
  ]
}

# Payment processing queue
resource "aws_lambda_event_source_mapping" "payment_processing" {
  event_source_arn = aws_sqs_queue.payment_processing.arn
  function_name    = aws_lambda_function.payment_processor.arn
  batch_size       = 5
  maximum_batching_window_in_seconds = 10

  depends_on = [
    aws_iam_role_policy_attachment.lambda_payment_processor_policy
  ]
}

# Notification queue
resource "aws_lambda_event_source_mapping" "notification" {
  event_source_arn = aws_sqs_queue.notification.arn
  function_name    = aws_lambda_function.notification_sender.arn
  batch_size       = 10
  maximum_batching_window_in_seconds = 0

  depends_on = [
    aws_iam_role_policy_attachment.lambda_notification_sender_policy
  ]
}

# Security Group for Lambda functions
resource "aws_security_group" "lambda" {
  name_prefix = "${var.project_name}-lambda-${var.environment}"
  vpc_id      = aws_vpc.main.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Redis access
  egress {
    from_port   = 6379
    to_port     = 6379
    protocol    = "tcp"
    cidr_blocks = [aws_vpc.main.cidr_block]
  }

  tags = {
    Name = "${var.project_name}-lambda-sg-${var.environment}"
  }
}