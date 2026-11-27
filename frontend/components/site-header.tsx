"use client";
/* 프로토타입 header(): 홈에서는 사진 위 투명 헤더, 스크롤하면 불투명. 휴대폰은 메뉴 버튼. */
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { useDialogs } from "@/components/dialogs";

const NAV: [string, string][] = [
  ["/", "홈"],
  ["/plants/", "식물"],
  ["/classes/", "클래스·출강"],
  ["/guides/", "관리 가이드"],
  ["/visit/", "오시는 길"],
];

const Icon = {
  search: <svg viewBox="0 0 24 24"><circle cx="10.5" cy="10.5" r="7.5" /><path d="m16 16 5 5" /></svg>,
  menu: <svg viewBox="0 0 24 24"><path d="M3 6h18M3 12h18M3 18h18" /></svg>,
  close: <svg viewBox="0 0 24 24"><path d="m5 5 14 14M19 5 5 19" /></svg>,
};

export function Logo() {
  return (
    <Link className="logo" href="/" aria-label="도화 홈">
      <strong>도화</strong>
      <small>DOHWA<br />BOTANICAL STUDIO</small>
    </Link>
  );
}

export function SiteHeader() {
  const path = usePathname() || "/";
  const isHome = path === "/";
  const { open } = useDialogs();
  const [menuOpen, setMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => setMenuOpen(false), [path]);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 65);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => { // Esc로 휴대폰 메뉴 닫기
    if (!menuOpen) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setMenuOpen(false);
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [menuOpen]);

  const active = (url: string) => (url === "/" ? path === "/" : path.startsWith(url));

  return (
    <header className={`site-header${isHome ? " home" : ""}${isHome && scrolled ? " scrolled" : ""}`}>
      <div className="header-inner">
        <Logo />
        <nav className={`nav${menuOpen ? " open" : ""}`} aria-label="메인 메뉴">
          {NAV.map(([url, label]) => (
            <Link key={url} href={url} className={active(url) ? "active" : undefined} aria-current={active(url) ? "page" : undefined}>{label}</Link>
          ))}
        </nav>
        <div className="head-actions">
          <button className="icon-btn" type="button" aria-label="검색" onClick={() => open("search")}>{Icon.search}</button>
          <button className="head-contact" type="button" onClick={() => open("contact")}>상담하기</button>
          <button
            className="icon-btn mobile-toggle" type="button"
            aria-label={menuOpen ? "메뉴 닫기" : "메뉴 열기"} aria-expanded={menuOpen}
            onClick={() => setMenuOpen((v) => !v)}
          >
            {menuOpen ? Icon.close : Icon.menu}
          </button>
        </div>
      </div>
    </header>
  );
}
