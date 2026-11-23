terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
      # CloudFront용 ACM 인증서는 us-east-1에만 만들 수 있다.
      configuration_aliases = [aws.us_east_1]
    }
  }
}
