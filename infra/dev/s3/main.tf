module "s3" {
  source = "../../modules/v1/s3"

  name = var.bucket_name
}
