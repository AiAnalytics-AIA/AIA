data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  name       = "aia-develop"
  ssm_prefix = "/aia/develop"

  artifacts_bucket = "${local.name}-artifacts-${local.account_id}"
  ops_bucket       = "${local.name}-ops-${local.account_id}"
  ecr_registry     = "${local.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com"
  images           = ["aia-api", "aia-worker", "aia-web"]

  # The EU inference profile and every EU foundation model it may route to.
  # Bedrock evaluates InvokeModel on both the profile ARN and the underlying
  # model ARN in the region it lands in, so both shapes are granted -- and only
  # for this one model id (ADR 0010).
  bedrock_foundation_model = replace(var.bedrock_model_id, "/^eu\\./", "")
  bedrock_model_arns = concat(
    ["arn:${data.aws_partition.current.partition}:bedrock:${var.aws_region}:${local.account_id}:inference-profile/${var.bedrock_model_id}"],
    [for r in ["eu-central-1", "eu-west-1", "eu-west-3", "eu-north-1", "eu-south-1", "eu-south-2", "eu-central-2"] :
    "arn:${data.aws_partition.current.partition}:bedrock:${r}::foundation-model/${local.bedrock_foundation_model}"]
  )
}

# ----------------------------------------------------------------------------- #
# Network: the default VPC is enough for one host with two public ports.
# ----------------------------------------------------------------------------- #

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
  filter {
    name   = "default-for-az"
    values = ["true"]
  }
}

locals {
  subnet_id = var.subnet_id != "" ? var.subnet_id : sort(data.aws_subnets.default.ids)[0]
}

resource "aws_security_group" "host" {
  name        = "${local.name}-host"
  description = "AIA develop host: HTTPS in, nothing else. Management is SSM, not SSH."
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "HTTP, redirected to HTTPS by Caddy"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    description = "HTTP/3"
    from_port   = 443
    to_port     = 443
    protocol    = "udp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    description = "Outbound: ECR, S3, SSM, ACME, Bedrock"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ----------------------------------------------------------------------------- #
# Storage: artifacts (the ArtifactStore) and ops (backups, deploy bundles).
# EU region, encrypted, versioned, private. Synthetic data only, so both may be
# destroyed with the environment.
# ----------------------------------------------------------------------------- #

resource "aws_s3_bucket" "artifacts" {
  bucket        = local.artifacts_bucket
  force_destroy = true
}

resource "aws_s3_bucket" "ops" {
  bucket        = local.ops_bucket
  force_destroy = true
}

locals {
  buckets = { artifacts = aws_s3_bucket.artifacts, ops = aws_s3_bucket.ops }
}

resource "aws_s3_bucket_public_access_block" "all" {
  for_each                = local.buckets
  bucket                  = each.value.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "all" {
  for_each = local.buckets
  bucket   = each.value.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "all" {
  for_each = local.buckets
  bucket   = each.value.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_policy" "tls_only" {
  for_each = local.buckets
  bucket   = each.value.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "DenyInsecureTransport"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:*"
      Resource  = [each.value.arn, "${each.value.arn}/*"]
      Condition = { Bool = { "aws:SecureTransport" = "false" } }
    }]
  })
}

resource "aws_s3_bucket_lifecycle_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  rule {
    id     = "tidy"
    status = "Enabled"
    filter {}
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "ops" {
  bucket = aws_s3_bucket.ops.id
  rule {
    id     = "backups"
    status = "Enabled"
    filter {
      prefix = "backups/"
    }
    expiration {
      days = var.backup_retention_days
    }
    noncurrent_version_expiration {
      noncurrent_days = 7
    }
  }
  rule {
    id     = "deploy-bundles"
    status = "Enabled"
    filter {
      prefix = "deploy/"
    }
    expiration {
      days = 90
    }
    noncurrent_version_expiration {
      noncurrent_days = 7
    }
  }
}

# ----------------------------------------------------------------------------- #
# Registry: one repository per image, pulled by the instance role.
# Tags stay mutable so `develop` can be re-pointed as a convenience alias; the
# deployment itself always pulls the immutable <sha> tag.
# ----------------------------------------------------------------------------- #

resource "aws_ecr_repository" "images" {
  for_each             = toset(local.images)
  name                 = each.value
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }
  encryption_configuration {
    encryption_type = "AES256"
  }
}

resource "aws_ecr_lifecycle_policy" "images" {
  for_each   = aws_ecr_repository.images
  repository = each.value.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep the 30 most recent images; older SHAs are rebuildable from git."
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 30
      }
      action = { type = "expire" }
    }]
  })
}

# ----------------------------------------------------------------------------- #
# Secrets and configuration: SSM Parameter Store, read by bin/write-env.sh.
# ----------------------------------------------------------------------------- #

