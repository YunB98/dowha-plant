/* 오시는 길 (프로토타입 visit()) */
import type { Metadata } from "next";

import { Photo } from "@/components/cards";
import { ContactButton } from "@/components/dialogs";
import { PageTop } from "@/components/ui";
import { getShop } from "@/lib/content";

export async function generateMetadata(): Promise<Metadata> {
  const shop = await getShop();
  return { title: "오시는 길", description: [shop.location, shop.address, shop.hours.join(", ")].filter(Boolean).join(". ") };
}

export default async function VisitPage() {
  const shop = await getShop();
  const rows = ([
    ["주소", [shop.address]],
    ["영업시간", shop.hours],
    ["전화번호", [shop.phone]],
  ] as [string, string[]][]).filter(([, v]) => v.some(Boolean)); // 비어 있는 항목은 숨긴다
  return (
    <>
      <PageTop en="VISIT DOHWA" title="오시는 길" sub={`${shop.location} · 식물가게 도화`} />
      <div className="wrap content">
        <div className="split">
          <Photo src="/assets/hero.webp" alt="매장 분위기 참고 콘셉트" />
          <div>
            <h2>도화</h2>
            <dl className="meta">
              {rows.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v.map((line, i) => <span key={line}>{i ? <br /> : null}{line}</span>)}</dd></div>)}
            </dl>
            <div className="button-row">
              <a className="btn outline" target="_blank" rel="noopener" href={`https://map.naver.com/p/search/${encodeURIComponent(shop.address || `식물가게 도화 ${shop.location}`)}`}>지도에서 검색 ↗</a>
              <ContactButton className="btn">상담하기</ContactButton>
            </div>
            <p className="hint" style={{ marginTop: 12 }}>매장 사진은 디자인 콘셉트이며 실제 사진이 아닙니다.</p>
          </div>
        </div>
      </div>
    </>
  );
}
