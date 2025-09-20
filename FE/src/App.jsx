// src/App.jsx
import { useEffect, useLayoutEffect, useRef, useState, useCallback } from "react";
import LandingPage from "./LandingPage";
import SimulatorPage from "./SimulatorPage";
import ReportPage from "./ReportPage";

/* ================== 색상 토큰 ================== */
const COLORS = {
  bg: "#1E1F22",
  panel: "#2B2D31",
  border: "#3F4147",
  text: "#DCDDDE",
  sub: "#B5BAC1",
  blurple: "#5865F2",
  success: "#57F287",
  warn: "#FEE75C",
  danger: "#ED4245",
  black: "#0A0A0A",
  white: "#FFFFFF",
};

const RAW_API_BASE = import.meta.env?.VITE_API_URL || window.location.origin;
const API_BASE = RAW_API_BASE.replace(/\/$/, "");
const API_PREFIX = "/api";
export const API_ROOT = `${API_BASE}${API_PREFIX}`;

console.log("VITE_API_URL =", import.meta.env.VITE_API_URL);
console.log("API_ROOT =", API_ROOT);

/* ================== MOCK MODE (더미 JSONL 주입) ================== */
const MOCK_MODE = true;

/* 유틸: is_convinced(1~10) → 10~100% 로 정규화 */
function normalizeConvincedToPct(v) {
  const n = Math.max(1, Math.min(10, Number(v) || 0));
  return n * 10; // 1->10%, 10->100%
}

// public의 JSONL을 줄단위로 읽기
async function loadJsonlFromPublic(path) {
  const res = await fetch(path, { cache: "no-store" });
  if (!res.ok) throw new Error(`JSONL 로드 실패: ${res.status} ${res.statusText}`);
  const text = await res.text();
  return text
    .split(/\r?\n/)
    .filter(Boolean)
    .map((line) => JSON.parse(line));
}

/**
 * JSONL → 번들 스키마
 * 핵심 변경점: victim의 thoughts/dialogue를 "각각 별도 로그"로 push하며 kind를 부여
 */
function jsonlToConversationBundle(rows) {
  const case_id = "dummy-case-1";
  if (!Array.isArray(rows) || rows.length === 0) {
    return { case_id, logs: [], total_turns: 0 };
  }

  const t0 = Date.now();
  const logs = [];
  let i = 0;

  for (const r of rows) {
    const role = (r.role || "").toLowerCase(); // "offender" | "victim" | "spinner_message" 등
    const textFromRow = typeof r.text === "string" ? r.text : "";

    const jr = r.json_reply || {};
    const vThoughts = typeof jr.thoughts === "string" ? jr.thoughts.trim() : "";
    const vDialogue = typeof jr.dialogue === "string" ? jr.dialogue.trim() : "";

    const isConvRaw = (r.is_convinced ?? jr.is_convinced);
    const isConvPct = isConvRaw == null ? null : normalizeConvincedToPct(isConvRaw);

    const base = {
      run: r.run_no ?? 1,
      turn_index: r.turn ?? i,
      role,
      created_kst: new Date(t0 + i * 700).toISOString(),
      offender_name: "사칭 콜센터",
      victim_name: "피해자",
      use_agent: (r.run_no ?? 1) !== 1,
      guidance_type: null,
      guideline: null,
      is_convinced: isConvRaw ?? null,  // 1~10
      convinced_pct: isConvPct,         // 10~100
    };

    // victim의 thoughts → 별도 로그
    if (role === "victim" && vThoughts) {
      logs.push({
        ...base,
        kind: "thought",
        content: vThoughts, // 괄호 포함 그대로
      });
    }

    // victim의 dialogue → 별도 로그
    if (role === "victim" && vDialogue) {
      logs.push({
        ...base,
        kind: "speech",
        content: vDialogue,
      });
    }

    // offender/기타(텍스트만 있는 경우) → 그대로 1로그
    if (role !== "victim") {
      logs.push({
        ...base,
        kind: "speech",
        content: textFromRow,
      });
    }

    i += 1;
  }

  // 정렬: run → turn → (같은 턴에서는 thought 먼저) → 시간
  logs.sort((a, b) => {
    const ra = (a.run ?? 0) - (b.run ?? 0);
    if (ra !== 0) return ra;
    const ta = (a.turn_index ?? 0) - (b.turn_index ?? 0);
    if (ta !== 0) return ta;
    if (a.kind !== b.kind) return a.kind === "thought" ? -1 : 1;
    return new Date(a.created_kst) - new Date(b.created_kst);
  });

  const total_turns = Math.max(...logs.map((x) => x.turn_index ?? 0), 0) + 1;

  return {
    case_id,
    scenario: {
      methods_used: [],
      last_analysis: {
        outcome: "inconclusive",
        reasons: [],
        guidance: { type: null, title: null, category: null },
        phishing: null,
      },
    },
    offender: { id: 1, name: "사칭 콜센터", type: "더미", is_active: true },
    victim: {
      id: 1,
      name: "피해자",
      is_active: true,
      photo_path: "/static/images/victims/1.png",
    },
    logs,
    total_turns,
    phishing: null,
    evidence: null,
  };
}

