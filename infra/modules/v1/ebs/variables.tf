variable "name" { type = string }
variable "availability_zone" { type = string }

variable "size_gb" {
  type    = number
  default = 10
}

variable "snapshot_time" {
  type        = string
  description = "UTC, HH:MM"
  default     = "07:00"
}

variable "snapshot_retention" {
  type    = number
  default = 7
}

variable "tags" {
  type    = map(string)
  default = {}
}
