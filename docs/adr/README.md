# 기술 결정 기록 (ADR)

중요한 기술 결정을 "왜 그렇게 정했는지"와 함께 기록합니다.
결정이 바뀌면 기존 문서를 지우지 않고, 새 ADR을 추가하고 기존 문서의 상태를 "대체됨"으로 바꿉니다.

| 번호 | 제목 | 상태 |
|---|---|---|
| [0001](0001-cloud-provider-aws.md) | 클라우드로 AWS 사용 | 채택 |
| [0002](0002-single-ec2-docker-compose.md) | EC2 한 대 + Docker Compose 구성 | 채택 |
| [0003](0003-backend-fastapi.md) | 백엔드로 FastAPI 사용 | 채택 |
| [0004](0004-client-side-product-fetch.md) | 상품 목록은 브라우저에서 API로 조회 | 대체됨 |
| [0005](0005-environments.md) | dev / staging(필요할 때만) / prod 환경 | 채택 |
| [0006](0006-mvp-scope.md) | MVP에서 결제·회원 기능 제외 | 일부 대체됨 |
| [0007](0007-admin-split.md) | 관리 화면을 사장님용과 운영자용으로 분리 | 채택 |
| [0008](0008-domain-kr.md) | .kr 도메인, 사장님 명의, Route 53 위임 | 대체됨 |
| [0009](0009-domain-dowha-plant-shop.md) | dowha-plant.shop 도메인 사용 | 채택 |
| [0010](0010-inquiry-data-model.md) | 문의 데이터 구조와 금액 스냅샷 | 대체됨 |
| [0011](0011-terraform-state-and-ci-auth.md) | Terraform 상태 관리와 GitHub Actions 인증 | 채택 |
| [0012](0012-pivot-to-outreach-and-discovery.md) | 홈페이지 목표 전환: 새 손님 유입과 출강 확대 | 채택 |
| [0013](0013-plant-guide-qr-indirection.md) | 식물 관리 QR은 짧은 코드로 간접 연결 | 채택 |
| [0014](0014-analytics-umami.md) | 방문 분석은 Umami 직접 운영 | 채택 |
| [0015](0015-static-content-pages-with-rebuild.md) | 콘텐츠 페이지는 빌드 시 HTML 생성, 공개 시 자동 재빌드 | 채택 |
| [0016](0016-multi-account-and-sso.md) | AWS 멀티 계정 구조와 IAM Identity Center(SSO) | 채택 |
| [0017](0017-organization-scp-guardrails.md) | 조직 SCP 가드레일 | 채택 |
| [0018](0018-github-oidc-subject-format.md) | GitHub OIDC 신뢰 정책은 ID 포함 sub로 제한 | 채택 |
| [0019](0019-external-health-check-uptimerobot.md) | 외부 헬스체크는 UptimeRobot | 채택 |
| [0020](0020-prod-network-and-storage.md) | prod 네트워크와 저장소 구성 | 채택 |
| [0021](0021-prod-compute-and-cdn.md) | prod 서버와 CDN 구성 | 일부 대체됨 |
| [0022](0022-downsize-to-t4g-micro.md) | 서버를 t4g.micro로 낮춰 월 20달러 이내 운영 | 채택 |
| [0023](0023-app-deploy-pipeline.md) | 앱 배포: ARM 러너 빌드 + S3 배포 묶음 + SSM 명령 | 채택 |
