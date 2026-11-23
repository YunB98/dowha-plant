# prod S3 버킷 3개. 모두 비공개이며 외부 공개는 CloudFront(OAC)로만 한다.
#   site   : Next.js 정적 빌드 결과, 소개서 PDF        (CI가 배포)
#   media  : 상품·사례·가이드 사진                      (관리 화면에서 presigned URL로 업로드)
#   backup : PostgreSQL 덤프                            (EC2 백업 스크립트)
#
# 버킷 정책은 이 모듈만 관리한다. CloudFront 배포 ARN을 받으면 OAC 읽기 허용을 추가한다.

data "aws_caller_identity" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id

  buckets = {
    site = {
      versioning         = false
      served_by_cdn      = true
      noncurrent_days    = null
      expire_prefix      = null
      expire_prefix_days = null
      expire_all_days    = null
    }
    media = {
      versioning         = true
      served_by_cdn      = true
      noncurrent_days    = 30
      expire_prefix      = "uploads/tmp/"
      expire_prefix_days = 1
      expire_all_days    = null
    }
    backup = {
      versioning         = true
      served_by_cdn      = false
      noncurrent_days    = 7
      expire_prefix      = null
      expire_prefix_days = null
      expire_all_days    = var.backup_retention_days
    }
  }
}

resource "aws_s3_bucket" "this" {
  for_each = local.buckets

  bucket = "${var.name}-${each.key}-${local.account_id}"
}

resource "aws_s3_bucket_ownership_controls" "this" {
  for_each = aws_s3_bucket.this

  bucket = each.value.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "this" {
  for_each = aws_s3_bucket.this

  bucket                  = each.value.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  for_each = aws_s3_bucket.this

  bucket = each.value.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# 사진·백업은 실수나 침해로 지워져도 되살릴 수 있게 버전 관리를 켠다.
resource "aws_s3_bucket_versioning" "this" {
  for_each = { for k, v in local.buckets : k => v if v.versioning }

  bucket = aws_s3_bucket.this[each.key].id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "this" {
  for_each = aws_s3_bucket.this

  bucket = each.value.id

  rule {
    id     = "abort-incomplete-multipart"
    status = "Enabled"
    filter {}
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }

  dynamic "rule" {
    for_each = local.buckets[each.key].noncurrent_days == null ? [] : [1]
    content {
      id     = "expire-noncurrent-versions"
      status = "Enabled"
      filter {}
      noncurrent_version_expiration {
        noncurrent_days = local.buckets[each.key].noncurrent_days
      }
    }
  }

  # 업로드만 하고 연결하지 않은 임시 파일 정리 (API 명세: uploads/tmp/는 1일 후 삭제)
  dynamic "rule" {
    for_each = local.buckets[each.key].expire_prefix == null ? [] : [1]
    content {
      id     = "expire-tmp-uploads"
      status = "Enabled"
      filter {
        prefix = local.buckets[each.key].expire_prefix
      }
      expiration {
        days = local.buckets[each.key].expire_prefix_days
      }
    }
  }

  dynamic "rule" {
    for_each = local.buckets[each.key].expire_all_days == null ? [] : [1]
    content {
      id     = "expire-old-backups"
      status = "Enabled"
      filter {}
      expiration {
        days = local.buckets[each.key].expire_all_days
      }
    }
  }

  depends_on = [aws_s3_bucket_versioning.this]
}

# 관리 화면에서 브라우저가 사진을 S3로 직접 올리므로(presigned POST) 사이트 도메인만 허용한다.
resource "aws_s3_bucket_cors_configuration" "media" {
  bucket = aws_s3_bucket.this["media"].id

  cors_rule {
    allowed_methods = ["POST", "PUT"]
    allowed_origins = var.upload_allowed_origins
    allowed_headers = ["*"]
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}

data "aws_iam_policy_document" "this" {
  for_each = aws_s3_bucket.this

  statement {
    sid     = "DenyInsecureTransport"
    effect  = "Deny"
    actions = ["s3:*"]
    resources = [
      each.value.arn,
      "${each.value.arn}/*",
    ]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }

  # CloudFront OAC: 지정한 배포에서 오는 읽기 요청만 허용한다.
  dynamic "statement" {
    for_each = (local.buckets[each.key].served_by_cdn && var.cloudfront_distribution_arn != null) ? [1] : []
    content {
      sid       = "AllowCloudFrontRead"
      effect    = "Allow"
      actions   = ["s3:GetObject"]
      resources = ["${each.value.arn}/*"]
      principals {
        type        = "Service"
        identifiers = ["cloudfront.amazonaws.com"]
      }
      condition {
        test     = "StringEquals"
        variable = "AWS:SourceArn"
        values   = [var.cloudfront_distribution_arn]
      }
    }
  }
}

resource "aws_s3_bucket_policy" "this" {
  for_each = aws_s3_bucket.this

  bucket = each.value.id
  policy = data.aws_iam_policy_document.this[each.key].json

  depends_on = [aws_s3_bucket_public_access_block.this]
}
