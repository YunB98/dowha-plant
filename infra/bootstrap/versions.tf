terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  # 상태를 저장할 버킷을 이 스택이 만들기 때문에, 최초 apply는 로컬 상태로 실행한다.
  # 버킷이 생기면 backend.tf를 추가하고 상태를 S3로 옮긴다. (infra/README.md 참고)
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project   = var.project
      ManagedBy = "terraform"
      Stack     = "bootstrap"
    }
  }
}
