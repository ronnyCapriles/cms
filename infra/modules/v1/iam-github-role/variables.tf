variable "name" { type = string }
variable "oidc_provider_arn" { type = string }
variable "ecr_repository_arn" { type = string }
variable "bucket_arn" { type = string }

variable "allowed_subjects" {
  type        = list(string)
  description = "e.g. [\"repo:owner/repo:ref:refs/heads/main\"]"
}

variable "tags" {
  type    = map(string)
  default = {}
}
