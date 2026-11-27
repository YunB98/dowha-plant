/* 출강·단체 견적 문의 (프로토타입 quote()). 실제 API로 접수한다 (POST /api/v1/inquiries) */
import type { Metadata } from "next";

import { InquiryForm } from "@/components/inquiry-form";
import { PageTop } from "@/components/ui";
import { SHOP, WORKSHOPS } from "@/lib/demo";

export const metadata: Metadata = {
  title: "견적 문의",
  description: "학교·어린이집·복지관·기관·기업 출강과 단체 원예 수업, 기업 화분 견적 문의.",
};

export default function OutreachPage() {
  return (
    <>
      <PageTop en="INQUIRY" title="견적 문의" sub="출강·단체·기업 프로그램에 대해 문의해 주세요." />
      <div className="wrap content">
        <InquiryForm workshops={WORKSHOPS.map((w) => ({ id: w.id, name: w.name }))} brochureUrl={SHOP.brochureUrl} />
      </div>
    </>
  );
}
