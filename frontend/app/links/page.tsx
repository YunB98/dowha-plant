/* 링크 모음 (프로토타입 links()). 인스타그램 프로필에 거는 한 화면 */
import type { Metadata } from "next";

import { ContactLinks } from "@/components/dialogs";
import { PageTop } from "@/components/ui";

export const metadata: Metadata = { title: "도화와 연결하기", description: "카카오톡, 네이버 톡톡, 전화, 인스타그램, 출강·단체 견적 문의." };

export default function LinksPage() {
  return (
    <>
      <PageTop en="DOHWA" title="도화와 연결하기" />
      <div className="wrap content">
        <div className="form-card">
          <ContactLinks includeStore />
        </div>
      </div>
    </>
  );
}
