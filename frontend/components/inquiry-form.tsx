"use client";
/* 견적 문의 폼. 디자인은 프로토타입 quote()(form-card, form-grid, field), 항목과 검증은 서버 API 기준
   (backend/app/inquiries.py, docs/api-spec.md "문의 접수", 디자인 전달서 8번).
   - 접수되면 사장님 텔레그램으로 알림이 간다
   - 서버가 돌려준 칸별 오류는 그 칸 아래에 보여 준다
   - 같은 곳에서 연속 접수는 서버(Nginx)가 막는다 (429) */
import Link from "next/link";
import { type FormEvent, type ReactNode, useState } from "react";

import { readAttribution } from "@/components/attribution";
import { ORGANIZATION_LABEL } from "@/lib/demo";

const TYPES = [["outreach", "출강"], ["group_visit", "매장 단체 수업"], ["corporate_order", "기업 대량 화분"], ["other", "기타"]] as const;
const AUDIENCES = [["children", "어린이"], ["teens", "청소년"], ["adults", "성인"], ["seniors", "어르신"], ["mixed", "여러 연령"]] as const;
const SOURCES = [["search", "검색"], ["instagram", "인스타그램"], ["qr", "QR 카드"], ["referral", "소개"], ["returning", "이용해 본 적 있음"], ["other", "기타"]] as const;
const PHONE_RE = /^0\d{1,2}[-\s]?\d{3,4}[-\s]?\d{4}$/;

type Errors = Record<string, string>;
type State = "idle" | "sending" | "done";

function Field({ id, label, required, error, children, full }: {
  id: string; label: string; required?: boolean; error?: string; children: ReactNode; full?: boolean;
}) {
  const body = (
    <div className="field">
      <label htmlFor={`f-${id}`}>{label}{required ? " *" : ""}</label>
      {children}
      {error ? <p className="field-error" id={`f-${id}-error`} role="alert">{error}</p> : null}
    </div>
  );
  return full ? <div className="full">{body}</div> : body;
}