// JSONL 캐시
let __dummyBundleCache = null;
async function getDummyBundle() {
  if (__dummyBundleCache) return __dummyBundleCache;
  const rows = await loadJsonlFromPublic("/dummy/sim_convo_rounds1_2_full.jsonl");
  __dummyBundleCache = jsonlToConversationBundle(rows);
  return __dummyBundleCache;
}

/* ================== 공통 fetch 유틸 ================== */

async function fetchWithTimeout(
  url,
  { method = "GET", headers = {}, body = null, timeout = 100000 } = {},
) {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeout);

  const opts = { method, headers: { ...headers }, signal: controller.signal };
  if (body != null) {
    opts.body = typeof body === "string" ? body : JSON.stringify(body);
    opts.headers["Content-Type"] =
      opts.headers["Content-Type"] || "application/json";
  }

  try {
    const res = await fetch(url, opts);
    clearTimeout(id);
    if (!res.ok) {
      const txt = await res.text().catch(() => "");
      throw new Error(`HTTP ${res.status} ${res.statusText} ${txt}`);
    }
    const txt = await res.text();
    return txt ? JSON.parse(txt) : null;
  } catch (err) {
    if (err.name === "AbortError") throw new Error("요청 타임아웃 또는 취소됨");
    throw err;
  } finally {
    clearTimeout(id);
  }
}

/* ================== API 헬퍼 ================== */

async function runReactSimulation(body) {
  if (MOCK_MODE) {
    return { case_id: (await getDummyBundle()).case_id };
  }
  return fetchWithTimeout(`${API_ROOT}/react-agent/simulation`, {
    method: "POST",
    body,
    timeout: 600000,
  });
}

async function getOffenders() { return fetchWithTimeout(`${API_ROOT}/offenders/`); }
async function getVictims() { return fetchWithTimeout(`${API_ROOT}/victims/`); }
async function getConversationBundle(caseId) {
  if (MOCK_MODE) return await getDummyBundle();
  return fetchWithTimeout(`${API_ROOT}/conversations/${encodeURIComponent(caseId)}`);
}
async function runConversationAsync(offenderId, victimId, payload = {}) {
  return fetchWithTimeout(
    `${API_ROOT}/conversations/run_async/${encodeURIComponent(offenderId)}/${encodeURIComponent(victimId)}`,
    { method: "POST", body: payload, timeout: 300000 },
  );
}
async function getJobStatus(jobId) {
  return fetchWithTimeout(`${API_ROOT}/conversations/job/${encodeURIComponent(jobId)}`, { timeout: 15000 });
}
async function runAgentForCase(caseId, payload = {}, { verbose = false } = {}) {
  return fetchWithTimeout(
    `${API_ROOT}/agent/run/${encodeURIComponent(caseId)}?verbose=${verbose ? "true" : "false"}`,
    { method: "POST", body: payload, timeout: 120000 },
  );
}
async function runAgentForCaseAsync(caseId, { verbose = false, timeout = 1200000 } = {}) {
  const url = `${API_ROOT}/agent/run_async/${encodeURIComponent(caseId)}?verbose=${verbose ? "true" : "false"}`;
  return fetchWithTimeout(url, { method: "POST", timeout });
}
async function getAgentJobStatus(jobId) {
  return fetchWithTimeout(`${API_ROOT}/agent/job/${encodeURIComponent(jobId)}`, { timeout: 300000 });
}
async function getPersonalizedForCase(caseId) {
  return fetchWithTimeout(`${API_ROOT}/personalized/by-case/${encodeURIComponent(caseId)}`, { timeout: 200000 });
}

