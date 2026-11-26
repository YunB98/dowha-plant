# 0026. S3·CloudFront 접근은 botocore 서명 + httpx로 (boto3를 쓰지 않는다)

- 상태: 채택
- 날짜: 2026-11-26

## 배경
사진·소개서 업로드(docs/api-spec.md 2장)로 API가 S3와 CloudFront를 다뤄야 한다.
API 컨테이너 메모리 한도는 160MB이고(ADR 0022), 로그인 해시 등으로 순간 사용량이 오른다(ADR 0025).
API가 쓰는 AWS 요청은 다섯 가지뿐이다: presigned POST, HEAD/앞부분 GET, 복사, 삭제, 캐시 무효화.

## 측정 (python:3.13.5-slim, 프로세스 RSS)
| 방식 | 늘어나는 메모리 |
|---|---|
| boto3 import + S3·CloudFront 클라이언트 | **약 45MB** (import 25MB, S3 클라이언트 16MB: 서비스 정의 JSON) |
| botocore 서명·자격 증명만 (httpx는 이미 쓰고 있음) | **약 12MB** |

api 컨테이너 전체: 기동 직후 74MB → 87.5MB (botocore와 이번 코드 포함). boto3였다면 120MB를 넘는다.

## 결정
| 결정 | 이유 |
|---|---|
| 서명은 botocore `S3SigV4Auth`, `S3SigV4PostAuth`, `SigV4Auth` | 보안에 민감한 계산은 AWS 공식 코드를 그대로 쓴다 |
| 자격 증명은 botocore 기본 체인 | EC2 인스턴스 역할(IMDSv2, hop limit 2)과 만료 전 자동 갱신. 로컬에서는 SSO 프로필 |
| 요청은 httpx로 직접 (`app/storage.py`, 약 100줄) | 쓰는 API가 다섯 개라 직접 만들어도 작다 |
| `Storage` 인터페이스 + 테스트용 메모리 구현 | 테스트가 AWS 없이 돈다. moto 같은 큰 의존성이 필요 없다 |
| CopyObject는 200이어도 본문의 `<Error>`를 확인 | S3는 복사 중 실패를 200 + 오류 본문으로 알려 주기도 한다 |

## 확인 (2026-11-26, 운영 media 버킷, 임시 파일은 지움)
presigned POST 업로드 204 / 다른 `Content-Type`·다른 key는 403 / 크기 초과 400 `EntityTooLarge` /
CORS는 사이트 주소만 허용 / HEAD·앞부분 읽기 / 복사 후 CloudFront `/images/*`로 공개, `Cache-Control` 1년 /
`uploads/tmp/`는 공개되지 않음 / 삭제.
서버 인스턴스 역할로 site 버킷에 복사하는 것과 캐시 무효화는 배포 후 소개서 교체로 확인한다.

## 한계
- AWS API를 더 많이 쓰게 되면(예: SES, SQS) 직접 만드는 코드가 늘어난다. 그때는 boto3로 바꾸고 api 메모리 한도를 다시 정한다.
- 요청 재시도는 하지 않는다. 실패하면 503으로 응답하고 사장님이 다시 시도한다 (관리 화면 작업이라 드물다).
