variable "name" {
  description = "리소스 이름 접두사 (예: dowha-plant-prod)"
  type        = string
}

variable "vpc_id" {
  type = string
}

variable "subnet_id" {
  description = "서버를 둘 퍼블릭 서브넷"
  type        = string
}

variable "instance_type" {
  type    = string
  default = "t4g.micro"
}

variable "cpu_credits" {
  description = "버스터블 인스턴스 CPU 크레딧 모드. standard는 추가 요금이 없다"
  type        = string
  default     = "standard"

  validation {
    condition     = contains(["standard", "unlimited"], var.cpu_credits)
    error_message = "cpu_credits는 standard 또는 unlimited여야 합니다."
  }
}

variable "ami_ssm_parameter" {
  description = "AMI ID를 담은 공개 SSM 파라미터 (Amazon Linux 2023, ARM)"
  type        = string
  default     = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-arm64"
}

variable "root_volume_size" {
  description = "루트 EBS 크기(GB)"
  type        = number
  default     = 20
}

variable "swap_size_mb" {
  type    = number
  default = 2048
}

variable "docker_compose_version" {
  description = "Docker Compose 플러그인 버전 (v 없이). 출시 후 2주 이상 지난 버전을 쓴다"
  type        = string
  default     = "5.6.1"
}

variable "termination_protection" {
  type    = bool
  default = true
}

variable "snapshot_retention_count" {
  description = "보관할 일일 EBS 스냅샷 개수"
  type        = number
  default     = 7
}

variable "ecr_keep_images" {
  description = "ECR에 남길 최근 이미지 개수"
  type        = number
  default     = 10
}

variable "site_bucket_arn" {
  type = string
}

variable "media_bucket_arn" {
  type = string
}

variable "backup_bucket_arn" {
  type = string
}

variable "ssm_parameter_prefix" {
  description = "서버가 읽을 수 있는 SSM 파라미터 경로 (예: /dowha-plant/prod)"
  type        = string
}

variable "route53_zone_id" {
  description = "Let's Encrypt DNS-01 인증에 쓸 호스팅 영역"
  type        = string
}

variable "origin_domain" {
  description = "CloudFront가 연결할 서버 도메인 (예: origin.dowha-plant.shop)"
  type        = string
}
