resource "aws_vpc" "this" {
  cidr_block                       = var.cidr_block
  assign_generated_ipv6_cidr_block = true
  enable_dns_hostnames             = true
  enable_dns_support               = true

  tags = merge(var.tags, { Name = var.name })
}

# All outbound traffic leaves here. There is deliberately no aws_internet_gateway
# and no NAT gateway: an egress-only gateway cannot carry inbound connections,
# which is what keeps the instance unreachable.
resource "aws_egress_only_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id
  tags   = merge(var.tags, { Name = "${var.name}-eigw" })
}

resource "aws_route_table" "this" {
  vpc_id = aws_vpc.this.id
  tags   = merge(var.tags, { Name = "${var.name}-rt" })
}

resource "aws_route" "ipv6_default" {
  route_table_id              = aws_route_table.this.id
  destination_ipv6_cidr_block = "::/0"
  egress_only_gateway_id      = aws_egress_only_internet_gateway.this.id
}

# Free, and it carries everything S3-backed over private IPv4: ECR image layers,
# the media bucket and the AL2023 package repos. Without it those depend on
# dual-stack DNS being configured correctly on every client.
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.this.id
  service_name      = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.this.id]

  tags = merge(var.tags, { Name = "${var.name}-s3" })
}
