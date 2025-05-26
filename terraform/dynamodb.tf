# Events Table
resource "aws_dynamodb_table" "events" {
  name           = "${var.project_name}-events-${var.environment}"
  billing_mode   = var.dynamodb_billing_mode
  hash_key       = "event_id"
  stream_enabled = true
  stream_view_type = "NEW_AND_OLD_IMAGES"

  dynamic "provisioned_throughput" {
    for_each = var.dynamodb_billing_mode == "PROVISIONED" ? [1] : []
    content {
      read_capacity  = var.dynamodb_read_capacity
      write_capacity = var.dynamodb_write_capacity
    }
  }

  attribute {
    name = "event_id"
    type = "S"
  }

  attribute {
    name = "status"
    type = "S"
  }

  attribute {
    name = "date"
    type = "S"
  }

  global_secondary_index {
    name            = "StatusDateIndex"
    hash_key        = "status"
    range_key       = "date"
    projection_type = "ALL"

    dynamic "provisioned_throughput" {
      for_each = var.dynamodb_billing_mode == "PROVISIONED" ? [1] : []
      content {
        read_capacity  = var.dynamodb_read_capacity
        write_capacity = var.dynamodb_write_capacity
      }
    }
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Name = "${var.project_name}-events-${var.environment}"
  }
}

# Bookings Table
resource "aws_dynamodb_table" "bookings" {
  name           = "${var.project_name}-bookings-${var.environment}"
  billing_mode   = var.dynamodb_billing_mode
  hash_key       = "booking_id"
  stream_enabled = true
  stream_view_type = "NEW_AND_OLD_IMAGES"

  dynamic "provisioned_throughput" {
    for_each = var.dynamodb_billing_mode == "PROVISIONED" ? [1] : []
    content {
      read_capacity  = var.dynamodb_read_capacity * 2  # Higher capacity for bookings
      write_capacity = var.dynamodb_write_capacity * 2
    }
  }

  attribute {
    name = "booking_id"
    type = "S"
  }

  attribute {
    name = "user_id"
    type = "S"
  }

  attribute {
    name = "event_id"
    type = "S"
  }

  attribute {
    name = "status"
    type = "S"
  }

  attribute {
    name = "created_at"
    type = "S"
  }

  global_secondary_index {
    name            = "UserBookingsIndex"
    hash_key        = "user_id"
    range_key       = "created_at"
    projection_type = "ALL"

    dynamic "provisioned_throughput" {
      for_each = var.dynamodb_billing_mode == "PROVISIONED" ? [1] : []
      content {
        read_capacity  = var.dynamodb_read_capacity
        write_capacity = var.dynamodb_write_capacity
      }
    }
  }

  global_secondary_index {
    name            = "EventBookingsIndex"
    hash_key        = "event_id"
    range_key       = "status"
    projection_type = "ALL"

    dynamic "provisioned_throughput" {
      for_each = var.dynamodb_billing_mode == "PROVISIONED" ? [1] : []
      content {
        read_capacity  = var.dynamodb_read_capacity
        write_capacity = var.dynamodb_write_capacity
      }
    }
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Name = "${var.project_name}-bookings-${var.environment}"
  }
}

# Users Table
resource "aws_dynamodb_table" "users" {
  name         = "${var.project_name}-users-${var.environment}"
  billing_mode = var.dynamodb_billing_mode
  hash_key     = "user_id"

  dynamic "provisioned_throughput" {
    for_each = var.dynamodb_billing_mode == "PROVISIONED" ? [1] : []
    content {
      read_capacity  = var.dynamodb_read_capacity
      write_capacity = var.dynamodb_write_capacity
    }
  }

  attribute {
    name = "user_id"
    type = "S"
  }

  attribute {
    name = "email"
    type = "S"
  }

  global_secondary_index {
    name            = "EmailIndex"
    hash_key        = "email"
    projection_type = "ALL"

    dynamic "provisioned_throughput" {
      for_each = var.dynamodb_billing_mode == "PROVISIONED" ? [1] : []
      content {
        read_capacity  = var.dynamodb_read_capacity
        write_capacity = var.dynamodb_write_capacity
      }
    }
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Name = "${var.project_name}-users-${var.environment}"
  }
}

