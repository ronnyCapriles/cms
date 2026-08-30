variable "name" { type = string }
variable "region" { type = string }

variable "cidr_block" {
  type        = string
  description = "IPv4 range. Never routed to the internet; it exists so the S3 gateway endpoint has an address family."
  default     = "10.0.0.0/16"
}

variable "tags" {
  type    = map(string)
  default = {}
}
