
data "terraform_remote_state" "vpc" {
  backend = "s3"

  config = {
    bucket = var.state_bucket
    key    = "prod/vpc/terraform.tfstate"
    region = var.region
  }
}

module "security_group" {
  source = "../../modules/v1/security-group"

  name   = "${var.project}-${var.environment}"
  vpc_id = data.terraform_remote_state.vpc.outputs.vpc_id
}
