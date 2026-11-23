# 0018. GitHub OIDC 신뢰 정책은 계정·저장소 ID를 포함한 sub로 제한한다

- 상태: 채택
- 날짜: 2026-11-23
- 관련: ADR 0011

## 문제 (장애 기록)
| 시각 (UTC) | 내용 |
|---|---|
| 05:13 | PR #2 워크플로의 plan 작업 2개가 `Could not assume role with OIDC: Not authorized to perform sts:AssumeRoleWithWebIdentity`로 실패 |
| 05:19 | PR #2를 머지했고, main 실행도 같은 단계에서 재시도하다 실패 |
| 05:25 | CloudTrail `AssumeRoleWithWebIdentity` `AccessDenied` 기록에서 토큰의 `sub` 값을 확인해 원인 파악 |
| 05:30 | 신뢰 정책을 로컬(`dowha-admin`)로 수정 적용 → PR #3에서 plan 성공, 머지 후 main 실행 성공 |

원인: 신뢰 정책은 `repo:YunB98/dowha-plant:pull_request`를 기다렸지만, GitHub가 보낸 토큰의 `sub`는
`repo:YunB98@251148256/dowha-plant@1464295966:pull_request`였다 (이름 뒤에 바뀌지 않는 숫자 ID가 붙은 형식).

## 결정
- 신뢰 정책의 `sub` 조건을 `repo:<owner>@<owner_id>/<repo>@<repo_id>:<context>` 형식으로 쓴다.
- 계정 ID와 저장소 ID는 Terraform 변수로 두고, GitHub API(`/repos/<owner>/<repo>`의 `owner.id`, `id`)로 확인한다.

## 이유
- 이름만 비교하면, 저장소가 삭제된 뒤 누군가 같은 이름으로 저장소를 만들 때 역할을 가로챌 수 있다. ID를 포함하면 이 공격이 막힌다.

## 교훈
- OIDC 신뢰 조건은 로컬에서 검증할 수 없다. **새 신뢰 정책은 PR에서 실제로 로그인이 되는지 확인한 뒤 머지한다.**
- CI가 AWS에 로그인하지 못하면 CI로 고칠 수 없다. 이런 수정은 로컬 SSO 권한으로 먼저 적용하고 PR로 코드를 맞춘다.
- 실패 원인은 CloudTrail에서 바로 확인할 수 있다 (`eventName = AssumeRoleWithWebIdentity`, `userIdentity.userName`에 sub 값).
