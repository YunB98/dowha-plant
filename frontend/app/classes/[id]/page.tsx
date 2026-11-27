/* 클래스 상세 (프로토타입 classDetail()) */
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Photo, workshopDuration, workshopPeople, WorkshopState } from "@/components/cards";
import { ContactButton } from "@/components/dialogs";
import { WORKSHOPS } from "@/lib/demo";
import { won } from "@/lib/format";

export const dynamicParams = false;

export function generateStaticParams() {
  return WORKSHOPS.map((w) => ({ id: String(w.id) }));
}

type Props = { params: Promise<{ id: string }> };
const find = async (params: Props["params"]) => { const { id } = await params; return WORKSHOPS.find((w) => String(w.id) === id); };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const w = await find(params);
  return w ? { title: w.name, description: w.description } : {};
}

export default async function ClassDetail({ params }: Props) {
  const w = await find(params);
  if (!w) notFound();
  const rows: [string, string][] = [
    ["1인 가격", won(w.pricePerPerson)],
    ["인원", workshopPeople(w)],
    ["시간", workshopDuration(w)],
    ["시즌", w.isSeasonal ? "시즌 한정" : "상시"],
    ["출강", w.supportsOutreach ? "가능" : "협의"],
  ];
  return (
    <div className="wrap content">
      <div className="crumb"><Link href="/classes/">클래스·출강</Link> / {w.name}</div>
      <div className="detail">
        <Photo src={w.image} alt={w.name} />
        <div className="detail-info">
          <WorkshopState status={w.status} />
          <h1>{w.name}</h1>
          <p className="sub">{w.description}</p>
          <dl className="meta">{rows.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>
          <div className="button-row">
            <Link className="btn" href="/outreach/">견적 문의</Link>
            <ContactButton className="btn outline">상담하기</ContactButton>
          </div>
        </div>
      </div>
    </div>
  );
}
