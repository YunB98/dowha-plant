# 0023. 애플리케이션 배포는 ARM 러너 빌드 + S3 배포 묶음 + SSM 명령으로 한다

- 상태: 채택
- 날짜: 2026-11-24

## 배경
서버는 t4g.micro(ARM) 한 대이고 SSH 포트가 없다 (ADR 0021). 이미지는 서버에서 빌드하지 않는다 (CPU 크레딧, ADR 0022).
인프라 변경(terraform.yml)과 앱 배포는 바뀌는 빈도와 위험도가 달라서 따로 둔다.

## 결정
`.github/workflows/deploy.yml`

```
PR   : test (pytest, docker compose config, shellcheck)
main : test → [production 승인] → deploy
         ARM 러너에서 이미지 빌드 → ECR push (커밋 SHA 12자리 태그)
         deploy/ 폴더를 묶어 backup 버킷 releases/{tag}.tgz 업로드
         SSM SendCommand → 서버가 묶음을 받아 /opt/dowha에 풀고 deploy.sh 실행
         CloudFront 경유 /api/v1/health 200 확인
```

| 결정 | 이유 |
|---|---|
| `ubuntu-24.04-arm` 러너 | 공개 저장소는 무료. QEMU 에뮬레이션보다 몇 배 빠르고 서버와 같은 아키텍처 |
| 배포 역할을 Terraform apply 역할과 **분리** | apply 역할은 AdministratorAccess. 앱 배포는 ECR push, `releases/` 업로드, 이 서버 한 대에 `AWS-RunShellScript`만 할 수 있다 |
| 배포 역할은 `environment:production` sub만 신뢰 | 승인 없이는 역할을 받을 수 없다 (ADR 0018 형식) |
| 파일 전달은 S3, 실행은 SSM | SSM 명령 파라미터 크기 제한이 있고, 서버는 이미 backup 버킷 읽기 권한이 있다. 묶음은 수명 주기(30일)로 자동 삭제 |
| 서버는 태그(`Name=dowha-plant-prod-app`)로 찾는다 | 서버를 다시 만들어도 워크플로를 고칠 필요가 없다 |
| 같은 태그 이미지가 있으면 빌드 생략 | ECR 태그가 IMMUTABLE이라 재실행(같은 커밋 재배포)이 실패하지 않게 |
| 배포가 겹치지 않게 `concurrency` | 진행 중인 배포는 취소하지 않는다 (서버가 중간 상태로 남지 않게) |

## 검토한 대안
| 대안 | 문제 |
|---|---|
| 서버에서 `git pull` 후 빌드 | 서버에 GitHub 자격 증명이 필요하고, 1GB 서버에서 빌드하면 서비스가 느려진다 |
| CodeDeploy | 에이전트와 앱·배포 그룹 설정이 추가된다. 서버 한 대에는 과하다 |
| x86 러너 + QEMU | 느리고(파이썬 휠 설치가 특히), 결과는 같다 |

## 결과
- 롤백: 이전 커밋으로 `workflow_dispatch`를 다시 실행하면 그 SHA의 이미지와 묶음으로 되돌아간다 (이미지가 ECR에 남아 있는 최근 10개까지).
- 서버의 `.env`, Alertmanager 렌더링 결과는 배포가 지우지 않는다 (SSM 값에서 매번 다시 만든다).
- 무중단 배포는 아니다. `docker compose up -d`가 바뀐 컨테이너만 재시작하므로 API가 몇 초 끊길 수 있다. 하루 방문 수십~수백 수준이라 받아들인다.
- 프론트엔드(Next.js 정적 빌드 → S3 site 버킷 + 캐시 무효화)는 프론트엔드를 만들 때 이 워크플로에 작업을 추가한다.