# Tickets Table
resource "aws_dynamodb_table" "tickets" {
  name         = "${var.project_name}-tickets-${var.environment}"
  billing_mode = var.dynamodb_billing_mode
  hash_key     = "event_id"
  range_key    = "ticket_id"

  dynamic "provisioned_throughput" {
    for_each = var.dynamodb_billing_mode == "PROVISIONED" ? [1] : []
    content {
      read_capacity  = var.dynamodb_read_capacity * 3  # Highest capacity for tickets
      write_capacity = var.dynamodb_write_capacity * 3
    }
  }

  attribute {
    name = "event_id"
    type = "S"
  }

  attribute {
    name = "ticket_id"
    type = "S"
  }

  attribute {
    name = "status"
    type = "S"
  }

  attribute {
    name = "tier"
    type = "S"
  }

  global_secondary_index {
    name            = "TicketStatusIndex"
    hash_key        = "event_id"
    range_key       = "status"
    projection_type = "ALL"

    dynamic "provisioned_throughput" {
      for_each = var.dynamodb_billing_mode == "PROVISIONED" ? [1] : []
      content {
        read_capacity  = var.dynamodb_read_capacity
        write_capacity = var.dynamodb_write_capacity
      }
    }
  }

  global_secondary_index {
    name            = "TicketTierIndex"
    hash_key        = "event_id"
    range_key       = "tier"
    projection_type = "ALL"

    dynamic "provisioned_throughput" {
      for_each = var.dynamodb_billing_mode == "PROVISIONED" ? [1] : []
      content {
        read_capacity  = var.dynamodb_read_capacity
        write_capacity = var.dynamodb_write_capacity
      }
    }
  }

  ttl {
    attribute_name = "reserved_until"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Name = "${var.project_name}-tickets-${var.environment}"
  }
}

# Sessions Table (for JWT blacklist and user sessions)
resource "aws_dynamodb_table" "sessions" {
  name         = "${var.project_name}-sessions-${var.environment}"
  billing_mode = var.dynamodb_billing_mode
  hash_key     = "session_id"

  dynamic "provisioned_throughput" {
    for_each = var.dynamodb_billing_mode == "PROVISIONED" ? [1] : []
    content {
      read_capacity  = var.dynamodb_read_capacity
      write_capacity = var.dynamodb_write_capacity
    }
  }

  attribute {
    name = "session_id"
    type = "S"
  }

  attribute {
    name = "user_id"
    type = "S"
  }

  global_secondary_index {
    name            = "UserSessionsIndex"
    hash_key        = "user_id"
    projection_type = "ALL"

    dynamic "provisioned_throughput" {
      for_each = var.dynamodb_billing_mode == "PROVISIONED" ? [1] : []
      content {
        read_capacity  = var.dynamodb_read_capacity
        write_capacity = var.dynamodb_write_capacity
      }
    }
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  tags = {
    Name = "${var.project_name}-sessions-${var.environment}"
  }
}

# Analytics Table (for reporting and metrics)
resource "aws_dynamodb_table" "analytics" {
  name         = "${var.project_name}-analytics-${var.environment}"
  billing_mode = var.dynamodb_billing_mode
  hash_key     = "metric_type"
  range_key    = "timestamp"

  dynamic "provisioned_throughput" {
    for_each = var.dynamodb_billing_mode == "PROVISIONED" ? [1] : []
    content {
      read_capacity  = var.dynamodb_read_capacity
      write_capacity = var.dynamodb_write_capacity
    }
  }

  attribute {
    name = "metric_type"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = {
    Name = "${var.project_name}-analytics-${var.environment}"
  }
}