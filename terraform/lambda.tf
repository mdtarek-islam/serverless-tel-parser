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

  statement {
    sid       = "StatsPut"
    actions   = ["dynamodb:PutItem"]
    resources = [aws_dynamodb_table.stats.arn]
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

  environment {
    variables = {
      TEL_TABLE_NAME        = aws_dynamodb_table.stats.name
      TEL_SCREENSHOT_BUCKET = var.screenshot_bucket
      TEL_LOG_LEVEL         = "INFO"
    }
  }

  logging_config {
    log_format = "Text"
    log_group  = aws_cloudwatch_log_group.parser.name
  }

  depends_on = [aws_iam_role_policy.parser]
}
