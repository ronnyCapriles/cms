# One per account. If the account already has it, import rather than declaring a
# second, which is an error.
resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = var.thumbprints

  tags = var.tags
}
