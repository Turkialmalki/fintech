terraform {
  required_version = ">= 1.7"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.80" }
    random = { source = "hashicorp/random", version = "~> 3.6" }
  }
  backend "s3" {}   # configure per environment: terraform init -backend-config=env/production.backend.hcl
}

provider "aws" {
  region = var.region   # me-central-1 (UAE) or the nearest region meeting data-residency requirements
  default_tags { tags = { project = "rip", environment = var.environment, managed_by = "terraform" } }
}
