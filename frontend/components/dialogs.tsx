"use client";
/* 상담 창과 검색 창 (프로토타입 contact(), search(), showModal()).
   <dialog> 하나를 같이 쓰고, 여는 함수는 context로 헤더·하단 바·상세 페이지 버튼에 준다. */
import Link from "next/link";
import { createContext, type ReactNode, useCallback, useContext, useEffect, useRef, useState } from "react";

import { PLANTS, type Shop } from "@/lib/demo";

type Kind = "contact" | "search" | null;
const DialogContext = createContext<{ open: (k: Exclude<Kind, null>) => void; shop: Shop | null }>({ open: () => {}, shop: null });
export const useDialogs = () => useContext(DialogContext);

const ICON = {
  phone: <svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M22 16.9v3a2 2 0 0 1-2.2 2 19 19 0 0 1-8.3-3 19 19 0 0 1-6-6 19 19 0 0 1-3.1-8.3A2 2 0 0 1 4.4 2h3a2 2 0 0 1 2 1.7l.7 3.4a2 2 0 0 1-.6 2l-1.3 1.3a15 15 0 0 0 5.4 5.4l1.3-1.3a2 2 0 0 1 2-.6l3.4.7a2 2 0 0 1 1.7 2.3Z" /></svg>,
  quote: <svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M7 3h7l5 5v12a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z" /><path d="M14 3v6h5M9 13h7m-7 4h7" /></svg>,
  store: <svg viewBox="0 0 24 24" aria-hidden="true" fill="currentColor"><path d="M16.273 12.845 7.376 0H0v24h7.726V11.156L16.624 24H24V0h-7.727v12.845Z" /></svg>,
};

type Channel = { key: string; title: string; sub: string; href: string | null; icon: ReactNode; internal?: boolean };

function channels(shop: Shop, includeStore: boolean): Channel[] {
  // eslint-disable-next-line @next/next/no-img-element
  const img = (k: string) => <img className="official-channel-icon" src={`/assets/contact-${k}.jpg`} alt="" width={46} height={46} />;
  const list: Channel[] = [
    { key: "kakao", title: "카카오톡 상담", sub: "카카오톡으로 편하게 문의", href: shop.kakaoUrl, icon: img("kakao") },
    { key: "talk", title: "네이버 톡톡", sub: "네이버에서 1:1 상담", href: shop.naverTalkUrl, icon: img("talk") },
    { key: "store", title: "스마트스토어", sub: "도화의 상품 둘러보기", href: shop.smartstoreUrl, icon: ICON.store },
    { key: "phone", title: "전화 상담", sub: shop.phone, href: shop.phone ? `tel:${shop.phone.replace(/[^\d+]/g, "")}` : null, icon: ICON.phone },
    { key: "instagram", title: "인스타그램", sub: "도화의 소식과 DM", href: shop.instagram ? `https://www.instagram.com/${shop.instagram}/` : null, icon: img("instagram") },
    { key: "quote", title: "출강·단체 견적 문의", sub: "기관·기업 프로그램 문의", href: "/outreach/", icon: ICON.quote, internal: true },
  ];
  // 상담 창에는 스마트스토어를 넣지 않는다 (프로토타입 contact()와 같다). 링크 모음에만
  return includeStore ? list : list.filter((c) => c.key !== "store");
}

export function ChannelRow({ c, onNavigate }: { c: Channel; onNavigate?: () => void }) {
  const inner = (
    <>
      <span className={`channel-icon channel-${c.key}`}>{c.icon}</span>
      <span className="channel-copy"><strong>{c.title}</strong><small>{c.href ? c.sub : "준비 중이에요"}</small></span>
      <span className="channel-arrow" aria-hidden="true">↗</span>
    </>
  );
  if (!c.href) return <div className="channel-row" aria-disabled="true">{inner}</div>;
  if (c.internal) return <Link className="channel-row" href={c.href} onClick={onNavigate}>{inner}</Link>;
  const external = c.href.startsWith("http");
  return <a className="channel-row" href={c.href} {...(external ? { target: "_blank", rel: "noopener" } : {})}>{inner}</a>;
}

export function ContactLinks({ onNavigate, includeStore = false }: { onNavigate?: () => void; includeStore?: boolean }) {
  const { shop } = useDialogs();
  if (!shop) return null;
  return <div className="contact-links branded-contact">{channels(shop, includeStore).map((c) => <ChannelRow key={c.key} c={c} onNavigate={onNavigate} />)}</div>;
}

function SearchBody({ close }: { close: () => void }) {
  const [q, setQ] = useState("");
  const query = q.trim().toLowerCase();
  const results = query ? PLANTS.filter((p) => p.name.toLowerCase().includes(query)) : [];
  return (
    <>
      <div className="field">
        <label htmlFor="site-search">식물 · 관리 가이드 · 클래스</label>
        <input id="site-search" type="search" placeholder="검색어 입력" value={q} onChange={(e) => setQ(e.target.value)} autoFocus />
      </div>
      <div className="search-results">
        {!query ? <p className="hint">검색어를 입력해 주세요.</p>
          : results.length ? results.map((p) => <Link key={p.id} href={`/plants/${p.id}/`} onClick={close}>{p.name} <span className="hint">식물</span></Link>)
          : <div className="empty">검색 결과가 없습니다.</div>}
      </div>
    </>
  );
}

export function DialogProvider({ shop, children }: { shop: Shop; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null);
  const [kind, setKind] = useState<Kind>(null);

  const open = useCallback((k: Exclude<Kind, null>) => setKind(k), []);
  const close = useCallback(() => ref.current?.close(), []);

  useEffect(() => {
    const d = ref.current;
    if (!d || !kind) return;
    if (!d.open) d.showModal();
    document.body.classList.add("dialog-open");
    d.scrollTop = 0;
  }, [kind]);

  return (
    <DialogContext.Provider value={{ open, shop }}>
      {children}
      <dialog
        id="modal"
        ref={ref}
        onClose={() => { document.body.classList.remove("dialog-open"); setKind(null); }}
        onClick={(e) => { // 바깥(배경)을 누르면 닫는다
          const d = ref.current;
          if (!d || e.target !== d) return;
          const r = d.getBoundingClientRect();
          if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) d.close();
        }}
      >
        {kind ? (
          <>
            <div className="modal-head">
              <h2 style={{ fontSize: 23 }}>{kind === "contact" ? "도화에 문의하기" : "무엇을 찾으시나요?"}</h2>
              <button className="icon-btn" type="button" onClick={close} aria-label="닫기">×</button>
            </div>
            {kind === "contact" ? (
              <>
                <p className="contact-intro">편하신 방법으로 도화와 이야기를 나눠보세요.</p>
                <ContactLinks onNavigate={close} />
              </>
            ) : <SearchBody close={close} />}
          </>
        ) : null}
      </dialog>
    </DialogContext.Provider>
  );
}

export function ContactButton({ className, children }: { className: string; children: ReactNode }) {
  const { open } = useDialogs();
  return <button type="button" className={className} onClick={() => open("contact")}>{children}</button>;
}
