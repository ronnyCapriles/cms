variable "name" { type = string }
variable "vpc_id" { type = string }
variable "vpc_cidr_block" { type = string }
variable "vpc_ipv6_cidr_block" { type = string }
variable "route_table_id" { type = string }
variable "availability_zone" { type = string }

variable "index" {
  type        = number
  description = "Which /24 and /64 to carve. IPv6 subnets must be /64."
  default     = 0
}

variable "tags" {
  type    = map(string)
  default = {}
}
