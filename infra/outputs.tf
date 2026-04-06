output "app_url" {
  description = "Public URL of the application (HTTPS)"
  value       = "https://${aws_apprunner_service.app.service_url}"
}

output "ecr_repository" {
  description = "ECR repository URL"
  value       = aws_ecr_repository.app.repository_url
}

output "github_actions_role_arn" {
  description = "IAM role ARN for GitHub Actions OIDC"
  value       = aws_iam_role.github_actions.arn
}

output "apprunner_service_arn" {
  description = "App Runner service ARN"
  value       = aws_apprunner_service.app.arn
}

output "aws_region" {
  description = "AWS region"
  value       = var.aws_region
}
