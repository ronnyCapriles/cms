variable "name" { type = string }
variable "region" { type = string }
variable "subnet_id" { type = string }
variable "security_group_id" { type = string }
variable "instance_profile_name" { type = string }
variable "data_volume_id" { type = string }
variable "bucket" { type = string }
variable "ecr_repository_url" {
  type        = string
  description = "Dual-stack: <acct>.dkr-ecr.<region>.on.aws/<repo>. The ordinary hostname has no AAAA record."
}
variable "parameter_prefix" { type = string }
variable "allowed_hosts" { type = string }
variable "csrf_origins" { type = string }

variable "instance_type" {
  type    = string
  default = "t4g.micro"
}

variable "root_size_gb" {
  type    = number
  default = 12
}

variable "poll_interval" {
  type        = string
  description = "systemd OnUnitActiveSec for the deploy poll"
  default     = "2min"
}

variable "tags" {
  type    = map(string)
  default = {}
}
