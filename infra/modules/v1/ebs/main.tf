# The SQLite database. The only state on this system that cannot be rebuilt.
resource "aws_ebs_volume" "this" {
  availability_zone = var.availability_zone
  size              = var.size_gb
  type              = "gp3"
  encrypted         = true

  tags = merge(var.tags, { Name = var.name, Snapshot = var.name })

  # Turns "terraform destroy ate the CMS" into an error message.
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_iam_role" "dlm" {
  name = "${var.name}-dlm"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "dlm.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "dlm" {
  role       = aws_iam_role.dlm.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSDataLifecycleManagerServiceRole"
}

resource "aws_dlm_lifecycle_policy" "this" {
  description        = "${var.name} daily snapshots"
  execution_role_arn = aws_iam_role.dlm.arn
  state              = "ENABLED"

  policy_details {
    resource_types = ["VOLUME"]
    target_tags    = { Snapshot = var.name }

    schedule {
      name = "daily"

      create_rule {
        interval      = 24
        interval_unit = "HOURS"
        times         = [var.snapshot_time]
      }

      retain_rule {
        count = var.snapshot_retention
      }

      copy_tags = true
    }
  }

  tags = var.tags
}
