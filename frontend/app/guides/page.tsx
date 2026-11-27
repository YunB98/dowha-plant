/* 식물 관리 가이드 목록 (프로토타입 guides(), guideRows()). 이름순, 검색은 브라우저에서 */
import type { Metadata } from "next";

import { GuideList } from "@/components/guide-list";
import { PageTop } from "@/components/ui";
import { getGuides } from "@/lib/content";

export const metadata: Metadata = {
  title: "식물 관리 가이드",
  description: "도화에서 만난 식물을 건강하게 키우는 방법. 햇빛, 물주기, 온도, 습도, 계절별 관리.",
};

export default async function GuidesPage() {
  const guides = [...(await getGuides())].sort((a, b) => a.name.localeCompare(b.name, "ko"));
  return (
    <>
      <PageTop en="PLANT CARE" title="식물 관리 가이드" sub="도화에서 만난 식물을 건강하게 키우는 방법." />
      <div className="wrap content">
        <GuideList guides={guides} />
      </div>
    </>
  );
}
