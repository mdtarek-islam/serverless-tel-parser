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
  default     = "x86_64"

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

variable "log_retention_days" {
  description = "CloudWatch log retention."
  type        = number
  default     = 14
}
