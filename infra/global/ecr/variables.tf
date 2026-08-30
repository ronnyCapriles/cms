variable "project" {
  type    = string
  default = "portfolio"
}

variable "environment" { type = string }
variable "region" { type = string }

variable "keep_images" {
  type    = number
  default = 10
}
