output "bucket_ids" {
  description = "용도 → 버킷 이름 (site, media, backup)"
  value       = { for k, b in aws_s3_bucket.this : k => b.id }
}

output "bucket_arns" {
  description = "용도 → 버킷 ARN"
  value       = { for k, b in aws_s3_bucket.this : k => b.arn }
}

output "bucket_regional_domain_names" {
  description = "CloudFront 오리진 주소로 쓴다"
  value       = { for k, b in aws_s3_bucket.this : k => b.bucket_regional_domain_name }
}
