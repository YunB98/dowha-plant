/* 홈 (프로토타입 home()와 같은 마크업). 빌드할 때 HTML로 만들어진다. */
import Link from "next/link";

import { HeroScrollCue } from "@/components/hero-scroll-cue";
import { Empty, PlantCard, Section } from "@/components/ui";
import { getPlants } from "@/lib/content";
import { PURPOSES, weeklyPlants } from "@/lib/demo";

export default async function Home() {
  const list = weeklyPlants(await getPlants());
  return (
    <>
      <section className="hero">
        <div className="hero-copy">
          <h1>당신의 일상에,<br />꽃과 초록을 더하다.</h1>
        </div>
        <HeroScrollCue />
      </section>

      <Section en="NEW ARRIVALS" title="이번 주 들어온 식물" sub="매주 새롭게 만나는 도화의 초록." href="/plants/" linkLabel="전체 식물 보기" id="arrivals">
        <div className="grid four">
          {list.length ? list.map((p) => <PlantCard key={p.id} plant={p} />) : <Empty>새로운 식물을 준비하고 있어요.</Empty>}
        </div>
      </Section>

      <Section en="FIND YOUR GREEN" title="어떤 식물을 찾으세요?" sub="공간과 마음에 어울리는 식물을 골라보세요." alt>
        <div className="purpose-grid">
          {PURPOSES.map((t) => (
            <Link key={t} href={`/plants/?purpose=${encodeURIComponent(t)}`}>{t} <span>↗</span></Link>
          ))}
        </div>
      </Section>

      <section className="section">
        <div className="wrap split">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/assets/studio.webp" alt="도화 클래스 분위기 예시" loading="lazy" />
          <div className="copy">
            <div className="eyebrow">CLASS &amp; WORKSHOP</div>
            <h2>함께 만드는<br />초록의 시간</h2>
            <p className="sub">원데이 클래스부터 기관·기업 출강까지. 식물과 가까워지는 시간을 만들어 보세요.</p>
            <div className="button-row">
              <Link className="btn" href="/classes/">클래스·출강 보기</Link>
              <Link className="btn outline" href="/outreach/">견적 문의</Link>
            </div>
          </div>
        </div>
      </section>

      <section className="section alt">
        <div className="wrap split">
          <div className="copy">
            <div className="eyebrow">PLANT CARE</div>
            <h2>오래도록 함께하는<br />식물 관리 가이드</h2>
            <p className="sub">햇빛, 물, 온도. 식물마다 필요한 관리 방법을 쉽게 찾아보세요.</p>
            <Link className="btn outline" href="/guides/">관리 가이드 보기 ↗</Link>
          </div>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/assets/schefflera-2.webp" alt="식물 관리 가이드 예시" loading="lazy" />
        </div>
      </section>

      <section className="section">
        <div className="wrap split">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/assets/hero.webp" alt="매장 분위기 콘셉트 이미지" loading="lazy" />
          <div className="copy">
            <div className="eyebrow">VISIT DOHWA</div>
            <h2>전주 남부시장 청년몰,<br />도화입니다.</h2>
            <p className="sub">공간과 선물에 어울리는 식물을 함께 고르고 정성스럽게 준비해 드려요.</p>
            <Link className="arrow-link" href="/visit/">오시는 길 ↗</Link>
          </div>
        </div>
      </section>
    </>
  );
}
