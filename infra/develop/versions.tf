# One small root for the develop environment (ADR 0009). No modules: the whole
# environment should be readable in one sitting, and a module hierarchy buys
# nothing until a second environment needs the same shapes.
#
# State: keep it out of the repository. The simplest safe choice is an S3
# backend in the same account; uncomment and fill in once the bucket exists, or
# pass `-backend-config` at init. Local state is acceptable only for the very
# first apply by one person.

terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.70"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # backend "s3" {
  #   bucket       = "aia-terraform-state-<account-id>"
  #   key          = "develop/terraform.tfstate"
  #   region       = "eu-central-1"
  #   encrypt      = true
  #   use_lockfile = true
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "aia"
      Environment = "develop"
      ManagedBy   = "terraform"
      Repository  = var.github_repository
    }
  }
}
