// src/App.jsx
import { useEffect, useLayoutEffect, useRef, useState, useCallback } from "react";
import LandingPage from "./LandingPage";
import ErrorBoundary from "./ErrorBoundary";
import SimulatorPage from "./SimulatorPage";
import ReportPage from "./ReportPage";

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

// ---- SSE 단일 연결 보장용 ----
const uuid = () => Math.random().toString(36).slice(2) + Date.now().toString(36);
let __activeES = null;          // 현재 열려있는 EventSource
let __activeStreamId = null;    // 현재 실행 stream_id (재연결/중복 클릭 방지)
let __ended = false;

// ANSI 컬러코드 제거
function stripAnsi(s = "") {
  return String(s).replace(/\x1B\[[0-9;]*m/g, "");
}

// "Finished chain" 포함 여부 (터미널 로그/문자열 모두 커버)
function containsFinishedChain(text = "") {
  const clean = stripAnsi(text);
  return /\bFinished chain\b/i.test(clean);
}


/* ================== API 헬퍼 ================== */
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
    if (err.name === "AbortError") throw new Error("요청 타임아웃");
    throw err;
  } finally {
    clearTimeout(id);
  }
}

async function getOffenders() {
  return fetchWithTimeout(`${API_ROOT}/offenders/`);
}
async function getVictims() {
  return fetchWithTimeout(`${API_ROOT}/victims/`);
}
async function getConversationBundle(caseId) {
  return fetchWithTimeout(
    `${API_ROOT}/conversations/${encodeURIComponent(caseId)}`,
  );
}

