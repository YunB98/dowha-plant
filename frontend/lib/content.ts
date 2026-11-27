/**
 * 페이지가 쓰는 내용 조회 (빌드할 때만 실행된다. 손님 브라우저는 API를 부르지 않는다).
 *
 * CONTENT_SOURCE=api  : 운영 API에서 받는다 (CI 빌드). 실패하면 빌드를 멈춘다 (빈 사이트 배포 방지)
 * 그 외(기본)          : lib/demo.ts 예시 데이터 (로컬 개발)
 * 식물은 블로그 식물 소개 글이다 (서버가 RSS로 가져온다, ADR 0027).
 *
 * API 응답(snake_case)을 화면용 타입(lib/demo.ts)으로 바꾸는 곳은 여기 한 곳이다.
 */
import {
  CASES, type Case, GUIDES, type Guide, type OrganizationType, PLANTS, type Plant, SHOP, type Shop,
  WORKSHOPS, type Workshop,
} from "@/lib/demo";

const USE_API = process.env.CONTENT_SOURCE === "api";
const BASE = (process.env.API_BASE_URL || "https://dowha-plant.shop").replace(/\/$/, "");

// 같은 빌드 안에서 같은 주소는 한 번만 부른다 (페이지 여러 개가 같은 목록을 쓴다)
const cache = new Map<string, Promise<unknown>>();

async function get<T>(path: string): Promise<T> {
  const url = `${BASE}/api/v1${path}`;
  if (!cache.has(url)) {
    cache.set(url, (async () => {
      for (let attempt = 1; ; attempt++) {
        try {
          // cache 옵션을 주지 않는다: "no-store"는 정적 내보내기를 막고, "force-cache"는 이전 빌드 값을 재사용한다
          const res = await fetch(url, { headers: { Accept: "application/json" } });
          if (res.ok) return res.json();
          if (res.status < 500 || attempt >= 3) throw new Error(`${res.status} ${res.statusText}`);
        } catch (e) {
          if (attempt >= 3) throw new Error(`API 조회 실패: ${url} (${(e as Error).message})`);
        }
        await new Promise((r) => setTimeout(r, attempt * 1000));
      }
    })());
  }
  return cache.get(url) as Promise<T>;
}

// ---------- API 응답 형태 (backend/app/public.py) ----------

type ApiImage = { id: number; image_url: string; alt_text: string };
type ApiStore = {
  contact: { phone: string | null; kakao_url: string | null; naver_talk_url: string | null; instagram: string | null };
  links: { smartstore_url: string | null; naver_place_url: string | null };
  store: { address: string | null; hours: string | null };
  outreach: { service_area: string | null; brochure_url: string | null };
};
type ApiWorkshop = {
  id: number; name: string; price_per_person: number; min_people: number; max_people: number;
  duration_min: number; duration_max: number; is_seasonal: boolean; supports_outreach: boolean;
  status: "open" | "closed"; thumbnail_url: string | null;
};
type ApiWorkshopDetail = ApiWorkshop & { description: string; images: ApiImage[] };
type ApiCase = {
  id: number; title: string; organization_type: OrganizationType; organization_display_name: string;
  held_on: string; participant_count: number | null; thumbnail_url: string | null;
};
type ApiCaseDetail = ApiCase & { summary: string; images: ApiImage[] };
type ApiPlant = {
  id: number; name: string; excerpt: string; thumbnail_url: string | null; purposes: string[];
  sale_status: Plant["saleStatus"]; price: number | null; size: string; published_at: string;
  blog_url: string; guide_slug: string | null;
};
type ApiGuide = { slug: string; name: string; difficulty: Guide["difficulty"]; summary: string; thumbnail_url: string | null };
type ApiGuideDetail = ApiGuide & {
  light: string; watering: string; temperature: string; humidity: string; seasonal_care: string; troubleshooting: string;
  images: ApiImage[];
};

// ---------- 가게 정보 ----------

export async function getShop(): Promise<Shop> {
  if (!USE_API) return SHOP;
  const s = await get<ApiStore>("/store");
  return {
    location: "전주 남부시장 청년몰",
    address: s.store.address ?? "",
    // 영업시간은 줄바꿈으로 여러 줄 ("화~목 12:00 ~ 19:00\n금~토 …")
    hours: (s.store.hours ?? "").split("\n").map((l) => l.trim()).filter(Boolean),
    phone: s.contact.phone ?? "",
    kakaoUrl: s.contact.kakao_url,
    naverTalkUrl: s.contact.naver_talk_url,
    instagram: s.contact.instagram ?? "",
    smartstoreUrl: s.links.smartstore_url,
    brochureUrl: s.outreach.brochure_url,
  };
}

