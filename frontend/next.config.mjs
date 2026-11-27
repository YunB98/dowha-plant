// 정적 HTML로 빌드해서 S3 + CloudFront로 배포한다 (ADR 0015, 0021, 0028).
// - trailingSlash: /plants → /plants/index.html. CloudFront Function이 끝의 /를 index.html로 바꾼다
// - images.unoptimized: 정적 배포에는 이미지 변환 서버가 없다
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
  reactStrictMode: true,
  poweredByHeader: false,
};

export default nextConfig;
