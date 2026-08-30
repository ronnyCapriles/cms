output "repository_name" { value = aws_ecr_repository.this.name }
output "repository_arn" { value = aws_ecr_repository.this.arn }

# What CI pushes to. The runner has IPv4, so it uses the ordinary endpoint.
output "repository_url" { value = aws_ecr_repository.this.repository_url }

# What the instance pulls from. Same repository; the ordinary hostname publishes
# no AAAA record, and the instance has no IPv4 route to the internet.
output "registry_dualstack" {
  value = "${data.aws_caller_identity.current.account_id}.dkr-ecr.${var.region}.on.aws"
}

output "repository_url_dualstack" {
  value = "${data.aws_caller_identity.current.account_id}.dkr-ecr.${var.region}.on.aws/${aws_ecr_repository.this.name}"
}
