output "instance_id" {
  value = aws_instance.this.id
}

output "public_ip" {
  description = "고정 공인 IP (EIP)"
  value       = aws_eip.this.public_ip
}

output "security_group_id" {
  value = aws_security_group.this.id
}

output "role_name" {
  description = "서버 IAM 역할 이름. 다른 스택에서 권한을 더 붙일 때 쓴다"
  value       = aws_iam_role.this.name
}

output "ecr_repository_url" {
  value = aws_ecr_repository.backend.repository_url
}

output "ecr_repository_arn" {
  value = aws_ecr_repository.backend.arn
}

output "instance_arn" {
  value = aws_instance.this.arn
}