resource "random_password" "postgres" {
  length  = 40
  special = false # the value is interpolated into a URL; keep it alphanumeric
}

resource "aws_ssm_parameter" "postgres_password" {
  name        = "${local.ssm_prefix}/postgres_password"
  description = "PostgreSQL password for the aia role on the develop host"
  type        = "SecureString"
  value       = random_password.postgres.result
}

# Non-secret configuration, so the host has one source for its env file. SSM
# refuses an empty String, so optional-and-empty values are simply absent and
# the compose file defaults them.
resource "aws_ssm_parameter" "config" {
  for_each = {
    aia_image_registry       = local.ecr_registry
    aia_public_hostname      = var.public_hostname
    aia_acme_email           = var.acme_email
    aws_region               = var.aws_region
    aia_storage_bucket       = aws_s3_bucket.artifacts.bucket
    aia_ops_bucket           = aws_s3_bucket.ops.bucket
    aia_cognito_user_pool_id = aws_cognito_user_pool.develop.id
    aia_cognito_client_id    = aws_cognito_user_pool_client.web.id
    aia_cognito_domain       = "${aws_cognito_user_pool_domain.develop.domain}.auth.${var.aws_region}.amazoncognito.com"
    aia_seed_owner_email     = var.seed_owner_email
  }
  name  = "${local.ssm_prefix}/${each.key}"
  type  = "String"
  value = each.value
}

# ----------------------------------------------------------------------------- #
# The instance role: the only credential the host has. Least privilege, one
# statement per purpose, and the Bedrock grant names one model (ADR 0010).
# ----------------------------------------------------------------------------- #

data "aws_iam_policy_document" "instance_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "instance" {
  name               = "${local.name}-instance"
  assume_role_policy = data.aws_iam_policy_document.instance_assume.json
}

resource "aws_iam_role_policy_attachment" "instance_ssm" {
  role       = aws_iam_role.instance.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy_attachment" "instance_cloudwatch" {
  role       = aws_iam_role.instance.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/CloudWatchAgentServerPolicy"
}

data "aws_iam_policy_document" "instance" {
  statement {
    sid       = "ArtifactStore"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket", "s3:GetBucketLocation"]
    resources = [aws_s3_bucket.artifacts.arn, "${aws_s3_bucket.artifacts.arn}/*"]
  }
  statement {
    sid       = "BackupsAndDeployBundles"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:ListBucket", "s3:GetBucketLocation"]
    resources = [aws_s3_bucket.ops.arn, "${aws_s3_bucket.ops.arn}/*"]
  }
  statement {
    sid       = "PullImages"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }
  statement {
    sid       = "PullImageLayers"
    actions   = ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer", "ecr:BatchCheckLayerAvailability", "ecr:DescribeImages", "ecr:ListImages"]
    resources = [for r in aws_ecr_repository.images : r.arn]
  }
  statement {
    sid       = "ReadConfiguration"
    actions   = ["ssm:GetParametersByPath", "ssm:GetParameter", "ssm:GetParameters"]
    resources = ["arn:${data.aws_partition.current.partition}:ssm:${var.aws_region}:${local.account_id}:parameter${local.ssm_prefix}/*"]
  }
  statement {
    sid       = "InvokeTheOneApprovedModel"
    actions   = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
    resources = local.bedrock_model_arns
  }
}

resource "aws_iam_role_policy" "instance" {
  name   = "${local.name}-instance"
  role   = aws_iam_role.instance.id
  policy = data.aws_iam_policy_document.instance.json
}

resource "aws_iam_instance_profile" "instance" {
  name = "${local.name}-instance"
  role = aws_iam_role.instance.name
}

# ----------------------------------------------------------------------------- #
# The host.
# ----------------------------------------------------------------------------- #

data "aws_ssm_parameter" "ubuntu_ami" {
  name = "/aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id"
}

resource "aws_instance" "host" {
  ami                         = data.aws_ssm_parameter.ubuntu_ami.value
  instance_type               = var.instance_type
  subnet_id                   = local.subnet_id
  vpc_security_group_ids      = [aws_security_group.host.id]
  iam_instance_profile        = aws_iam_instance_profile.instance.name
  associate_public_ip_address = true
  # No key pair: management is SSM Session Manager, audited, no port 22.
  key_name = null

  user_data = templatefile("${path.module}/user-data.yaml.tftpl", {
    aws_region = var.aws_region
  })
  user_data_replace_on_change = false

  metadata_options {
    http_tokens                 = "required" # IMDSv2 only
    http_put_response_hop_limit = 2          # containers reach IMDS through the docker bridge
    http_endpoint               = "enabled"
  }

  root_block_device {
    volume_type           = "gp3"
    volume_size           = var.root_volume_gb
    encrypted             = true
    delete_on_termination = true
    tags                  = { Name = "${local.name}-root", Snapshot = "daily" }
  }

  # The host is a pet by design at this size; a hardware failure is recovered
  # in place (alarm below) rather than by replacement.
  lifecycle {
    ignore_changes = [ami]
  }

  tags = { Name = local.name }
}

