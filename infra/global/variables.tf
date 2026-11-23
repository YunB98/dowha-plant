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

# GitHub OIDC 토큰의 sub 클레임은 이름 뒤에 바뀌지 않는 숫자 ID를 붙인 형식이다.
#   repo:<owner>@<owner_id>/<repo>@<repo_id>:<context>
# 저장소를 지우고 같은 이름으로 다시 만들어도 ID가 달라지므로 역할을 가로챌 수 없다.
# ID 확인: https://api.github.com/repos/<owner>/<repo> 의 owner.id, id
variable "github_owner" {
  description = "GitHub 계정 이름"
  type        = string
  default     = "YunB98"
}

variable "github_owner_id" {
  description = "GitHub 계정 숫자 ID"
  type        = number
  default     = 251148256
}

variable "github_repo" {
  description = "GitHub Actions가 AWS에 접근할 수 있는 저장소 이름"
  type        = string
  default     = "dowha-plant"
}

variable "github_repo_id" {
  description = "GitHub 저장소 숫자 ID"
  type        = number
  default     = 1464295966
}

variable "github_apply_environment" {
  description = "terraform apply를 허용할 GitHub Environment 이름. 승인 규칙은 GitHub에서 설정한다."
  type        = string
  default     = "production"
}
