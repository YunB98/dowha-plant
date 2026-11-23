terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  # bucket, region 등은 infra/backend.hcl에서 받는다.
  #   terraform init -backend-config=../../backend.hcl
  backend "s3" {
    key = "prod/terraform.tfstate"
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = var.project
      Environment = var.environment
      ManagedBy   = "terraform"
      Stack       = "prod"
    }
  }
}

# CloudFront용 ACM 인증서는 us-east-1에만 만들 수 있다. (조직 SCP도 us-east-1은 글로벌 서비스만 허용)
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"

  default_tags {
    tags = {
      Project     = var.project
      Environment = var.environment
      ManagedBy   = "terraform"
      Stack       = "prod"
    }
  }
}
