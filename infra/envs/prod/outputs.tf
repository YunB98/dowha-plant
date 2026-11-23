output "vpc_id" {
  value = module.network.vpc_id
}

output "public_subnet_ids" {
  value = module.network.public_subnet_ids
}

output "bucket_ids" {
  value = module.storage.bucket_ids
}

output "instance_id" {
  description = "SSM 접속: aws ssm start-session --target <instance_id>"
  value       = module.compute.instance_id
}

output "server_public_ip" {
  value = module.compute.public_ip
}

output "ecr_repository_url" {
  value = module.compute.ecr_repository_url
}

output "cloudfront_distribution_id" {
  value = module.cdn.distribution_id
}

output "cloudfront_domain_name" {
  value = module.cdn.distribution_domain_name
}

output "site_url" {
  value = "https://${var.domain_name}"
}
