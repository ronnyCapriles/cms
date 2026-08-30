variable "thumbprints" {
  type        = list(string)
  description = "AWS no longer validates these for GitHub, but the argument is still accepted."
  default     = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

variable "tags" {
  type    = map(string)
  default = {}
}
