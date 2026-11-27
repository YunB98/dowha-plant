/* 클래스·진행 사례 카드 (프로토타입 classCard(), cases()의 카드). 마크업은 plant-card와 같다 */
import Link from "next/link";
import type { ReactNode } from "react";

import { type Case, ORGANIZATION_LABEL, range, type Workshop, WORKSHOP_STATUS_LABEL } from "@/lib/demo";
import { won } from "@/lib/format";

export function Photo({ src, alt }: { src: string | null; alt: string }) {
  // 사진이 아직 없으면 빈 칸 (디자인 전달서 "사진 없는 카드")
  // eslint-disable-next-line @next/next/no-img-element
  return src ? <img src={src} alt={alt} loading="lazy" /> : <div className="photo-empty" aria-hidden="true" />;
}

export function WorkshopState({ status }: { status: Workshop["status"] }) {
  return <span className={`state${status === "closed" ? " sold" : ""}`}>{WORKSHOP_STATUS_LABEL[status]}</span>;
}

function Card({ href, image, alt, badge, title, meta, price }: {
  href: string; image: string | null; alt: string; badge?: ReactNode; title: string; meta: string; price?: string;
}) {
  return (
    <Link className="plant-card" href={href}>
      <div className="plant-photo"><Photo src={image} alt={alt} />{badge}</div>
      <div className="card-text">
        <h3>{title}</h3>
        <p>{meta}</p>
        {price ? <div className="price">{price}</div> : null}
      </div>
    </Link>
  );
}

export const workshopPeople = (w: Workshop) => range(w.minPeople, w.maxPeople, "명");
export const workshopDuration = (w: Workshop) => range(w.durationMin, w.durationMax, "분");

export function WorkshopCard({ w }: { w: Workshop }) {
  return (
    <Card href={`/classes/${w.id}/`} image={w.image} alt={w.name} badge={<WorkshopState status={w.status} />}
      title={w.name} meta={`${workshopPeople(w)} · ${workshopDuration(w)}`} price={won(w.pricePerPerson)} />
  );
}

export const heldOn = (d: string) => d.replaceAll("-", ".");

export function CaseCard({ c }: { c: Case }) {
  return (
    <Card href={`/cases/${c.id}/`} image={c.image} alt={c.title}
      title={c.title} meta={`${ORGANIZATION_LABEL[c.organizationType]} · ${heldOn(c.heldOn)}`} />
  );
}
