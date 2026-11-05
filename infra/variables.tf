variable "aws_region" {
  description = "Primary AWS region"
  type        = string
  default     = "us-east-1"
}

variable "instance_name" {
  description = "Value of the EC2 instance's Name tag"
  type        = string
  default     = "budget-tracker"
}

variable "instance_type" {
  description = "The EC2 instance's type"
  type        = string
  default     = "t2.micro" # Standard free tier type
}

variable "eip_name" {
  description = "Name tag of the Elastic IP allocated in the console"
  type        = string
  default     = "budget-tracker-eip" # must match the console tag exactly
}
