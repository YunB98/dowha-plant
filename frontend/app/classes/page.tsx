/* 클래스·출강 (프로토타입 classes()) */
import type { Metadata } from "next";
import Link from "next/link";

import { WorkshopCard } from "@/components/cards";
import { Empty, PageTop } from "@/components/ui";
import { getWorkshops } from "@/lib/content";

export const metadata: Metadata = {
  title: "클래스·출강",
  description: "도화의 원데이 클래스와 학교·기관·기업 출강 원예 프로그램.",
};

export default async function ClassesPage() {
  const workshops = await getWorkshops();
  return (
    <>
      <PageTop en="CLASS & WORKSHOP" title="클래스·출강" sub="원데이 클래스부터 기관·기업 원예 프로그램까지." />
      <div className="wrap content">
        <div className="button-row" style={{ marginBottom: 30 }}>
          <Link className="btn" href="/outreach/">출강·단체 견적 문의</Link>
          <Link className="btn outline" href="/cases/">진행 사례 보기</Link>
        </div>
        <div className="grid">
          {workshops.length ? workshops.map((w) => <WorkshopCard key={w.id} w={w} />) : <Empty>준비 중인 클래스입니다.</Empty>}
        </div>
      </div>
    </>
  );
}
