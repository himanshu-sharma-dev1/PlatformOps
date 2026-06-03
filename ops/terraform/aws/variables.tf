variable "aws_region" {
  type        = string
  description = "The target AWS region for deployment"
  default     = "us-west-2"
}

variable "environment" {
  type        = string
  description = "The target deployment environment (e.g. dev, staging, prod)"
  default     = "dev"
}

variable "instance_type" {
  type        = string
  description = "The instance type to provision for the control plane"
  default     = "t3.micro"
}

variable "ami_id" {
  type        = string
  description = "The AMI ID to use for the EC2 node (default is standard Ubuntu 22.04 LTS)"
  default     = "ami-03f1594ff9da600f5" # Ubuntu 22.04 LTS in us-west-2
}
