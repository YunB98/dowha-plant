# 0016. AWS 멀티 계정 구조와 IAM Identity Center(SSO)

- 상태: 채택
- 날짜: 2026-11-23

## 배경
AWS 초기 설정 과정에서 조직(Organizations)과 여러 멤버 계정이 자동으로 만들어졌고,
어느 계정이 무엇인지 몰라 Identity Center 설정이 여러 번 막혔다.
또 PC에 남아 있던 예전 프로젝트의 장기 액세스 키(`default` 프로필)가 무효여서 CLI·Terraform 인증이 혼동됐다.

## 결정
| 계정 | 용도 | 비고 |
|---|---|---|
| 관리 계정 | 조직, 결제, 예산, Identity Center만 | **서비스 리소스를 만들지 않는다.** 루트 사용자는 MFA를 켜고 꼭 필요할 때만 쓴다 |
| Dowha-plant | prod 서비스 | Terraform이 관리하는 모든 리소스가 여기에 있다 |

- **Identity Center는 관리 계정에서 서울 리전(`ap-northeast-2`)으로 운영한다.**
  - 사용자 `yunb` (MFA 필수), 권한 세트 `AdministratorAccess` (세션 4시간)
  - 로컬 CLI: `aws configure sso` → 프로필 `dowha-admin`, 만료 시 `aws sso login`
- **장기 액세스 키를 쓰지 않는다.** 로컬은 SSO 임시 자격 증명, CI는 GitHub OIDC(ADR 0011).
- staging은 우선 같은 계정에 만들고, 필요해지면 별도 멤버 계정으로 분리한다.

## 정리한 것
- 초기 설정이 만든 Identity 위임 관리 계정과 Proof of Concept 계정을 해지했다 (크레딧은 관리 계정에 있음을 먼저 확인).
- us-east-1에 있던 Identity Center를 위임 해제 후 삭제하고 서울에서 다시 만들었다.

## 이유
- 관리 계정이 탈취돼도 서비스 리소스와 분리되고, 서비스 계정에서 실수해도 조직·결제에 영향이 없다.
- 사용자 하나로 여러 계정에 들어갈 수 있고, 자격 증명이 자동으로 만료된다.

## 주의
- 셸마다 `AWS_PROFILE=dowha-admin`을 지정해야 한다. 지정하지 않으면 `default` 프로필의 무효 키로 접속해 `InvalidClientTokenId` 오류가 난다.
- PC의 예전 프로젝트 액세스 키는 해당 계정에서 비활성화한 뒤 `~/.aws/credentials`에서 지운다.