// ==== use_agent 판별 및 로그 필터 유틸 ====
function isUseAgentTrue(log) {
  if (!log) return false;
  const v = log?.use_agent ?? log?.useAgent ?? log?.use_agent_flag ?? log?.use_agent_value;
  if (v === true || v === "true") return true;
  if (v === 1 || v === "1") return true;
  return false;
}
function filterLogsByAgentFlag(logs = [], { forAgent = false } = {}) {
  if (!Array.isArray(logs)) return [];
  return forAgent ? logs.filter((l) => isUseAgentTrue(l)) : logs.filter((l) => !isUseAgentTrue(l));
}

// === 요약 박스 컴포넌트 (미리보기 preview를 그대로 표시) ======================
function mapOutcomeToKorean(outcome) {
  switch (outcome) {
    case "attacker_fail": return "공격자 실패";
    case "attacker_success": return "공격자 성공";
    case "inconclusive": return "판단 불가";
    default: return outcome || "-";
  }
}
function toArrayReasons(reason, reasons) {
  if (Array.isArray(reasons) && reasons.length) return reasons;
  if (Array.isArray(reason)) return reason;
  if (typeof reason === "string" && reason.trim()) return [reason];
  return [];
}
function InlinePhishingSummaryBox({ preview }) {
  if (!preview) return null;
  const outcome = mapOutcomeToKorean(preview.outcome);
  const reasons = toArrayReasons(preview.reason, preview.reasons);
  const guidanceTitle = preview?.guidance?.title || "-";

  return (
    <div className="max-w-3xl mx-auto my-4">
      <div className="rounded-2xl border border-gray-200 bg-white/60 shadow-sm backdrop-blur p-4 md:p-5">
        <h3 className="text-base md:text-lg font-semibold mb-3">
          요약(대화 1 분석)
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <div className="text-xs text-gray-500 mb-1">피싱여부</div>
            <div className="text-sm md:text-base text-gray-900">{outcome}</div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">적용 지침</div>
            <div className="text-sm md:text-base text-gray-900 line-clamp-2">
              {guidanceTitle}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">피싱여부 근거</div>
            {reasons.length === 0 ? (
              <div className="text-sm text-gray-500">-</div>
            ) : (
              <ul className="list-disc pl-5 space-y-1">
                {reasons.map((r, i) => (
                  <li key={i} className="text-sm leading-6">
                    {r}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ================== App 컴포넌트 ================== */
const App = () => {
  const [currentPage, setCurrentPage] = useState("landing");

  // data
  const [scenarios, setScenarios] = useState([]);
  const [characters, setCharacters] = useState([]);
  const [defaultCaseData, setDefaultCaseData] = useState(null);

  // selection / simulation
  const [selectedScenario, setSelectedScenario] = useState(null);
  const [selectedCharacter, setSelectedCharacter] = useState(null);
  const [simulationState, setSimulationState] = useState("IDLE"); // IDLE, PREPARE, RUNNING, INTERMISSION, IDLE
  const [messages, setMessages] = useState([]);
  const [sessionResult, setSessionResult] = useState(null);
  const [progress, setProgress] = useState(0);

  // modal / decision flags
  const [pendingAgentDecision, setPendingAgentDecision] = useState(false);
  const [showReportPrompt, setShowReportPrompt] = useState(false);

  // run control flags
  const [hasInitialRun, setHasInitialRun] = useState(false);
  const [hasAgentRun, setHasAgentRun] = useState(false);
  const [agentRunning, setAgentRunning] = useState(false);

  // NEW: spinner 노출 시간
  const [spinnerDelayMs, setSpinnerDelayMs] = useState(3000);
  const [boardDelaySec, setBoardDelaySec] = useState(18); // 오른쪽 보드 지연(초)

  // refs
  const scrollContainerRef = useRef(null);
  const jobPollRef = useRef(null);
  const simIntervalRef = useRef(null);
  const lastTurnRef = useRef(-1);

  // UI loading/error
  const [dataLoading, setDataLoading] = useState(true);
  const [dataError, setDataError] = useState(null);
  const [currentCaseId, setCurrentCaseId] = useState(null);

  const [agentPreviewShown, setAgentPreviewShown] = useState(false);
  const [showIntermissionSpinner, setShowIntermissionSpinner] = useState(false);

  // NEW: verbose 토글
  const [agentVerbose, setAgentVerbose] = useState(false);

  // victim image helper
  const getVictimImage = (photoPath) => {
    if (!photoPath) return null;
    try {
      const fileName = photoPath.split("/").pop();
      if (fileName)
        return new URL(`./assets/victims/${fileName}`, import.meta.url).href;
    } catch (e) {
      console.warn("이미지 로드 실패:", e);
    }
    return null;
  };

  /* 메시지 추가 유틸 */
  const addSystem = (content) =>
    setMessages((prev) => [
      ...prev,
      { type: "system", content, timestamp: new Date().toLocaleTimeString() },
    ]);
  const addAnalysis = (content) =>
    setMessages((prev) => [
      ...prev,
      { type: "analysis", content, timestamp: new Date().toLocaleTimeString() },
    ]);
  const addChat = (
    sender,
    content,
    timestamp = null,
    senderLabel = null,
    side = null,
    meta = {}
  ) =>
    setMessages((prev) => [
      ...prev,
      {
        type: "chat",
        sender,
        senderLabel: senderLabel ?? sender,
        senderName: senderLabel ?? sender,
        side: side ?? (sender === "offender" ? "left" : "right"),
        content,
        timestamp: timestamp ?? new Date().toLocaleTimeString(),
        ...meta, // ✅ 메타(예: convincedPct, variant) 주입
      },
    ]);
  // spinner_message 추가 유틸(현재는 system으로 표기)
  const addSpinner = (content) =>
    setMessages((prev) => [
      ...prev,
      {
        type: "system",
        content: content?.startsWith("🔄") ? content : `🔄 ${content}`,
        timestamp: new Date().toLocaleTimeString(),
      },
    ]);

  /* 스크롤 자동 하단 고정 */
  const stickToBottom = () => {
    const el = scrollContainerRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  };
  useLayoutEffect(() => {
    stickToBottom();
  }, [
    messages,
    simulationState,
    selectedScenario,
    selectedCharacter,
    sessionResult,
  ]);

  useEffect(() => {
    const el = scrollContainerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => stickToBottom());
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  /* 초기 데이터 로드 */
  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        setDataLoading(true);
        setDataError(null);
        const [offList, vicList] = await Promise.all([getOffenders(), getVictims()]);
        if (!mounted) return;
        setScenarios(Array.isArray(offList) ? offList : []);
        setCharacters(Array.isArray(vicList) ? vicList : []);
      } catch (err) {
        console.error("초기 데이터 로드 실패:", err);
        if (!mounted) return;
        setDataError(err.message || String(err));
      } finally {
        if (mounted) setDataLoading(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  /**
   * 대화 로그 재생
   * - run 1 → 2 전환 구간에서 spinner_message를 표시하고 spinnerDelayMs 만큼 대기 후 2라운드 시작
   * - JSONL에 role === 'spinner_message'가 있으면 그 텍스트 사용, 없으면 "생각중…" 사용
   */
  const playLogs = useCallback(
    (
      logs = [],
      {
        append = false,
        speed = 1500,
        spinnerText: spinnerTextArg = null,
        spinnerDelayOverride = null,
      } = {},
      onComplete = null,
    ) => {
      if (!Array.isArray(logs) || logs.length === 0) {
        onComplete && onComplete();
        return;
      }

      // spinner_message 추출 및 본 로그에서 제외
      const spinnerLog = logs.find((l) => (l.role || "").toLowerCase() === "spinner_message");
      const spinnerText =
        spinnerTextArg ||
        (spinnerLog?.content && String(spinnerLog.content).trim()) ||
        "생각중…";
      const purifiedLogs = logs.filter((l) => (l.role || "").toLowerCase() !== "spinner_message");

      if (!append) setMessages([]);
      setProgress((p) => (append ? p : 0));

      setSimulationState("PREPARE");

      if (simIntervalRef.current) {
        clearTimeout(simIntervalRef.current);
        simIntervalRef.current = null;
      }

      const total = purifiedLogs.length;
      let idx = 0;
      let prevRun = purifiedLogs[0]?.run ?? 1;

      const INITIAL_DELAY = 1000; // 첫 메시지 전 짧은 로딩
      const INTERMISSION_DELAY = spinnerDelayOverride ?? spinnerDelayMs;

      // ====== (1) pushOne: 다음 로그까지 받아서 합칠 수 있게 변경 ======
      const pushOne = (log, nextLog = null) => {
        const role = (log.role || "").toLowerCase();
        const offenderLabel =
          log.offender_name ||
          (selectedScenario ? `피싱범${selectedScenario.id}` : "피싱범");
        const victimLabel =
          log.victim_name ||
          (selectedCharacter ? `피해자${selectedCharacter.id}` : "피해자");
        const displayLabel = role === "offender" ? offenderLabel : victimLabel;
        const side = role === "offender" ? "left" : "right";

        const content = String(log.content ?? "");

        const ts =
          log.created_kst && typeof log.created_kst === "string"
            ? new Date(log.created_kst).toLocaleTimeString()
            : log.created_kst ?? new Date().toLocaleTimeString();

        const convincedPct =
          (typeof log.convinced_pct === "number" ? log.convinced_pct : null) ??
          (log.is_convinced != null ? normalizeConvincedToPct(log.is_convinced) : null);

        // victim thought + (다음 victim speech 같은 run/turn) → 한 카드로 병합
        const canCombine =
          (log.role || "").toLowerCase() === "victim" &&
          log.kind === "thought" &&
          nextLog &&
          (nextLog.role || "").toLowerCase() === "victim" &&
          nextLog.kind === "speech" &&
          (nextLog.run ?? log.run) === log.run &&
          (nextLog.turn_index ?? log.turn_index) === log.turn_index;

        if (canCombine) {
          const speechText = String(nextLog.content ?? "");
          addChat(
            role,                     // victim
            speechText,               // 카드의 본문은 '발화'
            ts,
            displayLabel,
            side,
            {
              convincedPct,
              variant: "combined",    // UI에서 결합 카드로 분기
              thoughtText: content,   // 내부 박스(빨간)
              speechText,             // 일반 발화(흰색)
              run: log.run,
              turn: log.turn_index,
            }
          );
          return 2; // 두 로그를 소비
        }

        // 기본(단일 로그) 처리
        addChat(
          role || "offender",
          content,
          ts,
          displayLabel,
          side,
          {
            convincedPct,
            variant: log.kind === "thought" ? "thought" : "speech",
            run: log.run,
            turn: log.turn_index,
          }
        );
        return 1; // 한 로그 소비
      };

      // ====== (2) step: 병합(consumed=2) 반영 + intermission 구간에서도 병합 처리 ======
      const step = () => {
        if (idx >= total) {
          simIntervalRef.current = null;
          setSimulationState("IDLE");
          onComplete && onComplete();
          return;
        }

        const log = purifiedLogs[idx];
        const currRun = log.run ?? prevRun;

        // run 1 -> 2 전환 시: spinner 표시 → 대기 → 다음 로그 출력 (병합 고려)
        if (prevRun === 1 && currRun === 2) {
          setSimulationState("INTERMISSION");
          setShowIntermissionSpinner(true);
          simIntervalRef.current = setTimeout(() => {
            setShowIntermissionSpinner(false);
            setSimulationState("RUNNING");

            // intermission 뒤 첫 출력에서도 병합 여부 판단
            const next = purifiedLogs[idx + 1];
            let consumed = 1;
            if (
              (log.role || "").toLowerCase() === "victim" &&
              log.kind === "thought" &&
              next &&
              (next.role || "").toLowerCase() === "victim" &&
              next.kind === "speech" &&
              (next.run ?? log.run) === log.run &&
              (next.turn_index ?? log.turn_index) === log.turn_index
            ) {
              consumed = pushOne(log, next); // 2 소비
            } else {
              consumed = pushOne(log);       // 1 소비
            }

            if (!append) {
              setProgress(Math.min(100, ((idx + consumed) / total) * 100));
            } else {
              setProgress((p) => Math.min(100, p + (consumed * 100) / Math.max(1, total)));
            }

            prevRun = currRun;
            idx += consumed;
            step();
          }, INTERMISSION_DELAY);
          return;
        }

        const delay = idx === 0 ? INITIAL_DELAY : speed;

        simIntervalRef.current = setTimeout(() => {
          setSimulationState("RUNNING");

          // 일반 경로에서도 병합 판단
          const next = purifiedLogs[idx + 1];
          let consumed = 1;
          if (
            (log.role || "").toLowerCase() === "victim" &&
            log.kind === "thought" &&
            next &&
            (next.role || "").toLowerCase() === "victim" &&
            next.kind === "speech" &&
            (next.run ?? log.run) === log.run &&
            (next.turn_index ?? log.turn_index) === log.turn_index
          ) {
            consumed = pushOne(log, next); // 2 소비
          } else {
            consumed = pushOne(log);       // 1 소비
          }

          if (!append) {
            setProgress(Math.min(100, ((idx + consumed) / total) * 100));
          } else {
            setProgress((p) => Math.min(100, p + (consumed * 100) / Math.max(1, total)));
          }

          prevRun = currRun;
          idx += consumed;
          step();
        }, delay);
      };

      step();

    },
    [
      addChat,
      setMessages,
      setProgress,
      setSimulationState,
      selectedScenario,
      selectedCharacter,
      spinnerDelayMs,
    ],
  );

  const showConversationBundle = useCallback((bundle) => {
    setDefaultCaseData(bundle);
    setSessionResult((prev) => ({
      ...(prev || {}),
      phishing: bundle.phishing ?? prev?.phishing ?? null,
      isPhishing: bundle.phishing ?? prev?.isPhishing ?? null,
      evidence: bundle.evidence ?? prev?.evidence ?? null,
      totalTurns: bundle.total_turns ?? prev?.totalTurns ?? null,
    }));

    const logs = (bundle.logs || []).slice().sort((a, b) => {
      const ra = (a.run ?? 0) - (b.run ?? 0);
      if (ra !== 0) return ra;
      const ta = (a.turn_index ?? 0) - (b.turn_index ?? 0);
      if (ta !== 0) return ta;
      const da =
        new Date(a.created_at || a.created_kst || 0) -
        new Date(b.created_at || b.created_kst || 0);
      return da;
    });

    if (!logs.length) {
      addSystem("표시할 대화 로그가 없습니다.");
      setShowReportPrompt(true);
      setSimulationState("IDLE");
      return;
    }

    // 전체 로그 재생 (spinner_message는 playLogs 내부에서 처리)
    playLogs(
      logs,
      {
        append: false,
        speed: 700,
      },
      () => {
        setShowReportPrompt(true);
        addSystem("대화 재생이 완료되었습니다. 리포트를 확인할 수 있습니다.");
      },
    );
  }, [addSystem, playLogs, setShowReportPrompt, setSimulationState]);

  const showExistingCase = useCallback(async (caseId) => {
    try {
      const bundle = await getConversationBundle(caseId);
      setCurrentCaseId(caseId);
      showConversationBundle(bundle);
    } catch (e) {
      addSystem(`대화 불러오기 실패: ${e.message}`);
    }
  }, [addSystem, showConversationBundle]);

  /* job 폴링 */
  const startJobPollingForKick = (
    jobId,
    {
      intervalMs = 1200,
      timeoutMs = 120000,
      onProgress = null,
      onDone = null,
      onError = null,
    } = {},
  ) => {
    if (!jobId) {
      onError && onError(new Error("jobId 없음"));
      return;
    }
    if (jobPollRef.current) {
      clearInterval(jobPollRef.current);
      jobPollRef.current = null;
    }

    const start = Date.now();
    jobPollRef.current = setInterval(async () => {
      try {
        if (Date.now() - start > timeoutMs) {
          clearInterval(jobPollRef.current);
          jobPollRef.current = null;
          onError && onError(new Error("폴링 타임아웃"));
          return;
        }

        const st = await getJobStatus(jobId).catch((e) => { throw e; });
        onProgress && onProgress(st);
        if (!st) return;

        if (st.status === "error") {
          clearInterval(jobPollRef.current);
          jobPollRef.current = null;
          onError && onError(new Error(st.error || "job error"));
        } else if (st.status === "not_found") {
          clearInterval(jobPollRef.current);
          jobPollRef.current = null;
          onError && onError(new Error("job not_found"));
        } else if (st.status === "done" && st.case_id) {
          clearInterval(jobPollRef.current);
          jobPollRef.current = null;
          setCurrentCaseId(st.case_id);
          try {
            const bundle = await getConversationBundle(st.case_id);
            onDone && onDone(bundle, st.case_id);
          } catch (err) {
            onError && onError(err);
          }
        }
      } catch (err) {
        console.warn("job 폴링 실패:", err);
      }
    }, intervalMs);
  };

  /* --------- startSimulation --------- */
  const startSimulation = async () => {
    if (!selectedScenario || !selectedCharacter) {
      addSystem("시나리오와 캐릭터를 먼저 선택해주세요.");
      return;
    }
    setAgentPreviewShown(false);
    setHasInitialRun(true);
    setAgentRunning(false);

    if (simIntervalRef.current) {
      clearInterval(simIntervalRef.current);
      simIntervalRef.current = null;
    }
    if (jobPollRef.current) {
      clearInterval(jobPollRef.current);
      jobPollRef.current = null;
    }

    setSimulationState("PREPARE");
    setMessages([]);
    setProgress(0);
    setSessionResult(null);
    setCurrentCaseId(null);
    lastTurnRef.current = -1;
    setPendingAgentDecision(false);
    setShowReportPrompt(false);

    addSystem(
      `오케스트레이터 시뮬레이션 시작: ${selectedScenario.name} / ${selectedCharacter.name}`,
    );

    try {
      const res = await runReactSimulation({
        victim_id: selectedCharacter.id,
        offender_id: selectedScenario.id,
        use_tavily: false,
        max_turns: 15,
        round_limit: 3,
        round_no: 1
      });
      if (!res || !res.case_id) {
        addSystem("시뮬레이션 실패: case_id를 받지 못했습니다.");
        setSimulationState("IDLE");
        return;
      }
      setCurrentCaseId(res.case_id);
      const bundle = await getConversationBundle(res.case_id);
      showConversationBundle(bundle);
    } catch (err) {
      console.error("시뮬레이션 실행 실패:", err);
      addSystem("시뮬레이션 실행 실패 (콘솔 로그 확인).");
      setSimulationState("IDLE");
    }
  };

  /* --------- declineAgentRun --------- */
  const declineAgentRun = () => {
    setPendingAgentDecision(false);
    setShowReportPrompt(true);
    addSystem("에이전트 사용을 건너뜁니다. 리포트를 확인할 수 있습니다.");
  };

  /* --------- startAgentRun --------- */
  const startAgentRun = async () => {
    if (!currentCaseId) {
      addSystem("case_id가 없습니다. 초기 시뮬레이션이 정상적으로 완료되었는지 확인하세요.");
      return;
    }
    if (hasAgentRun || agentRunning) return;

    setPendingAgentDecision(false);
    setSimulationState("PREPARE");
    setAgentRunning(true);
    addSystem(`에이전트 시뮬레이션을 시작합니다... (verbose=${agentVerbose ? "on" : "off"})`);

    try {
      const kick = await runAgentForCaseAsync(currentCaseId, { verbose: agentVerbose, timeout: 120000 });
      if (!kick || !kick.job_id) {
        addSystem("에이전트 실행 실패: job_id를 받지 못했습니다.");
        setAgentRunning(false);
        setSimulationState("IDLE");
        return;
      }

      const jobId = kick.job_id;
      const start = Date.now();
      const POLL_INTERVAL = 1200;
      const POLL_TIMEOUT = 180000;

      const poll = async () => {
        if (Date.now() - start > POLL_TIMEOUT) throw new Error("에이전트 폴링 타임아웃");
        const st = await getAgentJobStatus(jobId);
        if (!st) return null;

        const preview = st?.result?.preview ?? st?.preview ?? null;
        if (preview && !agentPreviewShown) {
          addSystem(
            [
              "🔎 에이전트 사전 판정(미리보기)",
              `- 피싱 여부: ${preview.phishing ? "성공(공격자 우세)" : "실패(피해자 우세)"}`,
              Array.isArray(preview.reasons) && preview.reasons.length
                ? `- 이유: ${preview.reasons.slice(0, 3).join(" / ")}`
                : "",
              preview.guidance?.title ? `- 지침: ${preview.guidance.title}` : "",
            ].filter(Boolean).join("\n"),
          );
          setSessionResult((prev) => ({ ...(prev || {}), preview }));
          setAgentPreviewShown(true);
        }

        if (st.status === "error") throw new Error(st.error || "agent job error");
        if (st.status === "not_found") throw new Error("agent job not_found");
        if (st.status === "running") return null;

        return st.result || st;
      };

      let result = null;
      while (true) {
        const r = await poll();
        if (r) { result = r; break; }
        await new Promise((res) => setTimeout(res, POLL_INTERVAL));
      }

      const cid = result.case_id || currentCaseId;
      setCurrentCaseId(cid);
      const bundle = await getConversationBundle(cid);

      setDefaultCaseData(bundle);

      let personalized = bundle.personalized || bundle.personalized_preventions || null;
      if (!personalized) {
        try {
          const pj = await getPersonalizedForCase(cid);
          if (pj) personalized = pj;
        } catch (_) {}
      }

      const agentOnlyLogs = filterLogsByAgentFlag(bundle.logs || [], { forAgent: true });
      setSessionResult((prev) => ({
        ...(prev || {}),
        phishing: bundle.phishing ?? prev?.phishing ?? null,
        isPhishing: bundle.phishing ?? prev?.isPhishing ?? null,
        evidence: bundle.evidence ?? prev?.evidence ?? null,
        totalTurns: bundle.total_turns ?? prev?.totalTurns ?? null,
        agentUsed: true,
        agentLogs: agentOnlyLogs,
        personalized,
      }));

      if (!agentOnlyLogs.length) {
        addSystem("에이전트 전용 로그(use_agent=true)가 없습니다.");
        setHasAgentRun(true);
        setAgentRunning(false);
        setShowReportPrompt(true);
        return;
      }

      playLogs(agentOnlyLogs, { append: true, speed: 1500 }, () => {
        setHasAgentRun(true);
        setAgentRunning(false);
        setShowReportPrompt(true);
        addSystem("에이전트 대화 재생이 완료되었습니다. 리포트를 확인할 수 있습니다.");
      });
    } catch (err) {
      console.error("에이전트 실행 실패:", err);
      addSystem(`에이전트 실행 실패: ${err.message || String(err)}`);
      setAgentRunning(false);
      setSimulationState("IDLE");
    }
  };

  /* --------- resetToSelection --------- */
  const resetToSelection = () => {
    setSelectedScenario(null);
    setSelectedCharacter(null);
    setMessages([]);
    setSessionResult(null);
    setProgress(0);
    setSimulationState("IDLE");
    setCurrentPage("simulator");
  };

  const handleBack = () => {
    setCurrentPage("landing");
  };

  // cleanup on unmount
  useEffect(() => {
    return () => {
      if (simIntervalRef.current) {
        clearInterval(simIntervalRef.current);
        simIntervalRef.current = null;
      }
      if (jobPollRef.current) {
        clearInterval(jobPollRef.current);
        jobPollRef.current = null;
      }
    };
  }, []);

  /* --------- pageProps 전달 --------- */
  const pageProps = {
    COLORS,
    boardDelaySec,
    setBoardDelaySec,
    mockMode: MOCK_MODE,
    apiRoot: API_ROOT,
    onBack: handleBack,
    setCurrentPage,
    selectedScenario,
    setSelectedScenario,
    selectedCharacter,
    setSelectedCharacter,
    simulationState,
    setSimulationState,
    messages,
    addSystem,
    addAnalysis,
    addChat,
    sessionResult,
    resetToSelection,
    startSimulation,
    startAgentRun,
    declineAgentRun,
    scenarios,
    characters,
    scrollContainerRef,
    defaultCaseData,
    dataLoading,
    dataError,
    currentCaseId,
    pendingAgentDecision,
    showReportPrompt,
    hasInitialRun,
    hasAgentRun,
    agentRunning,
    progress,
    setProgress,
    setShowReportPrompt,
    agentVerbose,
    setAgentVerbose,
    spinnerDelayMs,
    setSpinnerDelayMs,
    victimImageUrl: selectedCharacter
      ? getVictimImage(selectedCharacter.photo_path)
      : null,
  };

  return (
    <div className="font-sans">
      {currentPage === "landing" && (
        <LandingPage setCurrentPage={setCurrentPage} />
      )}
      {currentPage === "simulator" && <SimulatorPage {...pageProps} />}
      {currentPage === "report" && (
        <ReportPage {...pageProps} apiRoot={API_ROOT} mockMode={MOCK_MODE} defaultCaseData={defaultCaseData} />
      )}
    </div>
  );
};

export default App;
