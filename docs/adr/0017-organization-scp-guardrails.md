# 0017. 조직 SCP 가드레일

- 상태: 채택
- 날짜: 2026-11-23

## 배경
AWS 초기 설정이 서비스 제어 정책(SCP)을 조직 루트에 연결해 두었다. SCP는 멤버 계정(Dowha-plant)의 모든 권한 위에 적용되며, 관리 계정에는 적용되지 않는다.

## 결정
아래 정책을 유지하되, 리전 제한은 서울로 고쳤다.

| 정책 | 내용 | 조치 |
|---|---|---|
| 리전 제한 (`AdvancedModeRegionRestriction...`) | 허용 리전 외 모든 작업 거부. us-east-1은 글로벌 서비스(IAM, CloudFront, ACM, Route 53 등)만 허용 | 허용 리전을 `ap-southeast-2`(시드니) → **`ap-northeast-2`(서울)** 로 변경 |
| 계정 보호 (`ManagedAccountSecurityControlPolicy`) | 멤버 계정의 조직 탈퇴, 계정 해지, 자체 Identity Center 생성 금지. `/managed/` 경로 IAM 역할 보호 | 유지 |
| 예산 한도 차단 (`BudgetsSpendLimitDeny...` 4개) | 예상 비용이 예산(월 20달러)에 가까워지면 새 유료 리소스 생성, Lambda, Bedrock, SageMaker 사용 차단 | 유지. 한도 상향(30달러) 검토 |

## 영향
- 이 프로젝트의 리소스는 **서울**과 **us-east-1 글로벌 서비스**(CloudFront용 ACM 인증서 등)에만 만들 수 있다.
- us-east-1에서 CloudWatch 알람 생성과 SNS가 막혀 있어 Route 53 헬스체크 알림을 쓸 수 없다 → ADR 0019.
- 예산 예상치가 한도에 가까워지면 `terraform apply`가 권한 오류로 실패할 수 있다. 그때는 예산 화면부터 확인한다.
- Terraform이 만드는 IAM 역할은 기본 경로(`/`)를 써서 `/managed/` 보호 규칙에 걸리지 않는다.

## 이후 할 일
- SCP는 지금 관리 계정 콘솔에서 관리한다. 관리 계정용 Terraform 스택을 따로 두어 코드로 관리하는 것을 검토한다.