resource "aws_eip" "host" {
  domain = "vpc"
  tags   = { Name = local.name }
}

resource "aws_eip_association" "host" {
  instance_id   = aws_instance.host.id
  allocation_id = aws_eip.host.id
}

resource "aws_route53_record" "host" {
  count   = var.route53_zone_id != "" ? 1 : 0
  zone_id = var.route53_zone_id
  name    = var.public_hostname
  type    = "A"
  ttl     = 300
  records = [aws_eip.host.public_ip]
}

# ----------------------------------------------------------------------------- #
# Snapshots: the second copy of the database, behind the nightly pg_dump.
# ----------------------------------------------------------------------------- #

data "aws_iam_policy_document" "dlm_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["dlm.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "dlm" {
  name               = "${local.name}-dlm"
  assume_role_policy = data.aws_iam_policy_document.dlm_assume.json
}

resource "aws_iam_role_policy_attachment" "dlm" {
  role       = aws_iam_role.dlm.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/service-role/AWSDataLifecycleManagerServiceRole"
}

resource "aws_dlm_lifecycle_policy" "daily" {
  description        = "Daily snapshot of the develop root volume, 7 kept"
  execution_role_arn = aws_iam_role.dlm.arn
  state              = "ENABLED"

  policy_details {
    resource_types = ["VOLUME"]
    target_tags    = { Snapshot = "daily" }
    schedule {
      name = "daily"
      create_rule {
        interval      = 24
        interval_unit = "HOURS"
        times         = ["03:30"]
      }
      retain_rule {
        count = 7
      }
      copy_tags = true
    }
  }
}

# ----------------------------------------------------------------------------- #
# Observability: one log group, three alarms, one email.
# ----------------------------------------------------------------------------- #

resource "aws_cloudwatch_log_group" "develop" {
  name              = "/aia/develop"
  retention_in_days = 30
}

resource "aws_sns_topic" "alerts" {
  name = "${local.name}-alerts"
}

resource "aws_sns_topic_subscription" "alerts_email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

resource "aws_cloudwatch_metric_alarm" "system_check" {
  alarm_name          = "${local.name}-system-check-failed"
  alarm_description   = "The host's underlying hardware failed a status check; EC2 recovers it in place."
  namespace           = "AWS/EC2"
  metric_name         = "StatusCheckFailed_System"
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 2
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  dimensions          = { InstanceId = aws_instance.host.id }
  alarm_actions = [
    "arn:${data.aws_partition.current.partition}:automate:${var.aws_region}:ec2:recover",
    aws_sns_topic.alerts.arn,
  ]
}

resource "aws_cloudwatch_metric_alarm" "disk" {
  alarm_name          = "${local.name}-disk-85-percent"
  alarm_description   = "Root volume over 85 % (CloudWatch agent). Prune images or grow the volume (README § Resize)."
  namespace           = "CWAgent"
  metric_name         = "disk_used_percent"
  statistic           = "Maximum"
  period              = 300
  evaluation_periods  = 2
  threshold           = 85
  comparison_operator = "GreaterThanThreshold"
  dimensions          = { InstanceId = aws_instance.host.id, path = "/", fstype = "ext4", device = "nvme0n1p1" }
  alarm_actions       = [aws_sns_topic.alerts.arn]
  treat_missing_data  = "missing"
}

resource "aws_cloudwatch_metric_alarm" "cpu" {
  alarm_name          = "${local.name}-cpu-90-percent"
  alarm_description   = "Sustained CPU over 90 % for 30 minutes; a simulation may need a larger instance."
  namespace           = "AWS/EC2"
  metric_name         = "CPUUtilization"
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 6
  threshold           = 90
  comparison_operator = "GreaterThanThreshold"
  dimensions          = { InstanceId = aws_instance.host.id }
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

resource "aws_budgets_budget" "develop" {
  name         = "${local.name}-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  cost_filter {
    name   = "TagKeyValue"
    values = ["user:Environment$develop"]
  }

  dynamic "notification" {
    for_each = [80, 100]
    content {
      comparison_operator        = "GREATER_THAN"
      threshold                  = notification.value
      threshold_type             = "PERCENTAGE"
      notification_type          = "ACTUAL"
      subscriber_email_addresses = [var.alert_email]
    }
  }
}
