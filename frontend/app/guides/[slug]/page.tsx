/* 식물 관리 가이드 상세 (프로토타입 guideDetail()). QR 카드를 스캔한 손님이 처음 보는 화면 (ADR 0013) */
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Photo } from "@/components/cards";
import { ContactButton } from "@/components/dialogs";
import { DIFFICULTY_LABEL, GUIDES } from "@/lib/demo";

export const dynamicParams = false;

export function generateStaticParams() {
  return GUIDES.map((g) => ({ slug: g.slug }));
}

type Props = { params: Promise<{ slug: string }> };
const find = async (params: Props["params"]) => { const { slug } = await params; return GUIDES.find((g) => g.slug === slug); };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const g = await find(params);
  return g ? { title: `${g.name} 키우기`, description: `${g.name} 관리법: 햇빛 ${g.light}, 물주기 ${g.watering}` } : {};
}

export default async function GuideDetail({ params }: Props) {
  const g = await find(params);
  if (!g) notFound();
  const rows: [string, string][] = [
    ["난이도", DIFFICULTY_LABEL[g.difficulty]],
    ["햇빛", g.light],
    ["물주기", g.watering],
    ["온도", g.temperature],
    ["습도", g.humidity],
    ["계절별 관리", g.seasonalCare],
    ["문제 해결", g.troubleshooting],
  ];
  return (
    <div className="wrap content">
      <div className="crumb"><Link href="/guides/">관리 가이드</Link> / {g.name}</div>
      <div className="detail">
        <Photo src={g.image} alt={g.name} />
        <div className="detail-info">
          <div className="eyebrow">PLANT CARE GUIDE</div>
          <h1>{g.name}</h1>
          <dl className="meta">{rows.filter(([, v]) => v).map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>
          <h3>이 식물은 도화에서 왔어요.</h3>
          <div className="button-row" style={{ marginTop: 16 }}>
            <ContactButton className="btn">식물 상담하기</ContactButton>
            <Link className="btn outline" href="/guides/">다른 가이드 보기</Link>
          </div>
        </div>
      </div>
    </div>
  );
}
