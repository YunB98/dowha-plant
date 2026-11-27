"use client";
/* 프로토타입 setupMotion(), updateMotionScroll(), onScroll()의 움직임.
   - 첫 화면(hero) 등장, 화면 아래쪽 요소는 스크롤해서 보일 때 나타남
   - 움직임 줄이기 설정을 켠 사람에게는 아무것도 하지 않는다
   - IntersectionObserver가 없으면 숨기지 않는다 (내용이 안 보이는 일이 없게) */
import { usePathname } from "next/navigation";
import { useEffect } from "react";

const reduced = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

export function Motion() {
  const path = usePathname();

  useEffect(() => {
    let frame = 0;
    const update = () => {
      frame = 0;
      const hero = document.querySelector<HTMLElement>(".hero");
      const head = document.querySelector<HTMLElement>(".site-header");
      if (head) {
        const max = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
        head.style.setProperty("--reading-progress", String(Math.min(1, Math.max(0, window.scrollY / max))));
      }
      if (hero && !reduced()) {
        const ratio = Math.min(1, Math.max(0, window.scrollY / Math.max(1, hero.offsetHeight)));
        hero.style.setProperty("--hero-travel", `${Math.round(ratio * 26)}px`);
        hero.style.setProperty("--hero-opacity", String(1 - ratio * 0.75));
      }
      // 휴대폰 하단 상담 바는 첫 화면 사진 위에서는 숨긴다
      document.body.classList.toggle("hero-at-top", !!hero && window.scrollY < Math.max(80, (hero?.offsetHeight || 0) - 150));
    };
    const onScroll = () => { if (!frame) frame = requestAnimationFrame(update); };
    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      if (frame) cancelAnimationFrame(frame);
    };
  }, [path]);

  useEffect(() => {
    const main = document.getElementById("main");
    if (!main || reduced()) return;
    const hero = main.querySelector(".hero");
    (hero ?? main).classList.add(hero ? "hero-enter" : "page-enter");
    if (!("IntersectionObserver" in window)) return;
    const io = new IntersectionObserver((entries) => {
      for (const e of entries) if (e.isIntersecting) { e.target.classList.add("is-revealed"); io.unobserve(e.target); }
    }, { threshold: 0.1 });
    main.querySelectorAll<HTMLElement>(".section .section-head,.section .plant-card,.section .purpose-grid,.section .split>img,.section .split>.copy")
      .forEach((el, i) => {
        if (el.getBoundingClientRect().top < window.innerHeight * 0.95) return; // 이미 보이는 것은 그대로
        el.style.setProperty("--reveal-delay", `${Math.min(i % 4, 3) * 55}ms`);
        el.classList.add("motion-reveal");
        io.observe(el);
      });
    return () => io.disconnect();
  }, [path]);

  return null;
}
