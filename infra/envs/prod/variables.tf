variable "project" {
  type    = string
  default = "dowha-plant"
}

variable "environment" {
  type    = string
  default = "prod"
}

variable "region" {
  type    = string
  default = "ap-northeast-2"
}

variable "domain_name" {
  description = "사이트 도메인 (global 스택의 Route 53 호스팅 영역)"
  type        = string
  default     = "dowha-plant.shop"
}

variable "vpc_cidr" {
  type    = string
  default = "10.20.0.0/16"
}

# 서버는 한 대지만, 나중에 로드밸런서나 DB를 붙일 때 필요한 두 번째 가용 영역을 미리 둔다 (비용 없음).
variable "public_subnets" {
  type = map(string)
  default = {
    "ap-northeast-2a" = "10.20.0.0/24"
    "ap-northeast-2c" = "10.20.1.0/24"
  }
}

variable "backup_retention_days" {
  type    = number
  default = 30
}

variable "instance_type" {
  type    = string
  default = "t4g.small"
}

variable "server_az" {
  description = "서버를 둘 가용 영역 (public_subnets의 키 중 하나)"
  type        = string
  default     = "ap-northeast-2a"
}
