resource "aws_dynamodb_table" "stats" {
  name         = "${var.project_name}-stats"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "match_id"
  range_key    = "player_slot"

  attribute {
    name = "match_id"
    type = "S"
  }

  attribute {
    name = "player_slot"
    type = "N"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }
}
