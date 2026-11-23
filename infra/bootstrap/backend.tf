# 최초 apply는 로컬 상태로 실행했고, 이후 상태를 이 버킷으로 옮겼다. (infra/README.md 3단계)
#   terraform init -backend-config=../backend.hcl
terraform {
  backend "s3" {
    key = "bootstrap/terraform.tfstate"
  }
}
