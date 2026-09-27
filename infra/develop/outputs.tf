output "instance_id" {
  description = "GitHub variable AIA_DEVELOP_INSTANCE_ID; also the SSM Session Manager target."
  value       = aws_instance.host.id
}

output "public_ip" {
  description = "Point the A record for public_hostname here (Terraform does it when route53_zone_id is set)."
  value       = aws_eip.host.public_ip
}

output "public_url" {
  value = "https://${var.public_hostname}/"
}

output "ecr_registry" {
  description = "GitHub variable AIA_ECR_REGISTRY."
  value       = local.ecr_registry
}

output "ecr_repositories" {
  value = { for k, r in aws_ecr_repository.images : k => r.repository_url }
}

output "artifacts_bucket" {
  value = aws_s3_bucket.artifacts.bucket
}

output "ops_bucket" {
  description = "GitHub variable AIA_OPS_BUCKET. Holds backups/ and deploy/."
  value       = aws_s3_bucket.ops.bucket
}

output "github_deploy_role_arn" {
  description = "GitHub variable AIA_DEPLOY_ROLE_ARN."
  value       = aws_iam_role.github_deploy.arn
}

output "cognito_user_pool_id" {
  value = aws_cognito_user_pool.develop.id
}

output "cognito_client_id" {
  value = aws_cognito_user_pool_client.web.id
}

output "cognito_domain" {
  value = "${aws_cognito_user_pool_domain.develop.domain}.auth.${var.aws_region}.amazoncognito.com"
}

output "google_redirect_uri" {
  description = "Add this to the Google OAuth client's authorised redirect URIs."
  value       = "https://${aws_cognito_user_pool_domain.develop.domain}.auth.${var.aws_region}.amazoncognito.com/oauth2/idpresponse"
}

output "ssm_parameter_prefix" {
  value = local.ssm_prefix
}

output "alerts_topic_arn" {
  value = aws_sns_topic.alerts.arn
}

output "bedrock_model_arns_granted" {
  description = "Exactly what the instance role may invoke (ADR 0010)."
  value       = local.bedrock_model_arns
}
