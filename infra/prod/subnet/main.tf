
data "terraform_remote_state" "vpc" {
  backend = "s3"

  config = {
    bucket = var.state_bucket
    key    = "prod/vpc/terraform.tfstate"
    region = var.region
  }
}

module "subnet" {
  source = "../../modules/v1/subnet"

  name                = "${var.project}-${var.environment}"
  vpc_id              = data.terraform_remote_state.vpc.outputs.vpc_id
  vpc_cidr_block      = data.terraform_remote_state.vpc.outputs.cidr_block
  vpc_ipv6_cidr_block = data.terraform_remote_state.vpc.outputs.ipv6_cidr_block
  route_table_id      = data.terraform_remote_state.vpc.outputs.route_table_id
  availability_zone   = var.availability_zone
}
