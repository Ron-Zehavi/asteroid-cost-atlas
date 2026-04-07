terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}

provider "aws" {
  region = "us-east-1"
}

variable "project" {
  type    = string
  default = "asteroid-cost-atlas"
}

# Look up shared resources created by the root infra/ stack
data "aws_ecr_repository" "app" {
  name = var.project
}

data "aws_iam_role" "apprunner_ecr_access" {
  name = "${var.project}-apprunner-ecr-access"
}

resource "aws_cloudwatch_log_group" "prod" {
  name              = "/apprunner/${var.project}-prod"
  retention_in_days = 14
}

resource "aws_apprunner_service" "prod" {
  service_name = "${var.project}-prod"

  source_configuration {
    authentication_configuration {
      access_role_arn = data.aws_iam_role.apprunner_ecr_access.arn
    }

    image_repository {
      image_identifier      = "${data.aws_ecr_repository.app.repository_url}:prod"
      image_repository_type = "ECR"

      image_configuration {
        port                          = "8000"
        runtime_environment_variables = {}
      }
    }

    auto_deployments_enabled = false
  }

  instance_configuration {
    cpu    = "1 vCPU"
    memory = "2 GB"
  }

  health_check_configuration {
    protocol            = "HTTP"
    path                = "/api/health"
    interval            = 10
    timeout             = 5
    healthy_threshold   = 1
    unhealthy_threshold = 5
  }

  tags = { Name = "${var.project}-prod" }
}

output "prod_url" {
  value = "https://${aws_apprunner_service.prod.service_url}"
}

output "prod_service_arn" {
  value = aws_apprunner_service.prod.arn
}
