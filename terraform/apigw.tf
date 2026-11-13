resource "aws_apigatewayv2_api" "http" {
  name          = "${var.project_name}-http"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "parser" {
  api_id                 = aws_apigatewayv2_api.http.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.parser.invoke_arn
  payload_format_version = "2.0"
}

# Used only when route_authorization is JWT.
resource "aws_apigatewayv2_authorizer" "jwt" {
  count = var.route_authorization == "JWT" ? 1 : 0

  api_id           = aws_apigatewayv2_api.http.id
  name             = "${var.project_name}-jwt"
  authorizer_type  = "JWT"
  identity_sources = ["$request.header.Authorization"]

  jwt_configuration {
    issuer   = var.jwt_issuer
    audience = var.jwt_audience
  }

  lifecycle {
    precondition {
      condition     = var.jwt_issuer != "" && length(var.jwt_audience) > 0
      error_message = "jwt_issuer and jwt_audience are required when route_authorization is JWT."
    }
  }
}

resource "aws_apigatewayv2_route" "parse" {
  api_id             = aws_apigatewayv2_api.http.id
  route_key          = "POST /parse"
  target             = "integrations/${aws_apigatewayv2_integration.parser.id}"
  authorization_type = var.route_authorization
  authorizer_id      = var.route_authorization == "JWT" ? aws_apigatewayv2_authorizer.jwt[0].id : null
}

resource "aws_cloudwatch_log_group" "access" {
  name              = "/aws/apigateway/${var.project_name}-http"
  retention_in_days = var.log_retention_days
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.http.id
  name        = "$default"
  auto_deploy = true

  default_route_settings {
    throttling_burst_limit = 50
    throttling_rate_limit  = 20
  }

  # JSON access log. The path field omits the query string. No body is logged.
  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.access.arn
    format = jsonencode({
      requestId        = "$context.requestId"
      ip               = "$context.identity.sourceIp"
      requestTime      = "$context.requestTime"
      httpMethod       = "$context.httpMethod"
      path             = "$context.path"
      status           = "$context.status"
      responseLength   = "$context.responseLength"
      latency          = "$context.responseLatency"
      integrationError = "$context.integrationErrorMessage"
      authorizerError  = "$context.authorizer.error"
    })
  }
}

resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowHttpApiInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.parser.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http.execution_arn}/*/*/parse"
}
