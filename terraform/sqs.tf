# terraform/sqs.tf

# Booking Processing Queue
resource "aws_sqs_queue" "booking_processing" {
  name                       = "${var.project_name}-booking-processing-${var.environment}"
  visibility_timeout_seconds = var.sqs_visibility_timeout
  message_retention_seconds  = var.sqs_message_retention
  max_message_size           = 262144
  delay_seconds             = 0
  receive_wait_time_seconds = 0

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.booking_processing_dlq.arn
    maxReceiveCount     = var.sqs_max_receive_count
  })

  tags = {
    Name = "${var.project_name}-booking-processing-${var.environment}"
  }
}

# Booking Processing Dead Letter Queue
resource "aws_sqs_queue" "booking_processing_dlq" {
  name                      = "${var.project_name}-booking-processing-dlq-${var.environment}"
  message_retention_seconds = 1209600 # 14 days

  tags = {
    Name = "${var.project_name}-booking-processing-dlq-${var.environment}"
  }
}

# Payment Processing Queue
resource "aws_sqs_queue" "payment_processing" {
  name                       = "${var.project_name}-payment-processing-${var.environment}"
  visibility_timeout_seconds = var.sqs_visibility_timeout
  message_retention_seconds  = var.sqs_message_retention
  max_message_size           = 262144
  delay_seconds             = 0
  receive_wait_time_seconds = 0

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.payment_processing_dlq.arn
    maxReceiveCount     = var.sqs_max_receive_count
  })

  tags = {
    Name = "${var.project_name}-payment-processing-${var.environment}"
  }
}

# Payment Processing Dead Letter Queue
resource "aws_sqs_queue" "payment_processing_dlq" {
  name                      = "${var.project_name}-payment-processing-dlq-${var.environment}"
  message_retention_seconds = 1209600 # 14 days

  tags = {
    Name = "${var.project_name}-payment-processing-dlq-${var.environment}"
  }
}

# Notification Queue
resource "aws_sqs_queue" "notification" {
  name                       = "${var.project_name}-notification-${var.environment}"
  visibility_timeout_seconds = var.sqs_visibility_timeout
  message_retention_seconds  = var.sqs_message_retention
  max_message_size           = 262144
  delay_seconds             = 0
  receive_wait_time_seconds = 0

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.notification_dlq.arn
    maxReceiveCount     = var.sqs_max_receive_count
  })

  tags = {
    Name = "${var.project_name}-notification-${var.environment}"
  }
}

# Notification Dead Letter Queue
resource "aws_sqs_queue" "notification_dlq" {
  name                      = "${var.project_name}-notification-dlq-${var.environment}"
  message_retention_seconds = 1209600 # 14 days

  tags = {
    Name = "${var.project_name}-notification-dlq-${var.environment}"
  }
}

# Cleanup Queue (for expired reservations)
resource "aws_sqs_queue" "cleanup" {
  name                       = "${var.project_name}-cleanup-${var.environment}"
  visibility_timeout_seconds = var.sqs_visibility_timeout
  message_retention_seconds  = var.sqs_message_retention
  max_message_size           = 262144
  delay_seconds             = 0
  receive_wait_time_seconds = 0

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.cleanup_dlq.arn
    maxReceiveCount     = var.sqs_max_receive_count
  })

  tags = {
    Name = "${var.project_name}-cleanup-${var.environment}"
  }
}

# Cleanup Dead Letter Queue
resource "aws_sqs_queue" "cleanup_dlq" {
  name                      = "${var.project_name}-cleanup-dlq-${var.environment}"
  message_retention_seconds = 1209600 # 14 days

  tags = {
    Name = "${var.project_name}-cleanup-dlq-${var.environment}"
  }
}

# Analytics Queue (for metrics and reporting)
resource "aws_sqs_queue" "analytics" {
  name                       = "${var.project_name}-analytics-${var.environment}"
  visibility_timeout_seconds = var.sqs_visibility_timeout
  message_retention_seconds  = var.sqs_message_retention
  max_message_size           = 262144
  delay_seconds             = 0
  receive_wait_time_seconds = 20 # Enable long polling

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.analytics_dlq.arn
    maxReceiveCount     = var.sqs_max_receive_count
  })

  tags = {
    Name = "${var.project_name}-analytics-${var.environment}"
  }
}

# Analytics Dead Letter Queue
resource "aws_sqs_queue" "analytics_dlq" {
  name                      = "${var.project_name}-analytics-dlq-${var.environment}"
  message_retention_seconds = 1209600 # 14 days

  tags = {
    Name = "${var.project_name}-analytics-dlq-${var.environment}"
  }
}

