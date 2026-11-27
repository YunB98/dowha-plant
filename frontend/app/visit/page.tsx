/* 오시는 길 (프로토타입 visit()) */
import type { Metadata } from "next";

import { Photo } from "@/components/cards";
import { ContactButton } from "@/components/dialogs";
import { PageTop } from "@/components/ui";
import { SHOP } from "@/lib/demo";

export const metadata: Metadata = {
  title: "오시는 길",
  description: `${SHOP.address}. 영업시간 ${SHOP.hours.join(", ")}.`,
};

export default function VisitPage() {
  const rows: [string, string[]][] = [
    ["주소", [SHOP.address]],
    ["영업시간", SHOP.hours],
    ["전화번호", [SHOP.phone]],
  ];
  return (
    <>
      <PageTop en="VISIT DOHWA" title="오시는 길" sub={`${SHOP.location} · 식물가게 도화`} />
      <div className="wrap content">
        <div className="split">
          <Photo src="/assets/hero.webp" alt="매장 분위기 참고 콘셉트" />
          <div>
            <h2>도화</h2>
            <dl className="meta">
              {rows.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v.map((line, i) => <span key={line}>{i ? <br /> : null}{line}</span>)}</dd></div>)}
            </dl>
            <div className="button-row">
              <a className="btn outline" target="_blank" rel="noopener" href={`https://map.naver.com/p/search/${encodeURIComponent(SHOP.address)}`}>지도에서 검색 ↗</a>
              <ContactButton className="btn">상담하기</ContactButton>
            </div>
            <p className="hint" style={{ marginTop: 12 }}>매장 사진은 디자인 콘셉트이며 실제 사진이 아닙니다.</p>
          </div>
        </div>
      </div>
    </>
  );
}
