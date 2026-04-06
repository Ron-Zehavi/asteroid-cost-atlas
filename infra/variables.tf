variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "aws_profile" {
  description = "AWS CLI profile name (null in CI/CD where OIDC provides credentials)"
  type        = string
  default     = "asteroid"
}

variable "project" {
  description = "Project name used for resource naming"
  type        = string
  default     = "asteroid-cost-atlas"
}

variable "container_port" {
  description = "Port the container listens on"
  type        = number
  default     = 8000
}

variable "github_org" {
  description = "GitHub org/user for OIDC trust"
  type        = string
  default     = "Ron-Zehavi"
}

variable "github_repo" {
  description = "GitHub repo name for OIDC trust"
  type        = string
  default     = "asteroid-cost-atlas"
}
