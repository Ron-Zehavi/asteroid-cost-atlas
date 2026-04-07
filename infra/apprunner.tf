resource "aws_cloudwatch_log_group" "app" {
  name              = "/apprunner/${var.project}-dev"
  retention_in_days = 14
}

resource "aws_apprunner_service" "app" {
  service_name = "${var.project}-dev"

  source_configuration {
    authentication_configuration {
      access_role_arn = aws_iam_role.apprunner_ecr_access.arn
    }

    image_repository {
      image_identifier      = "${aws_ecr_repository.app.repository_url}:dev"
      image_repository_type = "ECR"

      image_configuration {
        port                          = tostring(var.container_port)
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

  tags = { Name = var.project }
}
