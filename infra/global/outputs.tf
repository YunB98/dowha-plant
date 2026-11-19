output "zone_id" {
  description = "envs/prod, envs/staging에서 레코드를 만들 때 쓴다."
  value       = aws_route53_zone.main.zone_id
}

output "name_servers" {
  description = "가비아 도메인 관리 > 네임서버 설정에 입력할 값 4개"
  value       = aws_route53_zone.main.name_servers
}

output "github_oidc_provider_arn" {
  value = aws_iam_openid_connect_provider.github.arn
}

output "terraform_plan_role_arn" {
  description = "GitHub 저장소 변수 AWS_TERRAFORM_PLAN_ROLE_ARN에 등록"
  value       = aws_iam_role.terraform_plan.arn
}

output "terraform_apply_role_arn" {
  description = "GitHub production Environment 변수 AWS_TERRAFORM_APPLY_ROLE_ARN에 등록"
  value       = aws_iam_role.terraform_apply.arn
}
