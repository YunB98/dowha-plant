# 인프라 (Terraform)

## 스택 구성

| 스택 | 상태 저장 위치 | 내용 | 실행 빈도 |
|---|---|---|---|
| `bootstrap/` | S3 `bootstrap/terraform.tfstate` (최초 apply는 로컬 후 이전) | Terraform 상태 저장용 S3 버킷 | 최초 1회 |
| `global/` | S3 `global/terraform.tfstate` | Route 53 호스팅 영역, GitHub Actions OIDC 역할 | 거의 없음 |
| `envs/prod/` | S3 `prod/terraform.tfstate` | 운영 환경 (EC2, S3, CloudFront 등) | 변경 시 |
| `envs/staging/` | S3 `staging/terraform.tfstate` | 검증 환경, 필요할 때만 생성 후 삭제 | 필요 시 |

상태 잠금은 DynamoDB 없이 S3 네이티브 잠금(`use_lockfile`)을 쓴다. Terraform 1.10 이상 필요.

## 사전 준비

- Terraform 1.10 이상, AWS CLI v2
- 로컬에서 쓸 AWS 자격 증명. **IAM Identity Center(SSO) 로그인을 권장**한다. 장기 액세스 키를 쓴다면 MFA를 켜고 주기적으로 교체한다.

```bash
aws configure sso                             # 최초 1회, 프로필 이름 dowha-admin
aws sso login --profile dowha-admin           # 세션 만료 시 (4시간)
export AWS_PROFILE=dowha-admin                # PowerShell: $env:AWS_PROFILE = "dowha-admin"
aws sts get-caller-identity                   # Dowha-plant 계정 번호가 나와야 한다
```

`AWS_PROFILE`을 지정하지 않으면 `default` 프로필로 접속해 `InvalidClientTokenId` 오류가 날 수 있다.

## CI/CD (GitHub Actions)

워크플로: [`.github/workflows/terraform.yml`](../.github/workflows/terraform.yml)

| 이벤트 | 실행 내용 | AWS 역할 |
|---|---|---|
| `infra/**`를 바꾼 PR | fmt 검사, validate, 스택별 plan (결과는 실행 요약에 표시) | plan 역할 (읽기 전용) |
| main에 머지 | plan → **production 환경 승인 대기** → 승인하면 검토한 plan 파일 그대로 apply | plan 역할 → apply 역할 |
| 수동 실행 (`workflow_dispatch`) | main에서 실행하면 위와 같음 | |

- AWS 액세스 키를 GitHub에 저장하지 않는다. OIDC로 작업마다 임시 자격 증명을 받는다.
- `backend.hcl`은 git에 없으므로, CI가 로그인한 계정 ID로 버킷 이름을 만들어 생성한다.
- 변경이 없는 스택은 승인 후에도 apply를 건너뛴다.
- plan과 apply 사이에 상태가 바뀌면 저장된 plan 적용이 거부된다. 그때는 워크플로를 다시 실행한다.

## 최초 구축 순서

### 1. bootstrap — 상태 저장 버킷

```bash
cd infra/bootstrap
terraform init
terraform apply
terraform output state_bucket_name
```

### 2. backend.hcl 작성

```bash
cd infra
cp backend.hcl.example backend.hcl   # bucket 값을 1번 출력값으로 수정
```

`backend.hcl`은 계정 ID가 들어 있어 git에 올리지 않는다 (`.gitignore`에 등록됨).

### 3. bootstrap 상태를 S3로 옮기기

`infra/bootstrap/backend.tf`를 만든다.

```hcl
terraform {
  backend "s3" {
    key = "bootstrap/terraform.tfstate"
  }
}
```

```bash
cd infra/bootstrap
terraform init -backend-config=../backend.hcl -migrate-state   # 질문에 yes
rm terraform.tfstate terraform.tfstate.backup                 # S3로 옮겨진 것을 확인한 뒤
```

### 4. global — DNS, GitHub OIDC

```bash
cd infra/global
terraform init -backend-config=../backend.hcl
terraform apply
terraform output name_servers
```

### 5. 가비아 네임서버 변경

가비아 > My가비아 > 도메인 관리 > `dowha-plant.shop` > 네임서버 설정에서
4번의 `name_servers` 4개를 입력한다. 반영까지 최대 하루 정도 걸릴 수 있다.

확인:
```bash
nslookup -type=NS dowha-plant.shop
```

### 6. GitHub 설정

| 위치 | 이름 | 값 |
|---|---|---|
| Settings > Secrets and variables > Actions > Variables | `AWS_TERRAFORM_PLAN_ROLE_ARN` | `terraform output terraform_plan_role_arn` |
| Settings > Environments > `production` 생성 | 승인자: 본인, 배포 브랜치: `main`만 | |
| `production` Environment > Variables | `AWS_TERRAFORM_APPLY_ROLE_ARN` | `terraform output terraform_apply_role_arn` |

## GitHub Actions 권한 구조

| 역할 | 사용 조건 | 권한 |
|---|---|---|
| `dowha-plant-github-terraform-plan` | 이 저장소의 PR, main 브랜치 | 읽기 전용 + 상태 잠금 파일 쓰기 |
| `dowha-plant-github-terraform-apply` | `production` Environment (사람 승인 + main만) | 관리자 (ADR 0011) |

장기 액세스 키를 GitHub에 저장하지 않는다. 작업마다 OIDC로 1시간짜리 임시 자격 증명을 받는다.

## 비용

| 리소스 | 월 비용 (대략) |
|---|---|
| S3 상태 버킷 | 거의 0 (수 KB) |
| Route 53 호스팅 영역 | 0.5달러 + 조회 요청 |
| IAM, OIDC | 무료 |

## 삭제 보호

상태 버킷과 호스팅 영역은 `prevent_destroy`가 걸려 있다.
지우면 각각 "모든 인프라의 상태 유실", "가비아 네임서버 재설정"이 필요하므로 일부러 막아둔다.