// ---------- 클래스 ----------

const toWorkshop = (w: ApiWorkshop, description = "", image = w.thumbnail_url): Workshop => ({
  id: w.id, name: w.name, description, image,
  pricePerPerson: w.price_per_person, minPeople: w.min_people, maxPeople: w.max_people,
  durationMin: w.duration_min, durationMax: w.duration_max,
  isSeasonal: w.is_seasonal, supportsOutreach: w.supports_outreach, status: w.status,
});

export async function getWorkshops(): Promise<Workshop[]> {
  if (!USE_API) return WORKSHOPS;
  return (await get<ApiWorkshop[]>("/workshops")).map((w) => toWorkshop(w));
}

export async function getWorkshop(id: number): Promise<Workshop | undefined> {
  if (!USE_API) return WORKSHOPS.find((w) => w.id === id);
  const d = await get<ApiWorkshopDetail>(`/workshops/${id}`);
  return toWorkshop(d, d.description, d.images[0]?.image_url ?? d.thumbnail_url);
}

// ---------- 진행 사례 ----------

const toCase = (c: ApiCase, summary = "", image = c.thumbnail_url): Case => ({
  id: c.id, title: c.title, organizationType: c.organization_type, organizationDisplayName: c.organization_display_name,
  heldOn: c.held_on, participantCount: c.participant_count, summary, image,
});

export async function getCases(): Promise<Case[]> {
  if (!USE_API) return CASES;
  const all: Case[] = [];
  for (let page = 1; ; page++) { // 한 번에 50개까지라 끝까지 넘긴다
    const r = await get<{ items: ApiCase[]; total: number }>(`/cases?page=${page}&size=50`);
    all.push(...r.items.map((c) => toCase(c)));
    if (all.length >= r.total || r.items.length === 0) return all;
  }
}

export async function getCase(id: number): Promise<Case | undefined> {
  if (!USE_API) return CASES.find((c) => c.id === id);
  const d = await get<ApiCaseDetail>(`/cases/${id}`);
  return toCase(d, d.summary, d.images[0]?.image_url ?? d.thumbnail_url);
}

// ---------- 식물 관리 가이드 ----------

export type GuideListItem = Pick<Guide, "slug" | "name" | "image" | "difficulty"> & { note: string };

export async function getGuides(): Promise<GuideListItem[]> {
  if (!USE_API) return GUIDES.map((g) => ({ slug: g.slug, name: g.name, image: g.image, difficulty: g.difficulty, note: g.light }));
  return (await get<ApiGuide[]>("/guides")).map((g) => ({
    slug: g.slug, name: g.name, image: g.thumbnail_url, difficulty: g.difficulty, note: g.summary,
  }));
}

export async function getGuide(slug: string): Promise<Guide | undefined> {
  if (!USE_API) return GUIDES.find((g) => g.slug === slug);
  const d = await get<ApiGuideDetail>(`/guides/${encodeURIComponent(slug)}`);
  return {
    slug: d.slug, name: d.name, image: d.images[0]?.image_url ?? d.thumbnail_url, difficulty: d.difficulty,
    light: d.light, watering: d.watering, temperature: d.temperature, humidity: d.humidity,
    seasonalCare: d.seasonal_care, troubleshooting: d.troubleshooting,
  };
}

// ---------- 식물 (블로그 식물 소개 글, ADR 0027) ----------

export async function getPlants(): Promise<Plant[]> {
  if (!USE_API) return PLANTS;
  return (await get<ApiPlant[]>("/plants")).map((p) => ({
    id: String(p.id), name: p.name, image: p.thumbnail_url, summary: p.excerpt,
    saleStatus: p.sale_status, price: p.price, size: p.size, purposes: p.purposes,
    guideSlug: p.guide_slug, publishedAt: p.published_at, blogUrl: p.blog_url,
  }));
}

/** 목록이 비면 상세 페이지 묶음이 0개가 되는데, 정적 내보내기는 0개를 허용하지 않는다.
 *  이 자리표시 주소는 404 화면으로 만들어진다 (dynamicParams = false라 다른 주소는 생기지 않는다) */
export const PLACEHOLDER = "_";
export const staticParams = <K extends string>(key: K, values: string[]) =>
  (values.length ? values : [PLACEHOLDER]).map((v) => ({ [key]: v }) as Record<K, string>);
