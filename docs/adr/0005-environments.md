# 0005. dev / staging(필요할 때만) / prod 환경

- 상태: 채택
- 날짜: 2026-11-19

## 결정
| 환경 | 구성 |
|---|---|
| dev | 로컬 PC에서 Docker Compose |
| staging | `infra/envs/staging`. prod와 같은 Terraform 모듈을 쓰고, 필요할 때만 만들었다가 삭제한다 |
| prod | `infra/envs/prod` |

## 이유
- staging을 상시 운영하면 비용이 2배가 된다.
- staging이 필요한 경우는 인프라 변경, 큰 DB 변경, 복구 훈련 정도다.
- 같은 모듈로 환경을 바로 만들고 지울 수 있다는 것 자체가 IaC의 장점을 보여준다.
