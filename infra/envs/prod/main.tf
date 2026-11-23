locals {
  name                 = "${var.project}-${var.environment}"
  origin_domain        = "origin.${var.domain_name}"
  ssm_parameter_prefix = "/${var.project}/${var.environment}"
}

# global 스택이 만든 호스팅 영역
data "aws_route53_zone" "main" {
  name = var.domain_name
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

  # site, media 버킷은 이 배포에서만 읽을 수 있다 (OAC).
  cloudfront_distribution_arn = module.cdn.distribution_arn
}

# ---------------------------------------------------------------------------
# 서버
# ---------------------------------------------------------------------------

module "compute" {
  source = "../../modules/compute"

  name          = local.name
  vpc_id        = module.network.vpc_id
  subnet_id     = module.network.public_subnet_ids[var.server_az]
  instance_type = var.instance_type
  swap_size_mb  = var.swap_size_mb

  site_bucket_arn   = module.storage.bucket_arns["site"]
  media_bucket_arn  = module.storage.bucket_arns["media"]
  backup_bucket_arn = module.storage.bucket_arns["backup"]

  ssm_parameter_prefix = local.ssm_parameter_prefix
  route53_zone_id      = data.aws_route53_zone.main.zone_id
  origin_domain        = local.origin_domain
}

# CloudFront → 서버 연결용 이름. 서버의 Let's Encrypt 인증서도 이 이름으로 받는다.
resource "aws_route53_record" "origin" {
  zone_id = data.aws_route53_zone.main.zone_id
  name    = local.origin_domain
  type    = "A"
  ttl     = 300
  records = [module.compute.public_ip]
}

# CloudFront가 오리진에 보내는 비밀 헤더 값. Nginx가 SSM에서 읽어 확인한다.
# 값은 Terraform 상태에도 저장된다 (상태 버킷은 비공개·암호화).
resource "random_password" "origin_verify" {
  length  = 48
  special = false
}

resource "aws_ssm_parameter" "origin_verify" {
  name        = "${local.ssm_parameter_prefix}/origin-verify-secret"
  description = "X-Origin-Verify header value sent by CloudFront"
  type        = "SecureString"
  value       = random_password.origin_verify.result
}

# ---------------------------------------------------------------------------
# CDN
# ---------------------------------------------------------------------------

module "cdn" {
  source = "../../modules/cdn"

  providers = {
    aws           = aws
    aws.us_east_1 = aws.us_east_1
  }

  name                     = local.name
  domain_name              = var.domain_name
  route53_zone_id          = data.aws_route53_zone.main.zone_id
  site_bucket_domain_name  = module.storage.bucket_regional_domain_names["site"]
  media_bucket_domain_name = module.storage.bucket_regional_domain_names["media"]
  api_origin_domain        = aws_route53_record.origin.fqdn
  origin_verify_secret     = random_password.origin_verify.result
}

# 서버가 소개서 PDF를 바꾼 뒤 캐시를 지울 수 있게 한다.
# (compute 모듈 안에 두면 compute ↔ cdn 사이에 순환 참조가 생겨서 여기에 둔다)
data "aws_iam_policy_document" "app_invalidation" {
  statement {
    actions   = ["cloudfront:CreateInvalidation"]
    resources = [module.cdn.distribution_arn]
  }
}

resource "aws_iam_role_policy" "app_invalidation" {
  name   = "cloudfront-invalidation"
  role   = module.compute.role_name
  policy = data.aws_iam_policy_document.app_invalidation.json
}
