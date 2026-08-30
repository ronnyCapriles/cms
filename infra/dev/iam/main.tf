
data "terraform_remote_state" "ecr" {
  backend = "s3"

  config = {
    bucket = var.state_bucket
    key    = "global/ecr/terraform.tfstate"
    region = var.region
  }
}

data "terraform_remote_state" "oidc" {
  backend = "s3"

  config = {
    bucket = var.state_bucket
    key    = "global/iam/terraform.tfstate"
    region = var.region
  }
}

data "terraform_remote_state" "s3" {
  backend = "s3"

  config = {
    bucket = var.state_bucket
    key    = "dev/s3/terraform.tfstate"
    region = var.region
  }
}

locals {
  parameter_arns = [
    "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter${var.parameter_prefix}/*",
  ]
}

data "aws_caller_identity" "current" {}

module "instance_role" {
  source = "../../modules/v1/iam-instance-role"

  name               = "${var.project}-${var.environment}-instance"
  ecr_repository_arn = data.terraform_remote_state.ecr.outputs.repository_arn
  bucket_arn         = data.terraform_remote_state.s3.outputs.bucket_arn
  parameter_arns     = local.parameter_arns
}

module "github_role" {
  source = "../../modules/v1/iam-github-role"

  name               = "${var.project}-${var.environment}-github"
  oidc_provider_arn  = data.terraform_remote_state.oidc.outputs.provider_arn
  ecr_repository_arn = data.terraform_remote_state.ecr.outputs.repository_arn
  bucket_arn         = data.terraform_remote_state.s3.outputs.bucket_arn
  allowed_subjects   = var.allowed_subjects
}
