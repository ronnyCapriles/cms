
data "terraform_remote_state" "subnet" {
  backend = "s3"

  config = {
    bucket = var.state_bucket
    key    = "prod/subnet/terraform.tfstate"
    region = var.region
  }
}

module "ebs" {
  source = "../../modules/v1/ebs"

  name              = "${var.project}-${var.environment}-data"
  availability_zone = data.terraform_remote_state.subnet.outputs.availability_zone
  size_gb           = var.size_gb
}
