/* 프로토타입의 작은 문자열 함수(section, pageTop, plantCard, status, empty)를 같은 마크업의 컴포넌트로 옮긴 것 */
import Link from "next/link";
import type { ReactNode } from "react";

import { Photo } from "@/components/cards";
import { type Plant, SALE_LABEL, type SaleStatus } from "@/lib/demo";
import { won } from "@/lib/format";

export function StatusBadge({ status }: { status: SaleStatus | null }) {
  if (!status) return null;
  const tone = status === "sold" ? "sold" : status === "reserved" ? "reserved" : "";
  return <span className={`state ${tone}`.trim()}>{SALE_LABEL[status]}</span>;
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>;
}

export function Section({
  en, title, sub, href, linkLabel, alt, id, children,
}: {
  en: string; title: ReactNode; sub?: string; href?: string; linkLabel?: string; alt?: boolean; id?: string; children: ReactNode;
}) {
  return (
    <section className={`section${alt ? " alt" : ""}`} id={id}>
      <div className="wrap">
        <div className="section-head">
          <div>
            <div className="eyebrow">{en}</div>
            <h2>{title}</h2>
            {sub ? <p className="sub">{sub}</p> : null}
          </div>
          {href ? <Link className="arrow-link" href={href}>{linkLabel} ↗</Link> : null}
        </div>
        {children}
      </div>
    </section>
  );
}

export function PageTop({ en, title, sub }: { en: string; title: string; sub?: string }) {
  return (
    <div className="page-top">
      <div className="wrap">
        <div className="eyebrow">{en}</div>
        <h1>{title}</h1>
        {sub ? <p>{sub}</p> : null}
      </div>
    </div>
  );
}

export function PlantCard({ plant }: { plant: Plant }) {
  return (
    <Link className="plant-card" href={`/plants/${plant.id}/`}>
      <div className="plant-photo">
        <Photo src={plant.image} alt={plant.name} />
        <StatusBadge status={plant.saleStatus} />
      </div>
      <div className="card-text">
        <h3>{plant.name}</h3>
        <p>{plant.purposes.slice(0, 2).join(" · ")}</p>
        <div className="price">{won(plant.price)}</div>
      </div>
    </Link>
  );
}
