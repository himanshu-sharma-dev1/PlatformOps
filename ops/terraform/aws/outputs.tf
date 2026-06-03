output "vpc_id" {
  value       = aws_vpc.platformops_vpc.id
  description = "The ID of the provisioned VPC"
}

output "instance_id" {
  value       = aws_instance.platformops_control_plane.id
  description = "The ID of the PlatformOps control plane EC2 instance"
}

output "public_ip" {
  value       = aws_instance.platformops_control_plane.public_ip
  description = "The public IP address of the provisioned EC2 control plane node"
}

output "private_ip" {
  value       = aws_instance.platformops_control_plane.private_ip
  description = "The private IP address of the provisioned EC2 control plane node"
}