// ✅ SSE 스트리밍
export async function* streamReactSimulation(payload = {}) {
  const streamId = payload.stream_id ?? (__activeStreamId || (__activeStreamId = uuid()));
  const withId = { ...payload, stream_id: streamId };

  const endStream = (reason = "finished_chain") => {
    if (__ended) return;
    __ended = true;
    try { if (__activeES) __activeES.close(); } catch {}
    __activeES = null;
    __activeStreamId = null;
    done = true;
    push({ type: "run_end_local", content: { reason }, ts: new Date().toISOString() });
  };

  const params = new URLSearchParams();
  Object.entries(withId).forEach(([k, v]) => {
    if (v !== undefined && v !== null) params.set(k, String(v));
  });

  const base = typeof API_ROOT === "string" ? API_ROOT : "";
  const url = `${base}/react-agent/simulation/stream?${params.toString()}`;
  
  // ✅ 디버깅 1: URL 확인
  console.log('🚀 [streamReactSimulation] SSE 연결:', url);
  
  if (__activeES) { try { __activeES.close(); } catch {} }
  const es = new EventSource(url);
  __activeES = es;
  __ended = false;

  const queue = [];
  let notify;
  let done = false;

  const push = (data) => {
    // ✅ 디버깅 2: push 확인
    console.log('📥 [push] 큐에 추가:', data?.type || typeof data);
    queue.push(data);
    if (notify) { notify(); notify = undefined; }
  };

  // ✅ 디버깅 3: 연결 상태 확인
  es.onopen = () => {
    console.log('✅ [EventSource] 연결 성공!');
  };

  es.onmessage = (e) => {
    console.log('📩 [onmessage]', e.type, '| data:', e.data?.substring(0, 100));
    try { 
      const parsed = JSON.parse(e.data);
      push(parsed);
      const t = (parsed?.type || "").toLowerCase();
      const content = typeof parsed?.content === "string" ? parsed.content : (parsed?.content?.message ?? "");
      if (t === "terminal" || t === "log" || typeof parsed === "string") {
        if (containsFinishedChain(content || parsed)) endStream("finished_chain");
      }
    }
    catch { 
      push(e.data); 
      if (containsFinishedChain(String(e.data || ""))) endStream("finished_chain");
    }
  };

  const eventTypes = [
    "run_start",
    "log",
    "agent_action",
    "tool_observation",
    "agent_finish",
    "new_message",
    "turn_event",
    "debug",
    "result",
    "run_end",
    "ping",
    "heartbeat",
    "error",
    "terminal",
    "conversation_log",  // ✅ 이미 있음
    "judgement",
    "guidance",
    "prevention",
    "guidance_generated",
    "prevention_generated",
  ];
  
  // ✅ 디버깅 4: 등록 확인
  console.log('🎯 [EventSource] 리스너 등록:', eventTypes);
  
  eventTypes.forEach((t) => {
    es.addEventListener(t, (e) => {
      // ✅ 디버깅 5: 각 이벤트 수신 확인
      console.log(`📨 [${t}] 이벤트 수신! | data:`, e.data?.substring(0, 100) || e.data);
      
      if (__ended) return;
      let data = null;
      try { data = JSON.parse(e.data); } catch { data = e.data; }
      
      if (data && typeof data === "object" && !data.type) data.type = t;
      
      // ✅ 디버깅 6: conversation_log 특별 표시
      if (t === "conversation_log") {
        console.log('🎯🎯🎯 [conversation_log] 감지!!!');
        console.log('📦 data:', data);
      }
      
      push(data);

      const content = typeof data === "string"
        ? data
        : (typeof data?.content === "string" ? data.content : (data?.content?.message ?? ""));

      if (t === "run_end") { endStream("run_end_event"); return; }
      if (t === "error")   { endStream("error"); return; }
      if ((t === "terminal" || t === "log") && containsFinishedChain(content || "")) {
        endStream("finished_chain");
        return;
      }
    });
  });

  es.onerror = (e) => {
    console.error('❌ [EventSource] 에러:', e);
    if (!__ended) {
      push({ type: "error", message: "SSE connection error" });
      endStream("error_or_server_closed");
    }
  };

  try {
    console.log('🔄 [Generator] 이벤트 소비 시작');
    while (!done) {
      if (queue.length === 0) {
        await new Promise((r) => (notify = r));
      }
      while (queue.length) {
        const ev = queue.shift();
        // ✅ 디버깅 7: yield 확인
        console.log('⬆️ [yield] 이벤트 반환:', ev?.type);
        yield ev;
        if (ev?.type === "run_end" || ev?.type === "run_end_local" || ev?.type === "error") {
          endStream(ev?.type || "finished_chain");
          break;
        }
      }
    }
  } finally {
    console.log('🛑 [Generator] 종료');
    try { if (__activeES) es.close(); } catch {}
    __activeES = null;
    __activeStreamId = null;
    __ended = false;
  }
}

