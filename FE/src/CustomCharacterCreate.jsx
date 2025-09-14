// src/CustomCharacterCreate.jsx
import { useState } from "react";
// import CustomCharacterModal from "./CustomCharacterModal";

/** 내부에서 API_ROOT 계산 */
const RAW_API_BASE = import.meta.env?.VITE_API_URL || window.location.origin;
const API_BASE = RAW_API_BASE.replace(/\/$/, "");
const API_PREFIX = "/api";
const API_ROOT = `${API_BASE}${API_PREFIX}`;


/* ========== 내부 모달 컴포넌트 ========== */
function CustomCharacterModal({ open, onClose, onSave, theme }) {
  if (!open) return null;

  const C = theme || {
    panel: "#2B2D31",
    panelDark: "#232428",
    text: "#FFFFFF",
    sub: "#B5BAC1",
    border: "#3F4147",
    blurple: "#5865F2",
  };

  const DEFAULT = {
    name: "",
    ageBucket: "",
    gender: "",
    address: "",
    education: "",
    knowledge: { comparative_notes: [], competencies: [] },
    traits: {
      ocean: {
        openness: "낮음",
        neuroticism: "낮음",
        extraversion: "낮음",
        agreeableness: "낮음",
        conscientiousness: "낮음",
      },
      vulnerability_notes: [],
    },
    note: "사용자 입력으로 생성",
  };

  const [form, setForm] = useState(DEFAULT);
  const set = (patch) => setForm((prev) => ({ ...prev, ...patch }));

  const onSubmit = async (e) => {
    e.preventDefault();
    if (!form.name || !form.ageBucket || !form.gender || !form.address || !form.education) {
      alert("필수 항목을 모두 입력하세요.");
      return;
    }

    // 서버에 POST
    const body = {
      name: form.name.trim(),
      meta: {
        age: form.ageBucket,
        education: form.education,
        gender: form.gender,
        address: form.address,
      },
      knowledge: form.knowledge,
      traits: form.traits,
      note: form.note,
    };

    const res = await fetch(`${API_ROOT}/custom/victims`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const txt = await res.text();
      alert(`저장 실패: ${txt}`);
      return;
    }
    const saved = await res.json();
    onSave?.(saved);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div
        className="w-full max-w-2xl rounded-lg border shadow-xl"
        style={{ backgroundColor: C.panel, borderColor: C.border, color: C.text }}
      >
        <div className="px-5 py-4 border-b" style={{ borderColor: C.border }}>
          <h2 className="text-lg font-semibold">커스텀 캐릭터 만들기</h2>
        </div>

        <form onSubmit={onSubmit}>
          <div className="max-h-[70vh] overflow-y-auto px-5 py-4 space-y-4">
            {/* 이름 */}
            <input
              placeholder="이름 *"
              value={form.name}
              onChange={(e) => set({ name: e.target.value })}
              className="w-full p-2 rounded outline-none"
              style={{ backgroundColor: C.panelDark, color: C.text }}
            />
            {/* 연령대 */}
            <select
              value={form.ageBucket}
              onChange={(e) => set({ ageBucket: e.target.value })}
              className="w-full p-2 rounded outline-none"
              style={{ backgroundColor: C.panelDark, color: C.text }}
            >
              <option value="">연령대 *</option>
              {["20대","30대","40대","50대","60대","70대"].map((v) => (
                <option key={v} value={v}>{v}</option>
              ))}
            </select>
            {/* 성별 */}
            <select
              value={form.gender}
              onChange={(e) => set({ gender: e.target.value })}
              className="w-full p-2 rounded outline-none"
              style={{ backgroundColor: C.panelDark, color: C.text }}
            >
              <option value="">성별 *</option>
              <option value="남성">남성</option>
              <option value="여성">여성</option>
            </select>
            {/* 거주지 */}
            <input
              placeholder="거주지 *"
              value={form.address}
              onChange={(e) => set({ address: e.target.value })}
              className="w-full p-2 rounded outline-none"
              style={{ backgroundColor: C.panelDark, color: C.text }}
            />
            {/* 학력 */}
            <select
              value={form.education}
              onChange={(e) => set({ education: e.target.value })}
              className="w-full p-2 rounded outline-none"
              style={{ backgroundColor: C.panelDark, color: C.text }}
            >
              <option value="">학력 *</option>
              <option value="고등학교 중퇴">고등학교 중퇴</option>
              <option value="고등학교 졸업">고등학교 졸업</option>
              <option value="대학교 졸업">대학교 졸업</option>
            </select>
            {/* 비고 */}
            <textarea
              rows={3}
              placeholder="비고(선택)"
              value={form.note}
              onChange={(e) => set({ note: e.target.value })}
              className="w-full p-2 rounded outline-none"
              style={{ backgroundColor: C.panelDark, color: C.text }}
            />
          </div>

          <div className="px-5 py-4 border-t flex justify-end gap-3"
               style={{ borderColor: C.border }}>
            <button type="button" onClick={onClose}
              className="px-4 py-2 rounded"
              style={{ backgroundColor: C.panelDark, color: C.text }}>
              취소
            </button>
            <button type="submit"
              className="px-4 py-2 rounded text-white"
              style={{ backgroundColor: C.blurple }}>
              저장
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

/* ========== 외부에 노출되는 “생성 버튼/타일” 컴포넌트 ========== */



async function postJson(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status} ${res.statusText} ${text}`);
  }
  return res.json();
}

/** 서버에 커스텀 피해자 생성 */
async function createCustomVictim(newCharFromModal) {
  const payload = {
    name: newCharFromModal.name,
    meta: newCharFromModal.meta || {},
    knowledge: newCharFromModal.knowledge || {},
    traits: newCharFromModal.traits || {},
    note: newCharFromModal.note || "사용자 입력으로 생성",
  };
  return postJson(`${API_ROOT}/custom/victims`, payload);
}

/**
 * Props:
 * - theme: { panel, panelDark, panelDarker, border, text, sub, blurple }
 * - onCreated?: (createdVictim) => void   // 저장 성공 시 부모에게 전달
 */
export default function CustomCharacterCreate({ theme, onCreated }) {
  const C = theme || {
    panel: "#061329",
    panelDark: "#04101f",
    panelDarker: "#020812",
    border: "#A8862A",
    text: "#FFFFFF",
    sub: "#B5BAC1",
    blurple: "#A8862A",
  };

  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [created, setCreated] = useState(null);

  const handleSave = async (newCharFromModal) => {
    try {
      setSaving(true);
      const res = await createCustomVictim(newCharFromModal);
      const createdVictim = { ...res, isCustom: true }; // 프론트 표식
      setCreated(createdVictim);
      setOpen(false);
      onCreated && onCreated(createdVictim);
    } catch (e) {
      alert(`저장 실패: ${e.message || e}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="w-full">
      {/* 트리거 타일 */}
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="w-full text-left rounded-2xl overflow-hidden border-2 border-dashed hover:opacity-90 transition"
        style={{
          backgroundColor: C.panelDark,
          borderColor: C.border,
          height: 320,
        }}
      >
        <div
          className="h-44 flex items-center justify-center text-5xl"
          style={{ backgroundColor: C.panelDarker }}
        >
          ➕
        </div>
        <div className="p-4">
          <div className="font-semibold text-lg" style={{ color: C.text }}>
            커스텀 캐릭터
          </div>
          <p className="mt-1 text-sm" style={{ color: C.sub }}>
            나이/성별/거주지/학력과 성격, 지식을 직접 입력하여 저장
          </p>
        </div>
      </button>

      {/* 방금 만든 커스텀 미리보기 */}
      {created && (
        <div
          className="mt-4 rounded-xl border p-4"
          style={{ borderColor: C.border, backgroundColor: C.panelDark }}
        >
          <div className="flex items-center justify-between mb-2">
            <div style={{ color: C.text }} className="font-semibold text-lg">
              {created.name}
              <span
                className="ml-2 text-xs px-2 py-1 rounded-md"
                style={{
                  color: C.blurple,
                  backgroundColor: "rgba(168,134,42,.08)",
                  border: `1px solid rgba(168,134,42,.18)`,
                }}
              >
                저장 완료 (id: {created.id})
              </span>
            </div>
          </div>

          <div style={{ color: C.sub }} className="text-sm space-y-1">
            <div>나이: <span style={{ color: C.text }}>{created.meta?.age ?? "-"}</span></div>
            <div>성별: <span style={{ color: C.text }}>{created.meta?.gender ?? "-"}</span></div>
            <div>거주지: <span style={{ color: C.text }}>{created.meta?.address ?? "-"}</span></div>
            <div>학력: <span style={{ color: C.text }}>{created.meta?.education ?? "-"}</span></div>
          </div>
        </div>
      )}

      {/* 입력 모달 */}
      {open && (
        <CustomCharacterModal
          open={open}
          onClose={() => !saving && setOpen(false)}
          onSave={handleSave}
          theme={C}
        />
      )}
    </div>
  );
}
