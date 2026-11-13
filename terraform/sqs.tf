# Holds stats rows the function could not write to DynamoDB, and serves as the
# dead letter target for the function. Operators replay or inspect messages.
resource "aws_sqs_queue" "failed_writes" {
  name                       = "${var.project_name}-failed-writes"
  sqs_managed_sse_enabled    = true
  message_retention_seconds  = 1209600
  visibility_timeout_seconds = 60
}

resource "aws_cloudwatch_metric_alarm" "failed_writes_backlog" {
  alarm_name          = "${var.project_name}-failed-writes-backlog"
  alarm_description   = "At least one stats write is waiting in the failed-writes queue."
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  statistic           = "Maximum"
  comparison_operator = "GreaterThanThreshold"
  threshold           = 0
  period              = 300
  evaluation_periods  = 1
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_topic_arn == "" ? [] : [var.alarm_topic_arn]

  dimensions = {
    QueueName = aws_sqs_queue.failed_writes.name
  }
}
