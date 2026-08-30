
data "terraform_remote_state" "subnet" {
  backend = "s3"

  config = {
    bucket = var.state_bucket
    key    = "prod/subnet/terraform.tfstate"
    region = var.region
  }
}

data "terraform_remote_state" "sg" {
  backend = "s3"

  config = {
    bucket = var.state_bucket
    key    = "prod/security-group/terraform.tfstate"
    region = var.region
  }
}

data "terraform_remote_state" "iam" {
  backend = "s3"

  config = {
    bucket = var.state_bucket
    key    = "prod/iam/terraform.tfstate"
    region = var.region
  }
}

data "terraform_remote_state" "ebs" {
  backend = "s3"

  config = {
    bucket = var.state_bucket
    key    = "prod/ebs/terraform.tfstate"
    region = var.region
  }
}

data "terraform_remote_state" "s3" {
  backend = "s3"

  config = {
    bucket = var.state_bucket
    key    = "prod/s3/terraform.tfstate"
    region = var.region
  }
}

data "terraform_remote_state" "ecr" {
  backend = "s3"

  config = {
    bucket = var.state_bucket
    key    = "global/ecr/terraform.tfstate"
    region = var.region
  }
}

module "ec2" {
  source = "../../modules/v1/ec2"

  name   = "${var.project}-${var.environment}"
  region = var.region

  subnet_id             = data.terraform_remote_state.subnet.outputs.subnet_id
  security_group_id     = data.terraform_remote_state.sg.outputs.security_group_id
  instance_profile_name = data.terraform_remote_state.iam.outputs.instance_profile_name
  data_volume_id        = data.terraform_remote_state.ebs.outputs.volume_id
  bucket                = data.terraform_remote_state.s3.outputs.bucket_id

  # Dual-stack. The ordinary repository_url has no AAAA record and this box has
  # no IPv4 route to the internet.
  ecr_repository_url = data.terraform_remote_state.ecr.outputs.repository_url_dualstack

  parameter_prefix = var.parameter_prefix
  allowed_hosts    = var.allowed_hosts
  csrf_origins     = var.csrf_origins
  instance_type    = var.instance_type
  poll_interval    = var.poll_interval
}
