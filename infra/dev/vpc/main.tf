module "vpc" {
  source = "../../modules/v1/vpc"

  name       = "${var.project}-${var.environment}"
  region     = var.region
  cidr_block = var.cidr_block
}
