resource "aws_s3_bucket" "cf_logs_dev" {
  bucket        = "${var.project}-cf-logs-dev-${data.aws_caller_identity.current.account_id}"
  force_destroy = true
}

resource "aws_s3_bucket_ownership_controls" "cf_logs_dev" {
  bucket = aws_s3_bucket.cf_logs_dev.id
  rule {
    object_ownership = "BucketOwnerPreferred"
  }
}

resource "aws_s3_bucket_acl" "cf_logs_dev" {
  depends_on = [aws_s3_bucket_ownership_controls.cf_logs_dev]
  bucket     = aws_s3_bucket.cf_logs_dev.id
  acl        = "log-delivery-write"
}

resource "aws_s3_bucket_lifecycle_configuration" "cf_logs_dev" {
  bucket = aws_s3_bucket.cf_logs_dev.id
  rule {
    id     = "expire-old-logs"
    status = "Enabled"
    filter {}
    expiration {
      days = 30
    }
  }
}

resource "aws_cloudfront_distribution" "dev" {
  enabled         = true
  comment         = "${var.project}-dev"
  is_ipv6_enabled = true
  price_class     = "PriceClass_100"

  origin {
    domain_name = aws_apprunner_service.app.service_url
    origin_id   = "apprunner-dev"
    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  default_cache_behavior {
    target_origin_id       = "apprunner-dev"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true

    # Managed-CachingDisabled — pass everything through (cache later if needed)
    cache_policy_id = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad"
    # Managed-AllViewerExceptHostHeader — App Runner LB rejects requests if Host is the CF domain
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
    bucket          = aws_s3_bucket.cf_logs_dev.bucket_domain_name
    prefix          = "dev/"
    include_cookies = false
  }

  tags = { Name = "${var.project}-dev" }
}

output "cloudfront_dev_url" {
  description = "CloudFront URL fronting dev App Runner"
  value       = "https://${aws_cloudfront_distribution.dev.domain_name}"
}

output "cf_logs_dev_bucket" {
  description = "S3 bucket holding CloudFront access logs for dev"
  value       = aws_s3_bucket.cf_logs_dev.bucket
}
