# GitHub Actions가 장기 액세스 키 없이 AWS에 접근하도록 OIDC를 설정한다.
#
# 역할 2개:
#   terraform-plan  : PR에서 plan만 실행. 읽기 전용 + 상태 잠금 파일 쓰기
#   terraform-apply : main 브랜치의 production Environment에서만 apply 실행
#
# 배포용 역할(S3 업로드, ECR push, SSM 명령)은 대상 리소스를 만드는 envs/prod에서 정의한다.

data "aws_caller_identity" "current" {}

locals {
  github_oidc_host  = "token.actions.githubusercontent.com"
  state_bucket_name = "${var.project}-tfstate-${data.aws_caller_identity.current.account_id}"
  state_bucket_arn  = "arn:aws:s3:::${local.state_bucket_name}"
}

resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://${local.github_oidc_host}"
  client_id_list = ["sts.amazonaws.com"]
}

# ---------------------------------------------------------------------------
# terraform-plan
# ---------------------------------------------------------------------------

data "aws_iam_policy_document" "plan_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.github_oidc_host}:aud"
      values   = ["sts.amazonaws.com"]
    }

    # 이 저장소의 PR과 main 브랜치에서만 허용한다.
    condition {
      test     = "StringLike"
      variable = "${local.github_oidc_host}:sub"
      values = [
        "repo:${var.github_repository}:pull_request",
        "repo:${var.github_repository}:ref:refs/heads/main",
      ]
    }
  }
}

resource "aws_iam_role" "terraform_plan" {
  name                 = "${var.project}-github-terraform-plan"
  description          = "GitHub Actions: terraform plan (read-only)"
  assume_role_policy   = data.aws_iam_policy_document.plan_trust.json
  max_session_duration = 3600
}

resource "aws_iam_role_policy_attachment" "plan_readonly" {
  role       = aws_iam_role.terraform_plan.name
  policy_arn = "arn:aws:iam::aws:policy/ReadOnlyAccess"
}

# plan도 상태 잠금 파일(.tflock)을 만들고 지워야 한다. 상태 파일 자체는 읽기만 한다.
data "aws_iam_policy_document" "plan_state_lock" {
  statement {
    sid       = "ListStateBucket"
    actions   = ["s3:ListBucket"]
    resources = [local.state_bucket_arn]
  }

  statement {
    sid       = "ReadState"
    actions   = ["s3:GetObject"]
    resources = ["${local.state_bucket_arn}/*"]
  }

  statement {
    sid       = "WriteLockFile"
    actions   = ["s3:PutObject", "s3:DeleteObject"]
    resources = ["${local.state_bucket_arn}/*.tflock"]
  }
}

resource "aws_iam_role_policy" "plan_state_lock" {
  name   = "terraform-state-lock"
  role   = aws_iam_role.terraform_plan.id
  policy = data.aws_iam_policy_document.plan_state_lock.json
}

# ---------------------------------------------------------------------------
# terraform-apply
# ---------------------------------------------------------------------------

data "aws_iam_policy_document" "apply_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.github_oidc_host}:aud"
      values   = ["sts.amazonaws.com"]
    }

    # GitHub Environment로 제한한다. Environment에 승인자와 main 브랜치 제한을 걸어
    # 사람이 승인한 main 브랜치 작업만 apply할 수 있게 한다.
    condition {
      test     = "StringEquals"
      variable = "${local.github_oidc_host}:sub"
      values   = ["repo:${var.github_repository}:environment:${var.github_apply_environment}"]
    }
  }
}

resource "aws_iam_role" "terraform_apply" {
  name                 = "${var.project}-github-terraform-apply"
  description          = "GitHub Actions: terraform apply (production environment only)"
  assume_role_policy   = data.aws_iam_policy_document.apply_trust.json
  max_session_duration = 3600
}

# 1인 프로젝트라 관리 부담을 줄이려고 AdministratorAccess를 쓴다.
# 대신 위 신뢰 정책으로 "승인된 production Environment"에서만 이 역할을 쓸 수 있게 막는다.
# 리소스 구성이 안정되면 필요한 서비스만 허용하는 정책으로 좁힌다. (ADR 0011)
resource "aws_iam_role_policy_attachment" "apply_admin" {
  role       = aws_iam_role.terraform_apply.name
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
}
