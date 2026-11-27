"use client";
/* 관리 가이드 목록과 이름 검색 (프로토타입 guides()의 #guide-search). 검색 전 목록은 빌드 시 HTML에 들어간다 */
import Link from "next/link";
import { useState } from "react";

import { Photo } from "@/components/cards";
import { Empty } from "@/components/ui";
import type { GuideListItem } from "@/lib/content";
import { DIFFICULTY_LABEL } from "@/lib/demo";

export function GuideList({ guides }: { guides: GuideListItem[] }) {
  const [q, setQ] = useState("");
  const list = guides.filter((g) => g.name.includes(q.trim()));
  return (
    <>
      <div className="filterbar">
        <input id="guide-search" type="search" placeholder="식물 이름 검색" aria-label="식물 이름 검색" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      <div className="guide-list" id="guide-list">
        {list.length ? list.map((g) => (
          <Link key={g.slug} className="guide-row" href={`/guides/${g.slug}/`}>
            <Photo src={g.image} alt={g.name} />
            <div>
              <h3>{g.name}</h3>
              <p className="sub">난이도 {DIFFICULTY_LABEL[g.difficulty]}{g.note ? ` · ${g.note}` : ""}</p>
            </div>
            <span className="spacer">↗</span>
          </Link>
        )) : <Empty>해당 식물 가이드가 없어요.</Empty>}
      </div>
    </>
  );
}
