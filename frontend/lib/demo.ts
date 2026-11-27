/**
 * 예시 데이터 (사장님 쪽 프로토타입 data.js에서 옮김, ADR 0028).
 * 필드 이름은 백엔드 API 응답에 맞춰 두었다. 페이지마다 빌드 시 API 조회로 바꾼다 (lib/api.ts 예정).
 * 사진은 프로토타입의 예시 이미지이며 출시 전에 실제 사진으로 바꾼다.
 */

export type SaleStatus = "available" | "reserved" | "sold";

export type Plant = {
  id: string;
  name: string;
  image: string; // /assets/… 또는 CloudFront image_url
  summary: string;
  saleStatus: SaleStatus | null; // null: 소개 글 (배지 없음)
  price: number | null; // null: "상담 후 안내"
  size: string; // 자유 입력 ("약 55cm"), 빈 문자열이면 숨김
  purposes: string[];
  guideSlug: string | null;
  publishedAt: string; // YYYY-MM-DD
  blogUrl: string | null;
};

export type Shop = {
  location: string;
  address: string;
  hours: string[];
  phone: string;
  kakaoUrl: string | null;
  naverTalkUrl: string | null;
  instagram: string;
  smartstoreUrl: string | null;
  brochureUrl: string | null;
};

export const PURPOSES = [
  "개업·승진 선물",
  "집들이 선물",
  "거실·매장 인테리어",
  "키우기 쉬운 식물",
  "꽃이 피는 식물",
  "단체 답례품",
] as const;

export const SALE_LABEL: Record<SaleStatus, string> = {
  available: "판매 중",
  reserved: "예약 중",
  sold: "판매 완료",
};

// 가게 정보는 블로그·요구사항에 공개된 값. 운영에서는 /api/v1/store 응답으로 바뀐다
export const SHOP: Shop = {
  location: "전주 남부시장 청년몰",
  address: "전주시 완산구 풍남문2길 53 남부시장 2층 청년몰",
  hours: ["화~목 12:00 ~ 19:00", "금~토 12:00 ~ 20:00", "일 11:00 ~ 15:00", "월요일 휴무"],
  phone: "0507-1358-4480",
  kakaoUrl: null,
  naverTalkUrl: "https://naver.me/Gpl6QyeP",
  instagram: "dowha_plantshop",
  smartstoreUrl: null,
  brochureUrl: null,
};

export const PLANTS: Plant[] = [
  { id: "schefflera", name: "무늬 홍콩야자", image: "/assets/schefflera.webp", summary: "자연스럽게 뻗은 가지와 잎의 무늬가 공간에 편안한 분위기를 더해요.", saleStatus: "available", price: 65000, size: "약 55cm", purposes: ["집들이 선물", "거실·매장 인테리어"], guideSlug: "schefflera", publishedAt: "2026-11-26", blogUrl: null },
  { id: "monstera", name: "몬스테라", image: "/assets/monstera.webp", summary: "넓은 초록 잎이 매력적인 실내 식물. 밝은 간접광에서 건강하게 자라요.", saleStatus: "available", price: 45000, size: "약 40cm", purposes: ["거실·매장 인테리어", "키우기 쉬운 식물"], guideSlug: "monstera", publishedAt: "2026-11-25", blogUrl: null },
  { id: "schefflera-large", name: "홍콩야자 · 도자기 화분", image: "/assets/schefflera-2.webp", summary: "부드러운 질감의 화분과 풍성한 초록이 어우러진 구성입니다.", saleStatus: "reserved", price: null, size: "", purposes: ["개업·승진 선물", "집들이 선물"], guideSlug: "schefflera", publishedAt: "2026-11-24", blogUrl: null },
  { id: "season-flower", name: "계절 꽃", image: "/assets/flowers.webp", summary: "계절에 어울리는 꽃을 소개합니다. 실제 구성은 상담을 통해 안내해요.", saleStatus: "sold", price: null, size: "", purposes: ["꽃이 피는 식물", "집들이 선물"], guideSlug: null, publishedAt: "2026-11-22", blogUrl: null },
  { id: "green-gift", name: "식물 선물 구성", image: "/assets/gift.webp", summary: "소중한 마음을 전하기 위한 선물 구성입니다.", saleStatus: "available", price: null, size: "", purposes: ["단체 답례품", "개업·승진 선물"], guideSlug: null, publishedAt: "2026-11-21", blogUrl: null },
  { id: "green-selection", name: "실내 식물 셀렉션", image: "/assets/plants.webp", summary: "공간의 밝기와 크기에 맞춰 식물을 함께 골라요.", saleStatus: "available", price: null, size: "", purposes: ["키우기 쉬운 식물", "거실·매장 인테리어"], guideSlug: null, publishedAt: "2026-11-20", blogUrl: null },
];

// ---------- 클래스 (API /api/v1/workshops) ----------

