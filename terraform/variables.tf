variable "project_name" {
  description = "Prefix for every resource name."
  type        = string
  default     = "tel-parser"
}

variable "aws_region" {
  description = "AWS region for all resources."
  type        = string
  default     = "eu-west-2"
}

variable "image_tag" {
  description = "ECR image tag to deploy. Push the image before apply."
  type        = string
}

variable "architecture" {
  description = "Lambda architecture. Must match the platform of the pushed image."
  type        = string
  default     = "arm64"

  validation {
    condition     = contains(["x86_64", "arm64"], var.architecture)
    error_message = "architecture must be x86_64 or arm64."
  }
}

variable "memory_mb" {
  description = "Lambda memory. CPU share scales with memory."
  type        = number
  default     = 1024
}

variable "timeout_seconds" {
  description = "Lambda timeout."
  type        = number
  default     = 15
}

variable "screenshot_bucket" {
  description = "Optional S3 bucket for s3_key requests. Empty disables S3 read access."
  type        = string
  default     = ""
}

variable "reserved_concurrency" {
  description = "Reserved concurrent executions for the function. -1 removes the cap. Needs account quota headroom."
  type        = number
  default     = 10

  validation {
    condition     = var.reserved_concurrency >= -1
    error_message = "reserved_concurrency must be -1 or higher."
  }
}

variable "max_image_pixels" {
  description = "Pixel cap for a decoded screenshot. Sets TEL_MAX_IMAGE_PIXELS."
  type        = number
  default     = 16000000

  validation {
    condition     = var.max_image_pixels >= 4096 && var.max_image_pixels <= 89478485
    error_message = "max_image_pixels must be between 4096 and 89478485."
  }
}

variable "alarm_topic_arn" {
  description = "Optional SNS topic ARN notified when the failed-writes alarm fires. Empty sends no notification."
  type        = string
  default     = ""
}

variable "route_authorization" {
  description = "Authorisation for POST /parse: AWS_IAM (default), JWT or NONE. NONE leaves the route open."
  type        = string
  default     = "AWS_IAM"

  validation {
    condition     = contains(["AWS_IAM", "JWT", "NONE"], var.route_authorization)
    error_message = "route_authorization must be AWS_IAM, JWT or NONE."
  }
}

variable "jwt_issuer" {
  description = "JWT issuer URL. Required when route_authorization is JWT."
  type        = string
  default     = ""
}

variable "jwt_audience" {
  description = "JWT audience values. Required when route_authorization is JWT."
  type        = list(string)
  default     = []
}

variable "log_retention_days" {
  description = "CloudWatch log retention."
  type        = number
  default     = 14
}
