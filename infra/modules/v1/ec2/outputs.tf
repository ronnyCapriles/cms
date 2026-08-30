output "instance_id" { value = aws_instance.this.id }
output "ipv6_address" { value = one(aws_instance.this.ipv6_addresses) }
output "private_ip" { value = aws_instance.this.private_ip }
