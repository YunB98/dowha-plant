variable "name" {
  description = "리소스 이름 접두사 (예: dowha-plant-prod)"
  type        = string
}

variable "cidr_block" {
  description = "VPC CIDR"
  type        = string
}

variable "public_subnets" {
  description = "가용 영역 → 퍼블릭 서브넷 CIDR"
  type        = map(string)
}