export function InquiryForm({ workshops, brochureUrl }: { workshops: { id: number; name: string }[]; brochureUrl: string | null }) {
  const [state, setState] = useState<State>("idle");
  const [type, setType] = useState<string>("outreach");
  const [errors, setErrors] = useState<Errors>({});
  const [message, setMessage] = useState("");
  const [note, setNote] = useState("");

  const err = (name: string) => errors[name];
  const a11y = (name: string) => (errors[name] ? { "aria-invalid": true, "aria-describedby": `f-${name}-error` } : {});

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const v = (k: string) => String(f.get(k) ?? "").trim();
    const local: Errors = {};
    if (!PHONE_RE.test(v("phone"))) local.phone = "연락처 형식이 올바르지 않아요. 예: 010-1234-5678";
    if (type === "outreach" && !v("location")) local.location = "출강 문의는 수업 장소를 입력해주세요.";
    setErrors(local);
    if (Object.keys(local).length) { setNote("입력값을 확인해주세요."); return; }

    const opt = (k: string) => v(k) || undefined;
    const payload = {
      type,
      organization_name: v("organization_name"),
      organization_type: v("organization_type"),
      contact_name: v("contact_name"),
      phone: v("phone"),
      email: opt("email"),
      people_count: Number(v("people_count")),
      audience: opt("audience"),
      preferred_schedule: v("preferred_schedule"),
      location: type === "outreach" ? v("location") : opt("location"),
      workshop_id: v("workshop_id") ? Number(v("workshop_id")) : undefined,
      budget_range: opt("budget_range"),
      source: v("source"),
      attribution: readAttribution(),
      message,
      privacy_agreed: f.get("privacy_agreed") === "on",
      website: v("website"), // 허니팟: 사람은 비워 둔다
    };

    setState("sending");
    setNote("");
    try {
      const res = await fetch("/api/v1/inquiries", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (res.status === 201) { setState("done"); window.scrollTo({ top: 0 }); return; }
      const body = await res.json().catch(() => null);
      const server: Errors = {};
      for (const d of body?.error?.details ?? []) {
        const name = String(d.field).split(".").pop() ?? "body";
        server[name === "body" ? "_" : name] = d.message;
      }
      setErrors(server);
      setNote(server._ ?? body?.error?.message ?? "접수하지 못했어요. 잠시 후 다시 시도해주세요.");
    } catch {
      setNote("인터넷 연결을 확인하고 다시 시도해주세요. 계속 안 되면 전화나 카카오톡으로 문의해 주세요.");
    }
    setState("idle");
  }

  if (state === "done") {
    return (
      <div className="form-card">
        <div className="error-page" style={{ padding: "30px 0" }}>
          <h2>문의가 접수되었어요.</h2>
          <p>내용을 확인하고 남겨 주신 연락처로 연락드릴게요.</p>
          <Link className="btn" href="/">홈으로</Link>
        </div>
      </div>
    );
  }

  return (
    <form id="quote-form" className="form-card" onSubmit={submit} noValidate={false}>
      <div className="form-grid">
        <Field id="type" label="문의 유형" required>
          <select id="f-type" name="type" required value={type} onChange={(e) => setType(e.target.value)}>
            {TYPES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </Field>
        <Field id="organization_type" label="기관 종류" required error={err("organization_type")}>
          <select id="f-organization_type" name="organization_type" required defaultValue="" {...a11y("organization_type")}>
            <option value="" disabled>선택해 주세요</option>
            {Object.entries(ORGANIZATION_LABEL).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </Field>
        <Field id="organization_name" label="기관·기업명" required error={err("organization_name")}>
          <input id="f-organization_name" name="organization_name" required maxLength={100} {...a11y("organization_name")} />
        </Field>
        <Field id="contact_name" label="담당자 이름" required error={err("contact_name")}>
          <input id="f-contact_name" name="contact_name" required maxLength={50} autoComplete="name" {...a11y("contact_name")} />
        </Field>
        <Field id="phone" label="전화번호" required error={err("phone")}>
          <input id="f-phone" name="phone" type="tel" required maxLength={20} autoComplete="tel" placeholder="010-1234-5678" {...a11y("phone")} />
        </Field>
        <Field id="email" label="이메일" error={err("email")}>
          <input id="f-email" name="email" type="email" maxLength={255} autoComplete="email" {...a11y("email")} />
        </Field>
        <Field id="people_count" label="참여 인원" required error={err("people_count")}>
          <input id="f-people_count" name="people_count" type="number" inputMode="numeric" min={1} max={1000} required {...a11y("people_count")} />
        </Field>
        <Field id="audience" label="대상">
          <select id="f-audience" name="audience" defaultValue="">
            <option value="">선택 안 함</option>
            {AUDIENCES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </Field>
        <Field id="preferred_schedule" label="희망 일정" required error={err("preferred_schedule")} full>
          <input id="f-preferred_schedule" name="preferred_schedule" required maxLength={200} placeholder="예: 12월 둘째 주 평일 오전" {...a11y("preferred_schedule")} />
        </Field>
        {type === "outreach" ? (
          <Field id="location" label="수업 장소" required error={err("location")} full>
            <input id="f-location" name="location" required maxLength={200} placeholder="예: 전주 ○○초등학교 강당" {...a11y("location")} />
          </Field>
        ) : null}
        <Field id="workshop_id" label="관심 클래스" error={err("workshop_id")}>
          <select id="f-workshop_id" name="workshop_id" defaultValue="" {...a11y("workshop_id")}>
            <option value="">정하지 않았어요</option>
            {workshops.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
          </select>
        </Field>
        <Field id="budget_range" label="예산">
          <input id="f-budget_range" name="budget_range" maxLength={50} placeholder="예: 50만 원 이내" />
        </Field>
        <Field id="source" label="도화를 어떻게 알게 되셨나요?" required error={err("source")} full>
          <select id="f-source" name="source" required defaultValue="" {...a11y("source")}>
            <option value="" disabled>선택해 주세요</option>
            {SOURCES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </Field>
        <Field id="message" label={`요청사항 (${message.length}/1000)`} error={err("message")} full>
          <textarea id="f-message" name="message" maxLength={1000} value={message} onChange={(e) => setMessage(e.target.value)} {...a11y("message")} />
        </Field>
      </div>
      <div className="hidden" aria-hidden="true">
        <label htmlFor="f-website">비워 두세요</label>
        <input id="f-website" name="website" tabIndex={-1} autoComplete="off" />
      </div>
      <label style={{ display: "flex", gap: 8, marginBottom: 20, alignItems: "flex-start" }}>
        <input type="checkbox" name="privacy_agreed" required style={{ marginTop: 4 }} />
        <span>
          문의 답변을 위해 담당자 이름·연락처를 수집하는 데 동의합니다.
          <span className="hint" style={{ display: "block" }}>상담이 끝나고 6개월 뒤 자동으로 삭제돼요.</span>
        </span>
      </label>
      {note ? <p className="field-error" role="alert" style={{ marginBottom: 14 }}>{note}</p> : null}
      <div className="button-row">
        <button className="btn" type="submit" disabled={state === "sending"}>{state === "sending" ? "보내는 중…" : "문의 접수하기"}</button>
        {brochureUrl ? <a className="btn outline" href={brochureUrl} target="_blank" rel="noopener">소개서 PDF</a> : null}
      </div>
      <p className="hint" style={{ marginTop: 10 }}>* 필수 입력 항목</p>
    </form>
  );
}
