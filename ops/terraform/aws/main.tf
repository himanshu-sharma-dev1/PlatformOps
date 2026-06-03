terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# Create a VPC for the control plane
resource "aws_vpc" "platformops_vpc" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name        = "platformops-vpc-${var.environment}"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# Subnet for the control plane instance
resource "aws_subnet" "platformops_subnet" {
  vpc_id                  = aws_vpc.platformops_vpc.id
  cidr_block              = "10.0.1.0/24"
  map_public_ip_on_launch = true

  tags = {
    Name        = "platformops-subnet-${var.environment}"
    Environment = var.environment
  }
}

# Internet Gateway for public routing
resource "aws_internet_gateway" "platformops_igw" {
  vpc_id = aws_vpc.platformops_vpc.id

  tags = {
    Name = "platformops-igw-${var.environment}"
  }
}

# Route table to redirect internet traffic through the gateway
resource "aws_route_table" "platformops_rt" {
  vpc_id = aws_vpc.platformops_vpc.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.platformops_igw.id
  }

  tags = {
    Name = "platformops-route-table-${var.environment}"
  }
}

# Route table association
resource "aws_route_table_association" "platformops_rta" {
  subnet_id      = aws_subnet.platformops_subnet.id
  route_table_id = aws_route_table.platformops_rt.id
}

# Security group to expose SSH, HTTP, and the FastAPI Control Plane API
resource "aws_security_group" "platformops_sg" {
  name        = "platformops-sg-${var.environment}"
  description = "Security group for PlatformOps control plane node"
  vpc_id      = aws_vpc.platformops_vpc.id

  ingress {
    description = "SSH access"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "FastAPI backend control plane API"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTP web portal"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "All outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "platformops-sg-${var.environment}"
    Environment = var.environment
  }
}

# EC2 Instance simulating a PlatformOps orchestrator node (Ubuntu)
resource "aws_instance" "platformops_control_plane" {
  ami                    = var.ami_id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.platformops_subnet.id
  vpc_security_group_ids = [aws_security_group.platformops_sg.id]

  root_block_device {
    volume_size           = 20
    volume_type           = "gp3"
    delete_on_termination = true
  }

  tags = {
    Name        = "platformops-control-plane-${var.environment}"
    Environment = var.environment
    Role        = "control-plane"
  }
}
