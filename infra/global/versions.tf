terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  # bucket, region 등은 infra/backend.hcl에서 받는다.
  #   terraform init -backend-config=../backend.hcl
  backend "s3" {
    key = "global/terraform.tfstate"
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project   = var.project
      ManagedBy = "terraform"
      Stack     = "global"
    }
  }
}
