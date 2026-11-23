variable "name" {
  description = "리소스 이름 접두사 (예: dowha-plant-prod)"
  type        = string
}

variable "domain_name" {
  description = "사이트 도메인 (www도 함께 연결된다)"
  type        = string
}

variable "route53_zone_id" {
  type = string
}

variable "site_bucket_domain_name" {
  description = "site 버킷의 리전 도메인 이름"
  type        = string
}

variable "media_bucket_domain_name" {
  description = "media 버킷의 리전 도메인 이름"
  type        = string
}

variable "api_origin_domain" {
  description = "EC2 서버 도메인 (예: origin.dowha-plant.shop). 서버에 이 이름의 인증서가 있어야 한다"
  type        = string
}

variable "origin_verify_secret" {
  description = "CloudFront가 오리진에 보내는 X-Origin-Verify 헤더 값"
  type        = string
  sensitive   = true
}

variable "price_class" {
  description = "PriceClass_200은 한국을 포함한 아시아 엣지를 쓴다"
  type        = string
  default     = "PriceClass_200"
}