# FIFO Queue for order-critical operations
resource "aws_sqs_queue" "booking_order_processing" {
  name                        = "${var.project_name}-booking-order-processing-${var.environment}.fifo"
  fifo_queue                 = true
  content_based_deduplication = true
  visibility_timeout_seconds  = var.sqs_visibility_timeout
  message_retention_seconds   = var.sqs_message_retention

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.booking_order_processing_dlq.arn
    maxReceiveCount     = var.sqs_max_receive_count
  })

  tags = {
    Name = "${var.project_name}-booking-order-processing-${var.environment}"
  }
}

# FIFO Dead Letter Queue
resource "aws_sqs_queue" "booking_order_processing_dlq" {
  name                      = "${var.project_name}-booking-order-processing-dlq-${var.environment}.fifo"
  fifo_queue               = true
  message_retention_seconds = 1209600 # 14 days

  tags = {
    Name = "${var.project_name}-booking-order-processing-dlq-${var.environment}"
  }
}

# Queue Policies

# Booking Processing Queue Policy
resource "aws_sqs_queue_policy" "booking_processing" {
  queue_url = aws_sqs_queue.booking_processing.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowLambdaAccess"
        Effect = "Allow"
        Principal = {
          AWS = [
            aws_iam_role.lambda_booking.arn,
            aws_iam_role.lambda_booking_processor.arn
          ]
        }
        Action = [
          "sqs:SendMessage",
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = aws_sqs_queue.booking_processing.arn
      }
    ]
  })
}

# Payment Processing Queue Policy
resource "aws_sqs_queue_policy" "payment_processing" {
  queue_url = aws_sqs_queue.payment_processing.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowLambdaAccess"
        Effect = "Allow"
        Principal = {
          AWS = [
            aws_iam_role.lambda_booking.arn,
            aws_iam_role.lambda_payment_processor.arn
          ]
        }
        Action = [
          "sqs:SendMessage",
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = aws_sqs_queue.payment_processing.arn
      }
    ]
  })
}

# CloudWatch Alarms for SQS Queues

# Booking Processing Queue - High Message Count
resource "aws_cloudwatch_metric_alarm" "booking_processing_high_messages" {
  alarm_name          = "${var.project_name}-booking-processing-high-messages-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "ApproximateNumberOfVisibleMessages"
  namespace           = "AWS/SQS"
  period              = "300"
  statistic           = "Average"
  threshold           = "100"
  alarm_description   = "This metric monitors booking processing queue depth"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    QueueName = aws_sqs_queue.booking_processing.name
  }

  tags = {
    Name = "${var.project_name}-booking-processing-high-messages-${var.environment}"
  }
}

# Booking Processing Queue - Old Messages
resource "aws_cloudwatch_metric_alarm" "booking_processing_old_messages" {
  alarm_name          = "${var.project_name}-booking-processing-old-messages-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "ApproximateAgeOfOldestMessage"
  namespace           = "AWS/SQS"
  period              = "300"
  statistic           = "Maximum"
  threshold           = "300" # 5 minutes
  alarm_description   = "This metric monitors booking processing queue message age"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    QueueName = aws_sqs_queue.booking_processing.name
  }

  tags = {
    Name = "${var.project_name}-booking-processing-old-messages-${var.environment}"
  }
}

# Dead Letter Queue Alarms
resource "aws_cloudwatch_metric_alarm" "booking_processing_dlq_messages" {
  alarm_name          = "${var.project_name}-booking-processing-dlq-messages-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "ApproximateNumberOfVisibleMessages"
  namespace           = "AWS/SQS"
  period              = "300"
  statistic           = "Sum"
  threshold           = "0"
  alarm_description   = "This metric monitors messages in booking processing DLQ"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    QueueName = aws_sqs_queue.booking_processing_dlq.name
  }

  tags = {
    Name = "${var.project_name}-booking-processing-dlq-messages-${var.environment}"
  }
}

# SNS Topic for Alerts
resource "aws_sns_topic" "alerts" {
  name = "${var.project_name}-alerts-${var.environment}"

  tags = {
    Name = "${var.project_name}-alerts-${var.environment}"
  }
}

# SNS Topic Subscription (email alerts)
resource "aws_sns_topic_subscription" "email_alerts" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email_address

  count = var.alert_email_address != "" ? 1 : 0
}

# Output SQS Queue URLs for Lambda functions
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