output "distribution_id" {
  description = "캐시 무효화(create-invalidation)에 쓴다"
  value       = aws_cloudfront_distribution.this.id
}

output "distribution_arn" {
  description = "S3 버킷 정책(OAC)과 IAM 권한에 쓴다"
  value       = aws_cloudfront_distribution.this.arn
}

output "distribution_domain_name" {
  value = aws_cloudfront_distribution.this.domain_name
}

output "certificate_arn" {
  value = aws_acm_certificate_validation.this.certificate_arn
}
