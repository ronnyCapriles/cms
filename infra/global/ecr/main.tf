module "ecr" {
  source = "../../modules/v1/ecr"

  name        = var.project
  region      = var.region
  keep_images = var.keep_images
}
