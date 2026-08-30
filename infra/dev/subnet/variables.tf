variable "project" {
  type    = string
  default = "portfolio"
}

variable "environment" { type = string }
variable "region" { type = string }

variable "state_bucket" { type = string }

variable "availability_zone" {
  type        = string
  description = "Pinned: changing it recreates the subnet and orphans the data volume."
}
