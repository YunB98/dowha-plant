# 0011. Terraform 상태 관리와 GitHub Actions 인증

- 상태: 채택
- 날짜: 2026-11-20

## 결정
1. **상태 저장**: S3 버킷 하나에 스택별 키로 저장한다 (`bootstrap/`, `global/`, `prod/`, `staging/`).
   - 잠금은 DynamoDB 대신 S3 네이티브 잠금(`use_lockfile`, Terraform 1.10+)을 쓴다.
   - 버전 관리, 암호화, 공개 차단, HTTPS 강제, 이전 버전 90일 보관.
2. **스택 분리**: 상태 버킷(`bootstrap`)과 공용 리소스(`global`: DNS, OIDC)를 환경(`envs/*`)과 분리한다.
3. **CI 인증**: GitHub Actions는 액세스 키 대신 OIDC로 임시 자격 증명을 받는다.
   - plan 역할: PR과 main에서 사용, 읽기 전용.
   - apply 역할: `production` GitHub Environment에서만 사용, 사람 승인 필수.
4. **apply 권한**: 우선 `AdministratorAccess`를 쓴다.

## 이유
- DynamoDB 잠금 테이블은 이제 필요 없어 리소스와 비용을 줄인다.
- 호스팅 영역은 prod와 staging이 같이 쓰므로, staging을 지웠다 만들어도 영향이 없도록 따로 둔다.
- 장기 액세스 키는 유출 위험이 가장 큰 자격 증명이다. OIDC 임시 자격 증명은 1시간 뒤 만료되고 저장소·환경 조건으로 범위가 제한된다.
- 1인 프로젝트에서 서비스별 최소 권한 정책을 처음부터 관리하면 apply 실패가 잦다. 대신 신뢰 정책(승인된 Environment만)으로 위험을 줄인다.

## 이후 할 일
- 리소스 구성이 안정되면 CloudTrail/IAM Access Analyzer로 실제 사용한 권한을 확인하고 apply 역할 권한을 좁힌다.
