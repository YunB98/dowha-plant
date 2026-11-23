# 서비스 서버 한 대 (Docker Compose로 Nginx, FastAPI, PostgreSQL, Umami, 모니터링 실행).
# - SSH 포트 없음. 접속은 SSM Session Manager로만 한다.
# - 들어오는 트래픽은 CloudFront(origin-facing 프리픽스 리스트)에서 오는 443만 허용한다.
# - IMDSv2 강제, EBS 암호화, 매일 스냅샷.

data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

data "aws_ssm_parameter" "ami" {
  name = var.ami_ssm_parameter
}

data "aws_ec2_managed_prefix_list" "cloudfront" {
  name = "com.amazonaws.global.cloudfront.origin-facing"
}

locals {
  region     = data.aws_region.current.region
  account_id = data.aws_caller_identity.current.account_id
  # DLM이 이 태그가 붙은 볼륨의 스냅샷을 만든다.
  snapshot_tag = { Snapshot = "${var.name}-daily" }
}

# ---------------------------------------------------------------------------
# 보안 그룹
# ---------------------------------------------------------------------------

resource "aws_security_group" "this" {
  name        = "${var.name}-app"
  description = "App server: HTTPS from CloudFront only"
  vpc_id      = var.vpc_id

  tags = { Name = "${var.name}-app" }
}

# CloudFront origin-facing 프리픽스 리스트는 보안 그룹 규칙 한도를 약 55개 차지한다 (기본 한도 60).
resource "aws_vpc_security_group_ingress_rule" "https_from_cloudfront" {
  security_group_id = aws_security_group.this.id
  description       = "HTTPS from CloudFront"
  prefix_list_id    = data.aws_ec2_managed_prefix_list.cloudfront.id
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
}

# 패키지 설치, 이미지 pull, Let's Encrypt, 텔레그램·GitHub API 호출에 필요하다.
resource "aws_vpc_security_group_egress_rule" "all" {
  security_group_id = aws_security_group.this.id
  description       = "Outbound to internet"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

# ---------------------------------------------------------------------------
# IAM
# ---------------------------------------------------------------------------

data "aws_iam_policy_document" "ec2_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "this" {
  name               = "${var.name}-app"
  assume_role_policy = data.aws_iam_policy_document.ec2_trust.json
}

resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.this.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

