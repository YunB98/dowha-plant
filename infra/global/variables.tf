variable "project" {
  description = "프로젝트 이름. 리소스 이름과 태그에 쓴다."
  type        = string
  default     = "dowha-plant"
}

variable "region" {
  description = "AWS 리전"
  type        = string
  default     = "ap-northeast-2"
}

variable "domain_name" {
  description = "가비아에서 등록한 도메인"
  type        = string
  default     = "dowha-plant.shop"
}

variable "github_repository" {
  description = "GitHub Actions가 AWS에 접근할 수 있는 저장소 (owner/name)"
  type        = string
  default     = "YunB98/dowha-plant"
}

variable "github_apply_environment" {
  description = "terraform apply를 허용할 GitHub Environment 이름. 승인 규칙은 GitHub에서 설정한다."
  type        = string
  default     = "production"
}
