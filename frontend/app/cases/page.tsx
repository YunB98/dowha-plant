/* 진행 사례 (프로토타입 cases()). 전체 목록은 빌드 시 HTML, 기관 종류·페이지는 브라우저에서 (?type=, ?page=) */
import type { Metadata } from "next";
import { Suspense } from "react";

import { CasesBrowser, CasesView } from "@/components/cases-browser";
import { PageTop } from "@/components/ui";
import { CASES } from "@/lib/demo";

export const metadata: Metadata = {
  title: "진행 사례",
  description: "도화와 함께한 학교·어린이집·복지관·기관·기업 원예 수업과 출강 이야기.",
};

export default function CasesPage() {
  const cases = [...CASES].sort((a, b) => b.heldOn.localeCompare(a.heldOn) || b.id - a.id);
  return (
    <>
      <PageTop en="OUR WORK" title="진행 사례" sub="도화와 함께한 원예 수업과 출강 이야기." />
      <Suspense fallback={<CasesView cases={cases} type="" page={1} />}>
        <CasesBrowser cases={cases} />
      </Suspense>
    </>
  );
}
