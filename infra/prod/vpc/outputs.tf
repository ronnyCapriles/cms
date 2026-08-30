output "vpc_id" { value = module.vpc.vpc_id }
output "ipv6_cidr_block" { value = module.vpc.ipv6_cidr_block }
output "route_table_id" { value = module.vpc.route_table_id }
output "cidr_block" { value = var.cidr_block }
