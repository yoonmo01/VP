// src/App.jsx
import { useEffect, useLayoutEffect, useRef, useState, useCallback } from "react";
import LandingPage from "./LandingPage";
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
  // ① stream_id 고정(한 번의 실행 동안 유지)
  const streamId = payload.stream_id ?? (__activeStreamId || (__activeStreamId = uuid()));
  const withId = { ...payload, stream_id: streamId };

  const params = new URLSearchParams();
  Object.entries(withId).forEach(([k, v]) => {
    if (v !== undefined && v !== null) params.set(k, String(v));
  });

  const base = typeof API_ROOT === "string" ? API_ROOT : "";
  const url = `${base}/react-agent/simulation/stream?${params.toString()}`;
  // ② 기존 열린 SSE가 있으면 닫기(중복 연결 방지)
  if (__activeES) { try { __activeES.close(); } catch {} }
  const es = new EventSource(url);
  __activeES = es;

  const queue = [];
  let notify;
  let done = false;

  const push = (data) => {
    queue.push(data);
    if (notify) { notify(); notify = undefined; }
  };

  es.onmessage = (e) => {
    try { push(JSON.parse(e.data)); }
    catch { push(e.data); }
  };

  // 백엔드에서 실제로 쏘는 이름들까지 포함
  const eventTypes = [
    "run_start",
    "log",
    "agent_action",
    "tool_observation",
    "agent_finish",
    "new_message",        // ✅ 중요
    "turn_event",         // (외부 sink fan-in)
    "debug",
    "result",
    "run_end",
    "ping",
    "heartbeat",
    "error",
    "terminal",
  ];
  eventTypes.forEach((t) => {
    es.addEventListener(t, (e) => {
      try { push(JSON.parse(e.data)); }
      catch { push(e.data); }
      if (t === "run_end" || t === "error") {
        done = true;
        try { es.close(); } catch {}
        __activeES = null;
      }
    });
  });

  // ③ 브라우저의 자동 재연결 루프 차단(여기서 닫고 끝내기)
  es.onerror = () => {
    push({ type: "error", message: "SSE connection error" });
    done = true;
    try { es.close(); } catch {}
    __activeES = null;
  };


  try {
    while (!done) {
      if (queue.length === 0) {
        await new Promise((r) => (notify = r));
      }
      while (queue.length) {
        const ev = queue.shift();
        yield ev;
        if (ev?.type === "run_end" || ev?.type === "error") {
          done = true;
          try { es.close(); } catch {}
          __activeES = null;
          break;
        }
      }
    }
  } finally {
    try { es.close(); } catch {}
    __activeES = null;
    __activeStreamId = null; // 실행 종료 시 stream_id 해제
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

  /* ✅ startSimulation - SSE 스트리밍 */
  const startSimulation = async () => {
    if (streamingRef.current) {
      addSystem("이미 시뮬레이션이 진행 중입니다.");
      return;
    }
    streamingRef.current = true;

    if (!selectedScenario || !selectedCharacter) {
      addSystem("시나리오와 캐릭터를 먼저 선택해주세요.");
      streamingRef.current = false;
      return;
    }

    setHasInitialRun(true);
    seenTurnsRef.current = new Set();   // ✅ 중복 키 초기화

    if (simIntervalRef.current) {
      clearInterval(simIntervalRef.current);
      simIntervalRef.current = null;
    }

    setSimulationState("PREPARE");
    setMessages([]);
    setProgress(0);
    setSessionResult(null);
    setCurrentCaseId(null);
    setShowReportPrompt(false);

    addSystem(`시뮬레이션 시작: ${selectedScenario.name} / ${selectedCharacter.name}`);

    try {
      const payload = {
        victim_id: selectedCharacter.id,
        offender_id: selectedScenario.id,
        use_tavily: false,
        max_turns: 15,
        round_limit: 5,
        // stream_id는 generator에서 자동 부여(유지)
      };

      let caseId = null;
      let totalRounds = payload.round_limit;
      let currentRound = 0;

      for await (const event of streamReactSimulation(payload)) {
        // 서버는 { type, content, ts } 구조를 씀 → content 우선
        const evt = event?.content ?? event;
        console.log("[SSE Event]", event);

        if (event.type === "error") {
          // 서버의 409 메시지면 부드럽게 안내
          if ((event.message || "").includes("duplicated simulation run detected")) {
            addSystem("이미 실행 중인 시뮬레이션이 있습니다. 잠시 후 다시 시도해주세요.");
          }
          throw new Error(event.message || "시뮬레이션 오류");
        }

        else if (event.type === "case_created") {
          caseId = evt.case_id;
          setCurrentCaseId(caseId);
          addSystem(`케이스 생성: ${caseId}`);
        }
        
        else if (event.type === "round_start") {
          currentRound = evt.round;
          addSystem(evt.message);
        }
        
        else if (event.type === "simulation_progress") {
          setSimulationState("RUNNING");
          addSystem(evt.message || `라운드 ${evt.round} 진행 중...`);
        }
        
        else if (event.type === "conversation_logs") {
          // 진행 상황만 업데이트
          setProgress((evt.round / totalRounds) * 100);

          // ✅ 누락된 턴만 보정 (서버가 한꺼번에 보내줄 수 있으므로)
          const logs = Array.isArray(evt.logs) ? evt.logs : [];
          const missing = logs
            .sort((a,b) => (a.turn_index ?? 0) - (b.turn_index ?? 0))
            .filter((log) => {
              const role = (log.role || "offender").toLowerCase();
              const key = `${evt.round}:${log.turn_index}:${role}`;
              return !seenTurnsRef.current.has(key);
            });

          for (const log of missing) {
            const role = (log.role || "offender").toLowerCase();
            const raw = log.content || log.text || log.message || "";
            const content = extractDialogueOrPlainText(raw);

            const label =
              role === "offender"
                ? (selectedScenario?.name || "피싱범")
                : (selectedCharacter?.name || "피해자");
            const side = role === "offender" ? "left" : "right";
            const ts = log.created_kst
              ? new Date(log.created_kst).toLocaleTimeString()
              : new Date().toLocaleTimeString();

            addChat(role, content, ts, label, side, {
              run: log.run,
              turn: log.turn_index || log.turn,
            });

            const key = `${evt.round}:${log.turn_index}:${role}`;
            seenTurnsRef.current.add(key);
          }

          // 안내 메시지 (선택)
          if (evt.status === "no_logs") {
            addSystem(`⚠️ 라운드 ${evt.round} 로그를 가져오지 못했습니다.`);
          }
          setSimulationState("RUNNING");
        }
        
        else if (event.type === "round_complete") {
          // conversation_logs에서 이미 처리했으므로 중복 방지
          addSystem(`라운드 ${evt.round} 완료 (${evt.total_turns}턴)`);
        }
        // ✅ 백엔드가 [conversation_log] 묶음 로그만 보낼 때 프론트에서 발화별로 분해
        else if (
          event?.type === "log" &&
          typeof event.content === "string" &&
          event.content.startsWith("[conversation_log]")
        ) {
          const parsed = parseConversationLogContent(event.content);
          if (parsed && parsed.turns.length) {
            const roundNo = parsed.roundNo || 1;
            // 진행률 살짝 올려주기(선택)
            setProgress((p) => Math.min(100, p + 1));
            setSimulationState("RUNNING");

            parsed.turns.forEach((t, idx) => {
              const role = (t.role || "offender").toLowerCase();
              const raw = t.text || t.content || "";
              const content = extractDialogueOrPlainText(raw);

              const key = `${roundNo}:${idx}:${role}`;
              if (seenTurnsRef.current.has(key)) return; // 중복 방지
              seenTurnsRef.current.add(key);

              const label =
                role === "offender"
                  ? (selectedScenario?.name || "피싱범")
                  : (selectedCharacter?.name || "피해자");
              const side = role === "offender" ? "left" : "right";
              const ts = new Date().toLocaleTimeString();

              addChat(role, content, ts, label, side, {
                run: roundNo,
                turn: idx,
              });
            });
          }
        }
        else if (event.type === "new_message") {
          // 중복 방지
          const role = (evt.role || "offender").toLowerCase();
          const key = `${evt.round}:${evt.turn_index}:${role}`;
          if (seenTurnsRef.current.has(key)) {
            continue;
          }
          seenTurnsRef.current.add(key);

          // 내용 정리 (victim의 ```json``` 포함 케이스)
          const raw = evt.content || "";
          const content = extractDialogueOrPlainText(raw);

          const label =
            role === "offender"
              ? (selectedScenario?.name || "피싱범")
              : (selectedCharacter?.name || "피해자");

          const side = role === "offender" ? "left" : "right";
          const ts = evt.created_kst
            ? new Date(evt.created_kst).toLocaleTimeString()
            : new Date().toLocaleTimeString();

          // 바로 대화창에 append
          addChat(role, content, ts, label, side, {
            run: evt.round,
            turn: evt.turn_index,
          });

          // 스피너 감추기 / 진행중 표시
          setSimulationState("RUNNING");
          setProgress((p) => Math.min(100, p + 1));
        }
        
        else if (event.type === "judgement") {
          addSystem(`라운드 ${evt.round} 판정: ${evt.phishing ? "피싱 성공" : "피싱 실패"} - ${evt.reason}`);
        }
        
        else if (event.type === "guidance_generated") {
          addSystem(`라운드 ${evt.round} 지침 생성: ${evt.guidance?.categories?.join(", ") || "N/A"}`);
        }
        
        else if (event.type === "complete") {
          setProgress(100);
          setSimulationState("IDLE");
          setShowReportPrompt(true);
          addSystem("시뮬레이션 완료!");
          
          // 최종 데이터 조회
          if (caseId) {
            const bundle = await getConversationBundle(caseId);
            setDefaultCaseData(bundle);
            setSessionResult((prev) => ({
              ...(prev || {}),
              phishing: bundle.phishing,
              evidence: bundle.evidence,
              totalTurns: bundle.total_turns,
              preview: bundle.preview,
            }));
          }
        }
      }
    
      if (!caseId) {
        throw new Error("case_id를 받지 못했습니다.");
      }

    } catch (err) {
      console.error("SSE 스트리밍 실패:", err);
      addSystem(`시뮬레이션 실패: ${err.message}`);
      setSimulationState("IDLE");
    } finally {
      streamingRef.current = false;
    }
  };

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
    addSystem,
    addChat,

    sessionResult,
    resetToSelection,
    startSimulation,

    scenarios,
    characters,
    scrollContainerRef,
    defaultCaseData,
    dataLoading,
    dataError,
    currentCaseId,

    showReportPrompt,
    setShowReportPrompt,
    hasInitialRun,

    progress,
    setProgress,

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
        <ReportPage {...pageProps} defaultCaseData={defaultCaseData} />
      )}
    </div>
  );
};

export default App;
