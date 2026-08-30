variable "project" {
  type    = string
  default = "portfolio"
}

variable "environment" { type = string }
variable "region" { type = string }

variable "bucket_name" {
  type        = string
  description = "Globally unique. Holds media/ and deploy/."
}
