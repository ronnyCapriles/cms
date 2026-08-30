resource "aws_subnet" "this" {
  vpc_id            = var.vpc_id
  availability_zone = var.availability_zone

  cidr_block      = cidrsubnet(var.vpc_cidr_block, 8, var.index)
  ipv6_cidr_block = cidrsubnet(var.vpc_ipv6_cidr_block, 8, var.index)

  assign_ipv6_address_on_creation = true
  map_public_ip_on_launch         = false

  tags = merge(var.tags, { Name = var.name })
}

resource "aws_route_table_association" "this" {
  subnet_id      = aws_subnet.this.id
  route_table_id = var.route_table_id
}
