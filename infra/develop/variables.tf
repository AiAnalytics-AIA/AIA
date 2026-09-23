variable "aws_region" {
  description = "An EU region approved under ADR 0008. Frankfurt hosts the EU Bedrock inference profiles."
  type        = string
  default     = "eu-central-1"

  validation {
    condition     = startswith(var.aws_region, "eu-")
    error_message = "The develop environment must run in an EU region (ADR 0008)."
  }
}

variable "public_hostname" {
  description = "The one public hostname, e.g. dev.example.com. Caddy obtains its certificate for it."
  type        = string
}

variable "acme_email" {
  description = "Contact address for the ACME account Caddy registers."
  type        = string
}

variable "alert_email" {
  description = "Where CloudWatch alarms and the budget alerts are sent."
  type        = string
}

variable "seed_owner_email" {
  description = "The Google Workspace address the develop seed provisions as organization owner. Must match the account that will sign in."
  type        = string
}

variable "github_repository" {
  description = "owner/repo whose `develop` GitHub environment may assume the deploy role."
  type        = string
  default     = "AiAnalytics-AIA/AIA"
}

variable "github_environment" {
  description = "The GitHub environment name the deploy workflow runs in; the OIDC trust is scoped to it."
  type        = string
  default     = "develop"
}

variable "instance_type" {
  description = "Modest by design; raise it and re-apply to resize (README § Resize)."
  type        = string
  default     = "t3a.medium"
}

variable "root_volume_gb" {
  description = "Root volume holding Docker images and the PostgreSQL volume."
  type        = number
  default     = 80
}

variable "subnet_id" {
  description = "Subnet for the instance. Empty selects a subnet of the default VPC."
  type        = string
  default     = ""
}

variable "route53_zone_id" {
  description = "If the hostname's zone is in Route 53, its zone id; Terraform then manages the A record. Empty means DNS is managed elsewhere (README § Human actions)."
  type        = string
  default     = ""
}

variable "cognito_domain_prefix" {
  description = "Prefix for the Cognito hosted UI domain: <prefix>.auth.<region>.amazoncognito.com. Globally unique."
  type        = string
  default     = "aia-develop"
}

variable "google_client_id" {
  description = "OAuth client id from Google Cloud, for the Google Workspace federation (README § Human actions)."
  type        = string
}

variable "google_client_secret" {
  description = "The matching client secret. Held by Cognito only; never by AIA."
  type        = string
  sensitive   = true
}

variable "google_hosted_domain" {
  description = "The Google Workspace domain whose accounts may sign in (Google's `hd` parameter). Cognito still only admits users an administrator has provisioned."
  type        = string
}

variable "bedrock_model_id" {
  description = <<-EOT
    The ONE pinned model the instance role may invoke: an EU cross-region inference profile id, written in
    full with its version suffix (ADR 0010). Verify availability and terms in the console first; the role
    is granted this profile and its EU foundation-model ARNs and nothing else. Example shape:
    eu.anthropic.claude-sonnet-4-5-20250929-v1:0
  EOT
  type        = string

  validation {
    condition     = startswith(var.bedrock_model_id, "eu.") && !endswith(var.bedrock_model_id, "latest")
    error_message = "bedrock_model_id must be an EU inference profile id (eu.…), pinned to a version, never a floating alias."
  }
}

variable "monthly_budget_usd" {
  description = "AWS Budgets ceiling for the account's develop-tagged spend; alerts at 80 % and 100 %."
  type        = number
  default     = 100
}

variable "backup_retention_days" {
  description = "How long pg_dump objects stay in the ops bucket."
  type        = number
  default     = 30
}
