output "parse_url" {
  description = "POST endpoint for screenshot parsing."
  value       = "${aws_apigatewayv2_api.http.api_endpoint}/parse"
}

output "ecr_repository_url" {
  description = "Push the Lambda image here before apply."
  value       = aws_ecr_repository.parser.repository_url
}

output "stats_table_name" {
  value = aws_dynamodb_table.stats.name
}

output "lambda_function_name" {
  value = aws_lambda_function.parser.function_name
}
