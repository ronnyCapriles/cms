variable "project" {
  type    = string
  default = "portfolio"
}

variable "environment" { type = string }
variable "region" { type = string }

variable "state_bucket" { type = string }

variable "parameter_prefix" {
  type    = string
  default = "/portfolio/prod"
}

variable "allowed_subjects" {
  type        = list(string)
  description = "Scope this; a bare repo:owner/repo:* lets any branch assume the role."
}
