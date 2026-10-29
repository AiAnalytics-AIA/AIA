output "github_oidc_provider_arn" {
  description = "The account's GitHub OIDC provider, which develop and production look up."
  value       = aws_iam_openid_connect_provider.github.arn
}

output "cloudtrail_bucket" {
  value = aws_s3_bucket.cloudtrail.bucket
}
