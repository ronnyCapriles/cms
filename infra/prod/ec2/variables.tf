variable "project" {
  type    = string
  default = "portfolio"
}

variable "environment" { type = string }
variable "region" { type = string }

variable "state_bucket" { type = string }

variable "parameter_prefix" { type = string }

variable "allowed_hosts" {
  type        = string
  description = "Comma-separated. Keep 127.0.0.1 in it: the health check asks as that host."
}

variable "csrf_origins" {
  type        = string
  description = "Comma-separated, scheme included."
}

variable "instance_type" {
  type    = string
  default = "t4g.micro"
}

variable "poll_interval" {
  type    = string
  default = "2min"
}
