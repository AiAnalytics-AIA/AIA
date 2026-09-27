# GitHub Actions -> AWS, with OIDC and no stored keys (ARCHITECTURE.md §9).
#
# The role may be assumed only by a job of this repository running in the
# named GitHub environment, and may do only what the deploy needs: push the
# images in local.images, upload one deploy bundle, and run one SSM command on
# one instance. It cannot read the database, the artifacts or a parameter.

data "aws_iam_openid_connect_provider" "github" {
  count = var.create_github_oidc_provider ? 0 : 1
  url   = "https://token.actions.githubusercontent.com"
}

resource "aws_iam_openid_connect_provider" "github" {
  count          = var.create_github_oidc_provider ? 1 : 0
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
  # AWS validates GitHub's OIDC issuer against its own trust store; the
  # thumbprint list is required by the API but not consulted for this issuer.
  # These are GitHub's published intermediate thumbprints, for completeness.
  thumbprint_list = [
    "6938fd4d98bab03faadb97b34396831e3780aea1",
    "1c58a3a8518e8759bf075b76b750d4f2df264fcd",
  ]
}

variable "create_github_oidc_provider" {
  description = "An account holds at most one GitHub OIDC provider. Set false if it already exists; it is then looked up."
  type        = bool
  default     = true
}

variable "github_oidc_subject" {
  description = "Exact GitHub OIDC sub for this repository's develop environment. Set this when the organization enables immutable OIDC subjects; otherwise the default repository-name subject is used."
  type        = string
  default     = null
}

locals {
  github_oidc_arn = var.create_github_oidc_provider ? aws_iam_openid_connect_provider.github[0].arn : data.aws_iam_openid_connect_provider.github[0].arn
}

data "aws_iam_policy_document" "github_assume" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [local.github_oidc_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    # Scoped to the GitHub environment, not the branch: the environment is where
    # a human can add required reviewers later, and only the deploy workflow
    # runs in it.
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = [var.github_oidc_subject != null ? var.github_oidc_subject : "repo:${var.github_repository}:environment:${var.github_environment}"]
    }
  }
}

resource "aws_iam_role" "github_deploy" {
  name                 = "${local.name}-github-deploy"
  assume_role_policy   = data.aws_iam_policy_document.github_assume.json
  max_session_duration = 3600
}

data "aws_iam_policy_document" "github_deploy" {
  statement {
    sid       = "EcrLogin"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }
  statement {
    sid = "PushImages"
    actions = [
      "ecr:BatchCheckLayerAvailability", "ecr:CompleteLayerUpload", "ecr:InitiateLayerUpload",
      "ecr:PutImage", "ecr:UploadLayerPart", "ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer",
      "ecr:DescribeImages", "ecr:ListImages",
    ]
    resources = [for r in aws_ecr_repository.images : r.arn]
  }
  statement {
    sid       = "UploadDeployBundle"
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.ops.arn}/deploy/*"]
  }
  statement {
    sid     = "RunTheDeployOnTheHost"
    actions = ["ssm:SendCommand"]
    resources = [
      aws_instance.host.arn,
      "arn:${data.aws_partition.current.partition}:ssm:${var.aws_region}::document/AWS-RunShellScript",
    ]
  }
  statement {
    sid       = "ReadTheCommandResult"
    actions   = ["ssm:GetCommandInvocation", "ssm:ListCommandInvocations", "ssm:ListCommands"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "github_deploy" {
  name   = "${local.name}-github-deploy"
  role   = aws_iam_role.github_deploy.id
  policy = data.aws_iam_policy_document.github_deploy.json
}
