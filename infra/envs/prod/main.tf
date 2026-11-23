locals {
  name = "${var.project}-${var.environment}"
}

module "network" {
  source = "../../modules/network"

  name           = local.name
  cidr_block     = var.vpc_cidr
  public_subnets = var.public_subnets
}

module "storage" {
  source = "../../modules/storage"

  name                  = local.name
  backup_retention_days = var.backup_retention_days
  upload_allowed_origins = [
    "https://${var.domain_name}",
    "https://www.${var.domain_name}",
  ]

  # CloudFront 배포를 만든 뒤 연결한다 (다음 단계: modules/cdn).
  cloudfront_distribution_arn = null
}
