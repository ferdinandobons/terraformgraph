# examples/complex/variables.tf

variable "project" {
  description = "Project name"
  type        = string
  default     = "myapp"
}

variable "region" {
  description = "AWS region"
  type        = string
  default     = "eu-west-1"
}

variable "domain" {
  description = "Domain name for the application"
  type        = string
  default     = "example.com"
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
  default     = "prod"
}
