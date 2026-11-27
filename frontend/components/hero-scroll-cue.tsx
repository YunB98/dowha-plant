"use client";
/* 첫 화면 아래 "SCROLL" 버튼: 이번 주 식물로 내려간다 */
export function HeroScrollCue() {
  return (
    <button
      className="scroll-cue" type="button" aria-label="이번 주 식물 보기"
      onClick={() => {
        const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        document.getElementById("arrivals")?.scrollIntoView({ behavior: reduced ? "auto" : "smooth" });
      }}
    >
      <span className="mouse" />SCROLL<span>⌄</span>
    </button>
  );
}
