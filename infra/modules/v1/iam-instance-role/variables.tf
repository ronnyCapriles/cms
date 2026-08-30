variable "name" { type = string }
variable "ecr_repository_arn" { type = string }
variable "bucket_arn" { type = string }
variable "parameter_arns" { type = list(string) }

variable "tags" {
  type    = map(string)
  default = {}
}
