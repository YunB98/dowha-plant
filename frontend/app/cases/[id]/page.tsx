/* 진행 사례 상세 (프로토타입 caseDetail()) */
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { heldOn, Photo } from "@/components/cards";
import { PageTop } from "@/components/ui";
import { CASES, ORGANIZATION_LABEL } from "@/lib/demo";

export const dynamicParams = false;

export function generateStaticParams() {
  return CASES.map((c) => ({ id: String(c.id) }));
}

type Props = { params: Promise<{ id: string }> };
const find = async (params: Props["params"]) => { const { id } = await params; return CASES.find((c) => String(c.id) === id); };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const c = await find(params);
  return c ? { title: c.title, description: c.summary } : {};
}

export default async function CaseDetail({ params }: Props) {
  const c = await find(params);
  if (!c) notFound();
  const sub = [ORGANIZATION_LABEL[c.organizationType], c.organizationDisplayName, heldOn(c.heldOn),
    c.participantCount ? `${c.participantCount}명` : ""].filter(Boolean).join(" · ");
  return (
    <>
      <PageTop en="OUR WORK" title={c.title} sub={sub} />
      <div className="wrap content">
        <div className="detail">
          <Photo src={c.image} alt={c.title} />
          <div>
            <p>{c.summary}</p>
            <div className="button-row" style={{ marginTop: 25 }}>
              <Link className="btn" href="/outreach/">비슷한 수업 문의</Link>
              <Link className="btn outline" href="/cases/">목록으로</Link>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
