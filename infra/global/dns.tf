# prod와 staging이 함께 쓰는 호스팅 영역.
# 생성 후 출력되는 네임서버 4개를 가비아 도메인 관리에서 등록한다.

resource "aws_route53_zone" "main" {
  name    = var.domain_name
  comment = "${var.project} - prod, staging 공용"

  # 영역을 지웠다 다시 만들면 네임서버가 바뀌어 가비아 설정을 다시 해야 한다.
  lifecycle {
    prevent_destroy = true
  }
}
