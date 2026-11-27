/* 식물 상세 (프로토타입 detail()). 식물마다 빌드할 때 HTML로 만든다. 없는 id는 404. */
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Photo } from "@/components/cards";
import { ContactButton } from "@/components/dialogs";
import { StatusBadge } from "@/components/ui";
import { getGuides, getPlants, PLACEHOLDER, staticParams } from "@/lib/content";
import { SALE_LABEL } from "@/lib/demo";
import { won } from "@/lib/format";

export const dynamicParams = false;

export async function generateStaticParams() {
  return staticParams("id", (await getPlants()).map((p) => p.id));
}

type Props = { params: Promise<{ id: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  const p = (await getPlants()).find((x) => x.id === id);
  return p ? { title: p.name, description: p.summary } : {};
}

export default async function PlantDetail({ params }: Props) {
  const { id } = await params;
  const p = id === PLACEHOLDER ? undefined : (await getPlants()).find((x) => x.id === id);
  if (!p) notFound();
  // 공개된 가이드가 있을 때만 연결 (없는 가이드로 가는 링크를 만들지 않는다)
  const guide = p.guideSlug && (await getGuides()).some((g) => g.slug === p.guideSlug) ? p.guideSlug : null;
  return (
    <div className="wrap content">
      <div className="crumb"><Link href="/">홈</Link> / <Link href="/plants/">식물</Link> / {p.name}</div>
      <div className="detail">
        <Photo src={p.image} alt={p.name} />
        <div className="detail-info">
          <StatusBadge status={p.saleStatus} />
          <h1>{p.name}</h1>
          <p className="sub">{p.summary}</p>
          <div className="price">{won(p.price)}</div>
          <dl className="meta">
            {p.size ? <div><dt>크기</dt><dd>{p.size}</dd></div> : null}
            <div><dt>추천 목적</dt><dd>{p.purposes.join(" · ")}</dd></div>
            {p.saleStatus ? <div><dt>판매 상태</dt><dd>{SALE_LABEL[p.saleStatus]}</dd></div> : null}
          </dl>
          <div className="button-row">
            <ContactButton className="btn">{p.saleStatus === "sold" ? "비슷한 식물 추천받기" : "이 식물 상담하기"}</ContactButton>
            {guide ? <Link className="btn outline" href={`/guides/${guide}/`}>관리 가이드</Link> : null}
            {p.blogUrl ? <a className="btn outline" href={p.blogUrl} target="_blank" rel="noopener">블로그에서 전체 읽기</a> : null}
          </div>
          <div className="panel" style={{ marginTop: 30 }}>
            <h2>도화의 공통 안내</h2>
            <p className="sub">맞춤 식물 추천 · 메시지 카드 · 배송 안내는 상담으로 확인해 주세요. 전주 지역은 8만 원 이상 무료 배송이고, 그 외에는 식물 크기에 따라 달라요.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
