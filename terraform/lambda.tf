data "aws_iam_policy_document" "assume_lambda" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "parser" {
  name               = "${var.project_name}-lambda"
  assume_role_policy = data.aws_iam_policy_document.assume_lambda.json
}

resource "aws_cloudwatch_log_group" "parser" {
  name              = "/aws/lambda/${var.project_name}"
  retention_in_days = var.log_retention_days
}

# Least privilege: write logs to one group, PutItem on one table, and
# optionally GetObject on one bucket.
data "aws_iam_policy_document" "parser" {
  statement {
    sid       = "Logs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.parser.arn}:*"]
  }

  # PutItem also covers the Put actions inside a transact_write_items call.
  statement {
    sid       = "StatsPut"
    actions   = ["dynamodb:PutItem"]
    resources = [aws_dynamodb_table.stats.arn]
  }

  # One queue. The runtime sends failed writes here. Lambda sends failed
  # asynchronous invocations here as the dead letter target.
  statement {
    sid       = "FailedWritesSend"
    actions   = ["sqs:SendMessage"]
    resources = [aws_sqs_queue.failed_writes.arn]
  }

  dynamic "statement" {
    for_each = var.screenshot_bucket == "" ? [] : [var.screenshot_bucket]
    content {
      sid       = "ScreenshotRead"
      actions   = ["s3:GetObject"]
      resources = ["arn:aws:s3:::${statement.value}/*"]
    }
  }
}

resource "aws_iam_role_policy" "parser" {
  name   = "${var.project_name}-runtime"
  role   = aws_iam_role.parser.id
  policy = data.aws_iam_policy_document.parser.json
}

resource "aws_lambda_function" "parser" {
  function_name = var.project_name
  role          = aws_iam_role.parser.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.parser.repository_url}:${var.image_tag}"
  architectures = [var.architecture]
  memory_size   = var.memory_mb
  timeout       = var.timeout_seconds

  # -1 removes the cap. Any other value needs account quota headroom.
  reserved_concurrent_executions = var.reserved_concurrency

  dead_letter_config {
    target_arn = aws_sqs_queue.failed_writes.arn
  }

  environment {
    variables = {
      TEL_TABLE_NAME              = aws_dynamodb_table.stats.name
      TEL_SCREENSHOT_BUCKET       = var.screenshot_bucket
      TEL_MAX_IMAGE_PIXELS        = tostring(var.max_image_pixels)
      TEL_FAILED_WRITES_QUEUE_URL = aws_sqs_queue.failed_writes.url
      TEL_LOG_LEVEL               = "INFO"
    }
  }

  logging_config {
    log_format = "Text"
    log_group  = aws_cloudwatch_log_group.parser.name
  }

  depends_on = [aws_iam_role_policy.parser]
}
