variable "project" {
  type    = string
  default = "portfolio"
}

variable "environment" { type = string }
variable "region" { type = string }

variable "cidr_block" {
  type    = string
  default = "10.0.0.0/16"
}
