# 서버 한 대 구성용 네트워크.
# - 퍼블릭 서브넷만 둔다. NAT Gateway(월 4만 원 이상)를 쓰지 않는다. (ADR 0020)
# - EC2 → S3 트래픽은 게이트웨이 엔드포인트로 보내 인터넷을 거치지 않게 한다 (무료).

resource "aws_vpc" "this" {
  cidr_block           = var.cidr_block
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = { Name = var.name }
}

# 기본 보안 그룹의 규칙을 모두 비운다. 실수로 기본 보안 그룹을 쓰면 아무 통신도 되지 않는다.
resource "aws_default_security_group" "this" {
  vpc_id = aws_vpc.this.id

  tags = { Name = "${var.name}-default-deny" }
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id

  tags = { Name = var.name }
}

resource "aws_subnet" "public" {
  for_each = var.public_subnets

  vpc_id            = aws_vpc.this.id
  availability_zone = each.key
  cidr_block        = each.value

  # 공인 IP는 자동으로 붙이지 않는다. 필요한 인스턴스에만 명시적으로 붙인다.
  map_public_ip_on_launch = false

  tags = { Name = "${var.name}-public-${each.key}" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id

  tags = { Name = "${var.name}-public" }
}

resource "aws_route" "public_internet" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.this.id
}

resource "aws_route_table_association" "public" {
  for_each = aws_subnet.public

  subnet_id      = each.value.id
  route_table_id = aws_route_table.public.id
}

data "aws_region" "current" {}

resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.this.id
  service_name      = "com.amazonaws.${data.aws_region.current.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.public.id]

  tags = { Name = "${var.name}-s3" }
}