export type Workshop = {
  id: number;
  name: string;
  description: string;
  image: string | null;
  pricePerPerson: number | null; // null: 협의 (단체 프로그램)
  minPeople: number;
  maxPeople: number;
  durationMin: number;
  durationMax: number;
  isSeasonal: boolean;
  supportsOutreach: boolean;
  status: "open" | "closed";
};

export const WORKSHOP_STATUS_LABEL = { open: "모집 중", closed: "지금은 모집 안 함" } as const;

export const WORKSHOPS: Workshop[] = [
  { id: 1, name: "화분 꾸미기 & 가드닝", description: "식물과 화분을 고르고 직접 분갈이하는 원데이 클래스.", image: "/assets/schefflera-2.webp", pricePerPerson: 30000, minPeople: 1, maxPeople: 4, durationMin: 60, durationMax: 90, isSeasonal: false, supportsOutreach: true, status: "open" },
  { id: 2, name: "수형 잡기", description: "가지를 다듬어 식물의 모양을 잡는 방법을 배워요.", image: "/assets/schefflera.webp", pricePerPerson: 35000, minPeople: 1, maxPeople: 4, durationMin: 60, durationMax: 90, isSeasonal: false, supportsOutreach: true, status: "open" },
  { id: 3, name: "크리스마스 생화 리스", description: "생화와 초록으로 크리스마스 리스를 만들어요.", image: "/assets/flowers.webp", pricePerPerson: 40000, minPeople: 1, maxPeople: 4, durationMin: 90, durationMax: 120, isSeasonal: true, supportsOutreach: true, status: "open" },
];

export const range = (a: number, b: number, unit: string) => (a === b ? `${a}${unit}` : `${a}~${b}${unit}`);

// ---------- 진행 사례 (API /api/v1/cases) ----------

export type OrganizationType = "school" | "kindergarten" | "welfare" | "public" | "company" | "other";

export const ORGANIZATION_LABEL: Record<OrganizationType, string> = {
  school: "학교",
  kindergarten: "어린이집·유치원",
  welfare: "복지관",
  public: "공공기관",
  company: "기업",
  other: "기타",
};

export type Case = {
  id: number;
  title: string;
  organizationType: OrganizationType;
  organizationDisplayName: string;
  heldOn: string; // YYYY-MM-DD
  participantCount: number | null;
  summary: string;
  image: string | null;
};

export const CASES: Case[] = [
  { id: 1, title: "학교 단체 원예 수업", organizationType: "school", organizationDisplayName: "전주 ○○초등학교", heldOn: "2026-11-18", participantCount: 20, summary: "함께 식물을 심고 돌보는 시간을 가진 수업 예시입니다.", image: "/assets/plants.webp" },
  { id: 2, title: "복지관 반려식물 프로그램", organizationType: "welfare", organizationDisplayName: "완주 ○○복지관", heldOn: "2026-11-12", participantCount: 12, summary: "식물을 매개로 함께 이야기를 나누는 프로그램 예시입니다.", image: "/assets/studio.webp" },
];

// ---------- 식물 관리 가이드 (API /api/v1/guides) ----------

export type Guide = {
  slug: string;
  name: string;
  image: string | null;
  difficulty: "easy" | "normal" | "hard";
  light: string;
  watering: string;
  temperature: string;
  humidity: string;
  seasonalCare: string;
  troubleshooting: string;
};

export const DIFFICULTY_LABEL = { easy: "쉬움", normal: "보통", hard: "어려움" } as const;

export const GUIDES: Guide[] = [
  { slug: "schefflera", name: "홍콩야자", image: "/assets/schefflera.webp", difficulty: "easy", light: "밝은 간접광", watering: "겉흙이 마르면 충분히 주세요.", temperature: "18~26℃", humidity: "통풍이 되는 실내", seasonalCare: "겨울에는 물 주는 횟수를 줄이세요.", troubleshooting: "잎이 노랗게 변하면 과습과 빛을 확인하세요." },
  { slug: "monstera", name: "몬스테라", image: "/assets/monstera.webp", difficulty: "easy", light: "밝은 간접광", watering: "겉흙이 마르면 화분 아래로 물이 흐를 만큼 주세요.", temperature: "18~28℃", humidity: "보통~높음", seasonalCare: "추운 창가와 냉난방기 바람을 피하세요.", troubleshooting: "잎 끝이 마르면 물과 습도 상태를 확인하세요." },
];

/** 홈 "이번 주 들어온 식물": 최신순, 판매 중 먼저, 4개 (프로토타입 home()과 같은 규칙) */
export function weeklyPlants(plants: Plant[] = PLANTS, count = 4): Plant[] {
  return [...plants]
    .sort((a, b) => b.publishedAt.localeCompare(a.publishedAt))
    .sort((a, b) => Number(a.saleStatus !== "available") - Number(b.saleStatus !== "available"))
    .slice(0, count);
}
