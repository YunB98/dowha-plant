output "vpc_id" {
  value = module.network.vpc_id
}

output "public_subnet_ids" {
  value = module.network.public_subnet_ids
}

output "bucket_ids" {
  value = module.storage.bucket_ids
}
