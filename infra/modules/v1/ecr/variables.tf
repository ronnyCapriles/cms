variable "name" { type = string }
variable "region" { type = string }

variable "keep_images" {
  type    = number
  default = 10
}

variable "tags" {
  type    = map(string)
  default = {}
}
