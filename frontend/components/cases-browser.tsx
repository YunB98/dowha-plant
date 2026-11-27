"use client";
/* 진행 사례 목록의 기관 종류 필터와 페이지 (한 페이지 20개, 프로토타입 cases()) */
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { CaseCard } from "@/components/cards";
import { Empty } from "@/components/ui";
import { type Case, ORGANIZATION_LABEL, type OrganizationType } from "@/lib/demo";

const PAGE_SIZE = 20;
const TYPES = Object.keys(ORGANIZATION_LABEL) as OrganizationType[];

const href = (pathname: string, type: string, page: number) => {
  const q = new URLSearchParams();
  if (type) q.set("type", type);
  if (page > 1) q.set("page", String(page));
  const s = q.toString();
  return s ? `${pathname}?${s}` : pathname;
};

export function CasesView({ cases, type, page, onType }: {
  cases: Case[]; type: string; page: number; onType?: (t: string) => void;
}) {
  const list = cases.filter((c) => !type || c.organizationType === type);
  const pages = Math.max(1, Math.ceil(list.length / PAGE_SIZE));
  const current = Math.min(page, pages);
  return (
    <div className="wrap content">
      <div className="filterbar">
        <button type="button" className={`chip${!type ? " active" : ""}`} aria-pressed={!type} onClick={() => onType?.("")}>전체</button>
        {TYPES.map((t) => (
          <button key={t} type="button" className={`chip${type === t ? " active" : ""}`} aria-pressed={type === t} onClick={() => onType?.(t)}>{ORGANIZATION_LABEL[t]}</button>
        ))}
      </div>
      <div className="grid">
        {list.length ? list.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE).map((c) => <CaseCard key={c.id} c={c} />)
          : <Empty>등록된 진행 사례가 없습니다.</Empty>}
      </div>
      <div className="pagination">
        {current > 1 ? <Link className="btn outline small" href={href("/cases/", type, current - 1)}>이전</Link> : null}
        <span className="page-counter">{current} / {pages}</span>
        {current < pages ? <Link className="btn outline small" href={href("/cases/", type, current + 1)}>다음</Link> : null}
      </div>
    </div>
  );
}

export function CasesBrowser({ cases }: { cases: Case[] }) {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const raw = params.get("type") ?? "";
  const type = (TYPES as string[]).includes(raw) ? raw : "";
  const page = Math.max(1, parseInt(params.get("page") ?? "1", 10) || 1);
  return <CasesView cases={cases} type={type} page={page} onType={(t) => router.replace(href(pathname, t, 1), { scroll: false })} />;
}
