/* 없는 주소 (빌드하면 out/404.html). CloudFront가 S3 403을 이 페이지 + 404로 바꾼다 (ADR 0021).
   배포 확인 단계가 "찾으시는 페이지가 없어요" 문구를 검사하므로 바꾸면 deploy.yml도 같이 바꾼다. */
import Link from "next/link";

export const metadata = { title: "페이지를 찾을 수 없어요" };

export default function NotFound() {
  return (
    <div className="wrap error-page">
      <div className="eyebrow">404</div>
      <h1>찾으시는 페이지가 없어요.</h1>
      <p className="sub">주소를 확인하거나 홈으로 이동해 주세요.</p>
      <div className="button-row" style={{ justifyContent: "center" }}>
        <Link className="btn" href="/">홈으로</Link>
        <Link className="btn outline" href="/guides/">가이드 목록</Link>
      </div>
    </div>
  );
}
