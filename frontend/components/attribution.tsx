"use client";
/* 첫 방문 경로 기록 (요구사항 "어디서 왔는지 파악"). 문의를 보낼 때 같이 보낸다.
   한 번 기록하면 같은 탭에서는 덮어쓰지 않는다 (사이트 안에서 이동해도 처음 경로가 남게). 개인 식별 정보는 없다 */
import { useEffect } from "react";

const KEY = "dowha-attribution";

export type Attribution = {
  landing_referrer?: string;
  utm_source?: string;
  utm_medium?: string;
  utm_campaign?: string;
};

export function readAttribution(): Attribution | undefined {
  try {
    const v = sessionStorage.getItem(KEY);
    return v ? (JSON.parse(v) as Attribution) : undefined;
  } catch {
    return undefined;
  }
}

export function AttributionCapture() {
  useEffect(() => {
    try {
      if (sessionStorage.getItem(KEY)) return;
      const q = new URLSearchParams(location.search);
      const ref = document.referrer && !document.referrer.startsWith(location.origin) ? document.referrer : "";
      const a: Attribution = {
        landing_referrer: ref.slice(0, 500) || undefined,
        utm_source: q.get("utm_source")?.slice(0, 100) || undefined,
        utm_medium: q.get("utm_medium")?.slice(0, 100) || undefined,
        utm_campaign: q.get("utm_campaign")?.slice(0, 100) || undefined,
      };
      sessionStorage.setItem(KEY, JSON.stringify(a));
    } catch {
      // 저장소를 막은 브라우저: 기록 없이 진행
    }
  }, []);
  return null;
}
