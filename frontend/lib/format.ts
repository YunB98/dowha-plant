/** 가격 표시. 값이 없으면 "상담 후 안내" (프로토타입 won()과 같다) */
export function won(n: number | null | undefined): string {
  return n === null || n === undefined ? "상담 후 안내" : `${n.toLocaleString("ko-KR")}원`;
}

/** 출시 전에는 사이트 전체에 "준비 중" 띠와 noindex. 출시할 때 빌드 환경 변수 SITE_STAGE=live */
export const IS_PREVIEW = process.env.SITE_STAGE !== "live";
