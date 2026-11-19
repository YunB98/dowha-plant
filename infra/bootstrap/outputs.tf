output "state_bucket_name" {
  description = "backend.hcl의 bucket 값으로 쓴다."
  value       = aws_s3_bucket.tfstate.bucket
}

output "state_bucket_arn" {
  value = aws_s3_bucket.tfstate.arn
}
