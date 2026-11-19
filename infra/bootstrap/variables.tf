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

variable "noncurrent_version_retention_days" {
  description = "이전 버전 상태 파일을 보관할 기간(일)"
  type        = number
  default     = 90
}
