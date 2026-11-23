variable "name" {
  description = "버킷 이름 접두사 (예: dowha-plant-prod). 실제 이름은 <name>-<용도>-<계정 ID>"
  type        = string
}

variable "backup_retention_days" {
  description = "DB 백업 보관 기간(일)"
  type        = number
  default     = 30
}

variable "upload_allowed_origins" {
  description = "사진 직접 업로드를 허용할 사이트 주소 (CORS)"
  type        = list(string)
}

variable "cloudfront_distribution_arn" {
  description = "site, media 버킷 읽기를 허용할 CloudFront 배포 ARN. 배포를 만들기 전에는 null"
  type        = string
  default     = null
}
