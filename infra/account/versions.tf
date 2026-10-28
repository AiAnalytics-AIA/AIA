# The account-level root (ADR 0031 §2): what exists once per AWS account and every environment
# relies on. Develop and production share this account; each looks these up and never declares
# them, so neither environment's destroy can reach them. One root, no modules, as ADR 0009 asks.

terraform {
  # 1.10 is the first release whose S3 backend takes `use_lockfile`.
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.70"
    }
  }

  # The same state bucket as develop, under its own key and lock.
  backend "s3" {
    bucket       = "aia-terraform-state-311141567391"
    key          = "account/terraform.tfstate"
    region       = "eu-central-1"
    encrypt      = true
    use_lockfile = true
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "aia"
      Environment = "account"
      ManagedBy   = "terraform"
      Repository  = var.github_repository
    }
  }
}
