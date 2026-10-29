variable "aws_region" {
  description = "The region of the trail's bucket and the provider. The trail itself is multi-region."
  type        = string
  default     = "eu-central-1"
}

variable "github_repository" {
  description = "owner/repo, for the Repository tag."
  type        = string
  default     = "AiAnalytics-AIA/AIA"
}

variable "cloudtrail_retention_days" {
  description = "How long the trail's log files are kept before they expire."
  type        = number
  default     = 365
}
