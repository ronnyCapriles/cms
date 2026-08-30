data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-2023.*-arm64"]
  }
}

resource "aws_instance" "this" {
  # arm64: t4g is Graviton, and an x86 AMI cannot run the image CI builds.
  ami           = data.aws_ami.al2023.id
  instance_type = var.instance_type

  subnet_id                   = var.subnet_id
  vpc_security_group_ids      = [var.security_group_id]
  iam_instance_profile        = var.instance_profile_name
  associate_public_ip_address = false
  ipv6_address_count          = 1

  # t4g defaults to unlimited, which silently bills for CPU bursts.
  credit_specification {
    cpu_credits = "standard"
  }

  metadata_options {
    http_tokens   = "required"
    http_endpoint = "enabled"
  }

  root_block_device {
    volume_type = "gp3"
    volume_size = var.root_size_gb
    encrypted   = true
  }

  user_data = templatefile("${path.module}/user-data.sh", {
    region             = var.region
    bucket             = var.bucket
    ecr_repository_url = var.ecr_repository_url
    parameter_prefix   = var.parameter_prefix
    allowed_hosts      = var.allowed_hosts
    csrf_origins       = var.csrf_origins
    poll_interval      = var.poll_interval
  })

  tags = merge(var.tags, { Name = var.name })
}

resource "aws_volume_attachment" "data" {
  # Nitro renames this to /dev/nvme1n1; user-data mounts by UUID because the
  # numbering is not stable across reboots.
  device_name = "/dev/sdf"
  volume_id   = var.data_volume_id
  instance_id = aws_instance.this.id
}
