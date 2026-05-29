data "aws_caller_identity" "current" {}

resource "aws_s3_bucket" "cf_logs_prod" {
  bucket        = "${var.project}-cf-logs-prod-${data.aws_caller_identity.current.account_id}"
  force_destroy = true
}

resource "aws_s3_bucket_ownership_controls" "cf_logs_prod" {
  bucket = aws_s3_bucket.cf_logs_prod.id
  rule {
    object_ownership = "BucketOwnerPreferred"
  }
}

resource "aws_s3_bucket_acl" "cf_logs_prod" {
  depends_on = [aws_s3_bucket_ownership_controls.cf_logs_prod]
  bucket     = aws_s3_bucket.cf_logs_prod.id
  acl        = "log-delivery-write"
}

resource "aws_s3_bucket_lifecycle_configuration" "cf_logs_prod" {
  bucket = aws_s3_bucket.cf_logs_prod.id
  rule {
    id     = "expire-old-logs"
    status = "Enabled"
    filter {}
    expiration {
      days = 90
    }
  }
}

resource "aws_cloudfront_distribution" "prod" {
  enabled         = true
  comment         = "${var.project}-prod"
  is_ipv6_enabled = true
  price_class     = "PriceClass_100"

  origin {
    domain_name = aws_apprunner_service.prod.service_url
    origin_id   = "apprunner-prod"
    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  default_cache_behavior {
    target_origin_id       = "apprunner-prod"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true

    cache_policy_id          = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad"
    origin_request_policy_id = "b689b0a8-53d0-40ab-baf2-68738e2966ac"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  logging_config {
    bucket          = aws_s3_bucket.cf_logs_prod.bucket_domain_name
    prefix          = "prod/"
    include_cookies = false
  }

  tags = { Name = "${var.project}-prod" }
}

output "cloudfront_prod_url" {
  description = "CloudFront URL fronting prod App Runner"
  value       = "https://${aws_cloudfront_distribution.prod.domain_name}"
}

output "cf_logs_prod_bucket" {
  description = "S3 bucket holding CloudFront access logs for prod"
  value       = aws_s3_bucket.cf_logs_prod.bucket
}
