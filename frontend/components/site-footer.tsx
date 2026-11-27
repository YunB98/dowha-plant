/* 프로토타입 footer() + 휴대폰 하단 상담 바(.mobile-contact) */
import Link from "next/link";

import { ContactButton } from "@/components/dialogs";
import { Logo } from "@/components/site-header";
import type { Shop } from "@/lib/demo";

export function SiteFooter({ shop }: { shop: Shop }) {
  const lines = [shop.address, ...shop.hours, shop.phone].filter(Boolean); // 비어 있는 값은 숨긴다
  return (
    <>
      <footer className="footer">
        <div className="wrap">
          <div className="footer-grid">
            <div>
              <Logo />
              <p className="sub">{shop.location} · 식물가게</p>
              {lines.length ? <p className="sub">{lines.map((l, i) => <span key={l}>{i ? <br /> : null}{l}</span>)}</p> : null}
            </div>
            <div className="foot-links">
              <Link href="/plants/">식물</Link>
              <Link href="/classes/">클래스·출강</Link>
              <Link href="/outreach/">견적 문의</Link>
              <Link href="/links/">링크 모음</Link>
              <Link href="/visit/">오시는 길</Link>
            </div>
          </div>
          <div className="foot-bottom">
            <span>© DOHWA</span>
            {shop.instagram ? <a href={`https://www.instagram.com/${shop.instagram}/`} target="_blank" rel="noopener">@{shop.instagram}</a> : null}
          </div>
        </div>
      </footer>
      <div className="mobile-contact">
        <ContactButton className="btn">식물 상담</ContactButton>
        <Link href="/outreach/" className="btn outline">출강 문의</Link>
      </div>
    </>
  );
}
