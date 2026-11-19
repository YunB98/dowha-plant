# 기술 결정 기록 (ADR)

중요한 기술 결정을 "왜 그렇게 정했는지"와 함께 기록합니다.
결정이 바뀌면 기존 문서를 지우지 않고, 새 ADR을 추가하고 기존 문서의 상태를 "대체됨"으로 바꿉니다.

| 번호 | 제목 | 상태 |
|---|---|---|
| [0001](0001-cloud-provider-aws.md) | 클라우드로 AWS 사용 | 채택 |
| [0002](0002-single-ec2-docker-compose.md) | EC2 한 대 + Docker Compose 구성 | 채택 |
| [0003](0003-backend-fastapi.md) | 백엔드로 FastAPI 사용 | 채택 |
| [0004](0004-client-side-product-fetch.md) | 상품 목록은 브라우저에서 API로 조회 | 채택 |
| [0005](0005-environments.md) | dev / staging(필요할 때만) / prod 환경 | 채택 |
| [0006](0006-mvp-scope.md) | MVP에서 결제·회원 기능 제외 | 채택 |
| [0007](0007-admin-split.md) | 관리 화면을 사장님용과 운영자용으로 분리 | 채택 |
| [0008](0008-domain-kr.md) | .kr 도메인, 사장님 명의, Route 53 위임 | 대체됨 |
| [0009](0009-domain-dowha-plant-shop.md) | dowha-plant.shop 도메인 사용 | 채택 |
| [0010](0010-inquiry-data-model.md) | 문의 데이터 구조와 금액 스냅샷 | 채택 |
| [0011](0011-terraform-state-and-ci-auth.md) | Terraform 상태 관리와 GitHub Actions 인증 | 채택 |
