/* 식물 목록 (프로토타입 plants()).
   빌드할 때 전체 목록을 HTML로 만들고(검색엔진용), 필터(?purpose=, ?available=1)는 브라우저에서 적용한다. */
import type { Metadata } from "next";
import { Suspense } from "react";

import { PlantsBrowser, PlantsView } from "@/components/plants-browser";
import { PageTop } from "@/components/ui";
import { getPlants } from "@/lib/content";
import { PURPOSES } from "@/lib/demo";

export const metadata: Metadata = {
  title: "식물",
  description: "도화에서 소개한 식물. 개업·승진 선물, 집들이 선물, 거실·매장 인테리어 식물을 목적별로 골라 보세요.",
};

export default async function PlantsPage() {
  const plants = [...(await getPlants())].sort((a, b) => b.publishedAt.localeCompare(a.publishedAt));
  return (
    <>
      <PageTop en="PLANT COLLECTION" title="식물" sub="도화에서 소개한 식물들을 만나보세요." />
      <Suspense fallback={<PlantsView plants={plants} purposes={[...PURPOSES]} purpose="" available={false} />}>
        <PlantsBrowser plants={plants} purposes={[...PURPOSES]} />
      </Suspense>
    </>
  );
}