data "aws_iam_policy_document" "app" {
  # 사진: presigned URL 발급, 임시 업로드 파일을 정식 위치로 옮기기, 삭제
  statement {
    sid       = "MediaObjects"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = ["${var.media_bucket_arn}/*"]
  }

  statement {
    sid       = "ListBuckets"
    actions   = ["s3:ListBucket"]
    resources = [var.media_bucket_arn, var.backup_bucket_arn]
  }

  # DB 백업 업로드와 복구용 다운로드. 삭제는 수명 주기 규칙이 한다.
  statement {
    sid       = "BackupObjects"
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["${var.backup_bucket_arn}/*"]
  }

  # 소개서 PDF 교체 (API: PUT /admin/settings/brochure → files/brochure.pdf)
  statement {
    sid       = "SiteFiles"
    actions   = ["s3:PutObject"]
    resources = ["${var.site_bucket_arn}/files/*"]
  }

  # 비밀값 (DB 비밀번호, 토큰, CloudFront 오리진 비밀 헤더)
  statement {
    sid       = "ReadParameters"
    actions   = ["ssm:GetParameter", "ssm:GetParameters", "ssm:GetParametersByPath"]
    resources = ["arn:aws:ssm:${local.region}:${local.account_id}:parameter${var.ssm_parameter_prefix}/*"]
  }

  # 백엔드 이미지 pull
  statement {
    sid       = "EcrAuth"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid       = "EcrPull"
    actions   = ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer", "ecr:BatchCheckLayerAvailability"]
    resources = [aws_ecr_repository.backend.arn]
  }

  # Let's Encrypt DNS-01 인증 (certbot-dns-route53). 오리진 도메인의 _acme-challenge 레코드만 바꿀 수 있다.
  statement {
    sid       = "AcmeChallengeRecord"
    actions   = ["route53:ChangeResourceRecordSets"]
    resources = ["arn:aws:route53:::hostedzone/${var.route53_zone_id}"]
    condition {
      test     = "ForAllValues:StringEquals"
      variable = "route53:ChangeResourceRecordSetsNormalizedRecordNames"
      values   = ["_acme-challenge.${var.origin_domain}"]
    }
  }

  statement {
    sid       = "AcmeChallengeLookup"
    actions   = ["route53:ListHostedZones", "route53:GetChange"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "app" {
  name   = "app"
  role   = aws_iam_role.this.id
  policy = data.aws_iam_policy_document.app.json
}

resource "aws_iam_instance_profile" "this" {
  name = "${var.name}-app"
  role = aws_iam_role.this.name
}

# ---------------------------------------------------------------------------
# EC2
# ---------------------------------------------------------------------------

resource "aws_instance" "this" {
  ami                    = data.aws_ssm_parameter.ami.value
  instance_type          = var.instance_type
  subnet_id              = var.subnet_id
  vpc_security_group_ids = [aws_security_group.this.id]
  iam_instance_profile   = aws_iam_instance_profile.this.name

  # 부팅 중 패키지 설치에 인터넷이 필요하다. EIP가 붙으면 이 임시 공인 IP는 반납된다.
  associate_public_ip_address = true

  # 실수로 콘솔·CLI에서 종료하지 못하게 한다. 교체가 필요하면 이 값을 먼저 false로 바꾼다.
  disable_api_termination = var.termination_protection

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required" # IMDSv2 강제
    http_put_response_hop_limit = 2          # 컨테이너 안에서도 IMDS에 닿도록
  }

  root_block_device {
    volume_type = "gp3"
    volume_size = var.root_volume_size
    encrypted   = true
    tags        = merge({ Name = "${var.name}-app-root" }, local.snapshot_tag)
  }

  user_data = templatefile("${path.module}/user_data.sh.tftpl", {
    compose_version = var.docker_compose_version
    swap_size_mb    = var.swap_size_mb
  })

  # 새 AMI가 나오거나 user_data를 고쳐도 운영 중인 서버를 갈아엎지 않는다.
  # 서버 교체는 복구 절차(runbook)에 따라 의도적으로 한다.
  lifecycle {
    ignore_changes = [ami, user_data]
  }

  tags = { Name = "${var.name}-app" }
}

# 고정 공인 IP. origin 도메인이 이 주소를 가리킨다.
resource "aws_eip" "this" {
  domain   = "vpc"
  instance = aws_instance.this.id

  tags = { Name = "${var.name}-app" }
}

# ---------------------------------------------------------------------------
# EBS 스냅샷 (매일 KST 03:00, RPO 24시간)
# ---------------------------------------------------------------------------

data "aws_iam_policy_document" "dlm_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["dlm.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "dlm" {
  name               = "${var.name}-dlm"
  assume_role_policy = data.aws_iam_policy_document.dlm_trust.json
}

resource "aws_iam_role_policy_attachment" "dlm" {
  role       = aws_iam_role.dlm.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSDataLifecycleManagerServiceRole"
}

resource "aws_dlm_lifecycle_policy" "daily" {
  description        = "${var.name} daily EBS snapshots"
  execution_role_arn = aws_iam_role.dlm.arn
  state              = "ENABLED"

  policy_details {
    resource_types = ["VOLUME"]
    target_tags    = local.snapshot_tag

    schedule {
      name      = "daily"
      copy_tags = true

      create_rule {
        interval      = 24
        interval_unit = "HOURS"
        times         = ["18:00"] # UTC = KST 03:00
      }

      retain_rule {
        count = var.snapshot_retention_count
      }
    }
  }
}

# ---------------------------------------------------------------------------
# ECR (백엔드 이미지)
# ---------------------------------------------------------------------------

resource "aws_ecr_repository" "backend" {
  name = "${var.name}/backend"
  # 같은 태그로 다른 이미지를 덮어쓰지 못하게 한다 (커밋 SHA를 태그로 쓴다)
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }
}

resource "aws_ecr_lifecycle_policy" "backend" {
  repository = aws_ecr_repository.backend.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep the most recent images only"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = var.ecr_keep_images
      }
      action = { type = "expire" }
    }]
  })
}
