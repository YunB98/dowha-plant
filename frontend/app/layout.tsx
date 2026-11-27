import "pretendard/dist/web/variable/pretendardvariable-dynamic-subset.css";
import "./dohwa.css";
import "./site.css";

import type { Metadata, Viewport } from "next";
import { Noto_Serif_KR } from "next/font/google";
import type { ReactNode } from "react";

import { DialogProvider } from "@/components/dialogs";
import { Motion } from "@/components/motion";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import { IS_PREVIEW } from "@/lib/format";

// 프로토타입이 지정한 명조(--serif). 빌드할 때 받아 사이트에 같이 올린다 (preload 없이 필요할 때만)
const serif = Noto_Serif_KR({ weight: ["400", "600"], display: "swap", preload: false, variable: "--font-serif-kr" });

export const metadata: Metadata = {
  metadataBase: new URL("https://dowha-plant.shop"),
  title: { default: "도화 | 식물가게", template: "%s | 도화 식물가게" },
  description: "전주 남부시장 청년몰 식물가게 도화. 식물 소개, 클래스와 출강, 식물 관리 가이드.",
  // 출시 전에는 검색엔진에 올리지 않는다 (예시 사진·내용이 검색에 남지 않게)
  robots: IS_PREVIEW ? { index: false, follow: false } : undefined,
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#20291e",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ko" className={serif.variable}>
      <body>
        <a className="skip" href="#main">본문 바로가기</a>
        <DialogProvider>
          <SiteHeader />
          <main id="main" tabIndex={-1}>{children}</main>
          <SiteFooter />
        </DialogProvider>
        <Motion />
        {IS_PREVIEW ? (
          <div className="preview-bar" role="note">사이트를 준비하고 있어요 · 사진과 내용은 예시예요</div>
        ) : null}
      </body>
    </html>
  );
}
