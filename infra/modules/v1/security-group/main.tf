# No ingress rules, by design. The Cloudflare tunnel dials out, so nothing ever
# arrives unsolicited and there is no port to open.
resource "aws_security_group" "this" {
  name        = var.name
  description = "Egress only; the origin is reached through a Cloudflare tunnel"
  vpc_id      = var.vpc_id

  tags = merge(var.tags, { Name = var.name })
}

resource "aws_vpc_security_group_egress_rule" "ipv4" {
  security_group_id = aws_security_group.this.id
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

# Without this the instance can reach nothing: an egress rule carrying only an
# IPv4 CIDR does not permit IPv6, and IPv6 is the only route off this box.
resource "aws_vpc_security_group_egress_rule" "ipv6" {
  security_group_id = aws_security_group.this.id
  ip_protocol       = "-1"
  cidr_ipv6         = "::/0"
}