function extractDialogueOrPlainText(s) {
  if (!s) return s;
  // 코드펜스 제거
  const cleaned = s.replace(/```(?:json)?/gi, "").trim();
  try {
    const m = cleaned.match(/\{[\s\S]*\}/);
    if (m) {
      const obj = JSON.parse(m[0]);
      if (obj && typeof obj === "object") {
        if (typeof obj.dialogue === "string" && obj.dialogue.trim()) {
          return obj.dialogue.trim();
        }
        if (typeof obj.thoughts === "string" && obj.thoughts.trim()) {
          return obj.thoughts.trim();
        }
      }
    }
  } catch (_) {}
  // 과한 공백 정리
  return cleaned.replace(/[ \t]+/g, " ").replace(/\s*\n\s*/g, "\n").trim();
}

function parseConversationLogContent(content) {
  if (!content || typeof content !== "string") return null;
  // "[conversation_log] {...}" 형태만 처리
  const idx = content.indexOf("{");
  if (idx < 0) return null;
  try {
    const obj = JSON.parse(content.slice(idx));
    const caseId =
      obj.case_id || obj.meta?.case_id || obj.log?.case_id || null;
    const roundNo =
      obj.meta?.round_no ||
      obj.meta?.run_no ||
      obj.stats?.round ||
      obj.stats?.run ||
      1;
    const turns = Array.isArray(obj.turns) ? obj.turns : [];
    return { caseId, roundNo: Number(roundNo) || 1, turns };
  } catch (_) {
    return null;
  }
}

/* ================== App 컴포넌트 ================== */
const App = () => {
  const [currentPage, setCurrentPage] = useState("landing");
  const [personalized, setPersonalized] = useState(null);
  const [preventionEvent, setPreventionEvent] = useState(null);

  // data
  const [scenarios, setScenarios] = useState([]);
  const [characters, setCharacters] = useState([]);
  const [defaultCaseData, setDefaultCaseData] = useState(null);

  // selection / simulation
  const [selectedScenario, setSelectedScenario] = useState(null);
  const [selectedCharacter, setSelectedCharacter] = useState(null);
  const [simulationState, setSimulationState] = useState("IDLE"); // IDLE, PREPARE, RUNNING, FINISH
  const [messages, setMessages] = useState([]);
  const [sessionResult, setSessionResult] = useState(null);
  const [progress, setProgress] = useState(0);

  // modal / decision flags
  const [showReportPrompt, setShowReportPrompt] = useState(false);
  const [hasInitialRun, setHasInitialRun] = useState(false);

  // refs
  const scrollContainerRef = useRef(null);
  const simIntervalRef = useRef(null);
  const streamingRef = useRef(false);

  // 중복 턴 방지용
  const seenTurnsRef = useRef(new Set());

  // UI loading/error
  const [dataLoading, setDataLoading] = useState(true);
  const [dataError, setDataError] = useState(null);
  const [currentCaseId, setCurrentCaseId] = useState(null);

  const addSystem = (content) =>
    setMessages((prev) => [
      ...prev,
      { type: "system", content, timestamp: new Date().toLocaleTimeString() },
  ]);

const addChat = (sender, content, timestamp = null, senderLabel = null, side = null, meta = null) =>
    setMessages((prev) => [
      ...prev,
      {
        type: "chat",
        sender,
        senderLabel: senderLabel ?? sender,
        side: side ?? (sender === "offender" ? "left" : "right"),
        content,
        timestamp: timestamp ?? new Date().toLocaleTimeString(),
        ...(meta || {}),
      },
    ]);

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
        const [offList, vicList] = await Promise.all([
          getOffenders(),
          getVictims(),
        ]);
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

  /* resetToSelection */
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

  // cleanup
  useEffect(() => {
    return () => {
      if (simIntervalRef.current) {
        clearInterval(simIntervalRef.current);
        simIntervalRef.current = null;
      }
    if (__activeES) { try { __activeES.close(); } catch {} }
    __activeES = null;
    __activeStreamId = null;
    };
  }, []);

  /* --------- pageProps 전달 --------- */
  const pageProps = {
    COLORS,
    onBack: handleBack,
    setCurrentPage,

    selectedScenario,
    setSelectedScenario,
    selectedCharacter,
    setSelectedCharacter,

    simulationState,
    setSimulationState,

    messages,
    setMessages, // ✅ 추가: 외부에서 messages state 관리 중
    addSystem,
    addChat,

    sessionResult,
    resetToSelection,
    //startSimulation,

    scenarios,
    characters,
    scrollContainerRef,
    defaultCaseData,
    dataLoading,
    dataError,
    currentCaseId,
    setCurrentCaseId,

    showReportPrompt,
    setShowReportPrompt,
    hasInitialRun,

    progress,
    setProgress,

    victimImageUrl: selectedCharacter
      ? getVictimImage(selectedCharacter.photo_path)
      : null,

    // ✅ prevention 공유용 추가
    personalized,
    setPersonalized,
    preventionEvent,
    setPreventionEvent,
  };

  return (
    <div className="font-sans">
      {currentPage === "landing" && (
        <LandingPage setCurrentPage={setCurrentPage} />
      )}
      {currentPage === "simulator" && (
        <ErrorBoundary>
          <SimulatorPage {...pageProps} />
        </ErrorBoundary>
      )}
      {currentPage === "report" && (
        <ReportPage {...pageProps} defaultCaseData={defaultCaseData} />
      )}
    </div>
  );
};

export default App;
