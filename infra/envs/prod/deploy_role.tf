# GitHub Actions 애플리케이션 배포 역할 (.github/workflows/deploy.yml, ADR 0023)
# - production 환경(승인 필요)에서 실행된 작업만 이 역할을 쓸 수 있다
# - 할 수 있는 일: 백엔드 이미지 push, 배포 묶음 업로드, 이 서버 한 대에 SSM 명령 실행
# - Terraform apply 역할(AdministratorAccess)과 분리해서, 앱 배포가 인프라를 바꾸지 못하게 한다

data "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"
}

locals {
  release_prefix  = "releases"
  github_oidc_sub = "${var.github_subject_prefix}:environment:${var.github_deploy_environment}"
}

data "aws_iam_policy_document" "github_deploy_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [data.aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = [local.github_oidc_sub]
    }
  }
}

resource "aws_iam_role" "github_deploy" {
  name                 = "${var.project}-github-deploy-${var.environment}"
  description          = "GitHub Actions app deploy (ECR push, release upload, SSM command)"
  assume_role_policy   = data.aws_iam_policy_document.github_deploy_trust.json
  max_session_duration = 3600
}

data "aws_iam_policy_document" "github_deploy" {
  statement {
    sid       = "EcrAuth"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  # 태그가 IMMUTABLE이라 이미 있는 태그는 덮어쓸 수 없다
  statement {
    sid = "EcrPush"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:InitiateLayerUpload",
      "ecr:UploadLayerPart",
      "ecr:CompleteLayerUpload",
      "ecr:PutImage",
      "ecr:BatchGetImage",
      "ecr:DescribeImages",
    ]
    resources = [module.compute.ecr_repository_arn]
  }

  # 배포 묶음(deploy/ 폴더)을 서버가 읽을 수 있는 backup 버킷의 releases/ 아래에 둔다.
  # backup 버킷 수명 주기(30일)로 오래된 묶음은 자동 삭제된다.
  statement {
    sid       = "UploadRelease"
    actions   = ["s3:PutObject"]
    resources = ["${module.storage.bucket_arns["backup"]}/${local.release_prefix}/*"]
  }

  # 이 서버 한 대에, AWS-RunShellScript 문서로만 명령을 보낼 수 있다
  statement {
    sid     = "SendDeployCommand"
    actions = ["ssm:SendCommand"]
    resources = [
      module.compute.instance_arn,
      "arn:aws:ssm:${var.region}::document/AWS-RunShellScript",
    ]
  }

  # 태그로 서버를 찾는다 (서버를 다시 만들면 인스턴스 ID가 바뀌므로)
  statement {
    sid       = "FindInstance"
    actions   = ["ec2:DescribeInstances"]
    resources = ["*"]
  }

  statement {
    sid       = "ReadCommandResult"
    actions   = ["ssm:GetCommandInvocation", "ssm:ListCommandInvocations"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "github_deploy" {
  name   = "app-deploy"
  role   = aws_iam_role.github_deploy.id
  policy = data.aws_iam_policy_document.github_deploy.json
}
