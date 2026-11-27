"use client";
/* 식물 목록의 필터 (프로토타입 plants() + data-purpose, #available 처리).
   주소(?purpose=, ?available=1)에 상태를 둬서 홈의 "목적별로 고르기" 링크와 공유 링크가 그대로 동작한다. */
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { Empty, PlantCard } from "@/components/ui";
import type { Plant } from "@/lib/demo";

type ViewProps = {
  plants: Plant[];
  purposes: string[];
  purpose: string;
  available: boolean;
  onPurpose?: (p: string) => void;
  onAvailable?: (v: boolean) => void;
};

export function PlantsView({ plants, purposes, purpose, available, onPurpose, onAvailable }: ViewProps) {
  const list = plants.filter((p) => (!purpose || p.purposes.includes(purpose)) && (!available || p.saleStatus === "available"));
  return (
    <div className="wrap content">
      <div className="filterbar">
        <button type="button" className={`chip${!purpose ? " active" : ""}`} aria-pressed={!purpose} onClick={() => onPurpose?.("")}>전체</button>
        {purposes.map((t) => (
          <button key={t} type="button" className={`chip${t === purpose ? " active" : ""}`} aria-pressed={t === purpose} onClick={() => onPurpose?.(t)}>{t}</button>
        ))}
      </div>
      <div className="filterbar">
        <span className="hint">총 {list.length}개</span>
        <label className="push">
          <input type="checkbox" id="available" checked={available} onChange={(e) => onAvailable?.(e.target.checked)} /> 판매 중만 보기
        </label>
        <span className="hint">최신순</span>
      </div>
      <div className="grid four">
        {list.length ? list.map((p) => <PlantCard key={p.id} plant={p} />) : <Empty>조건에 맞는 식물이 없어요.</Empty>}
      </div>
    </div>
  );
}

export function PlantsBrowser({ plants, purposes }: { plants: Plant[]; purposes: string[] }) {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const purpose = params.get("purpose") ?? "";
  const available = params.get("available") === "1";

  const update = (next: { purpose?: string; available?: boolean }) => {
    const q = new URLSearchParams(params.toString());
    const p = next.purpose ?? purpose;
    const a = next.available ?? available;
    if (p) q.set("purpose", p); else q.delete("purpose");
    if (a) q.set("available", "1"); else q.delete("available");
    const s = q.toString();
    router.replace(s ? `${pathname}?${s}` : pathname, { scroll: false });
  };

  return (
    <PlantsView
      plants={plants} purposes={purposes}
      purpose={purposes.includes(purpose) ? purpose : ""} available={available}
      onPurpose={(p) => update({ purpose: p })} onAvailable={(v) => update({ available: v })}
    />
  );
}
