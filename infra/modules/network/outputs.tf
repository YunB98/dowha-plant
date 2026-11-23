output "vpc_id" {
  value = aws_vpc.this.id
}

output "public_subnet_ids" {
  description = "가용 영역 → 서브넷 ID"
  value       = { for az, subnet in aws_subnet.public : az => subnet.id }
}

output "s3_endpoint_prefix_list_id" {
  description = "S3 게이트웨이 엔드포인트의 프리픽스 리스트. 보안 그룹 아웃바운드 규칙에 쓴다."
  value       = aws_vpc_endpoint.s3.prefix_list_id
}
