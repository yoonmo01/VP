// src/App.jsx (개선 버전)
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
    opts.headers["Content-Type"] = opts.headers["Content-Type"] || "application/json";
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
  return fetchWithTimeout(`${API_ROOT}/conversations/${encodeURIComponent(caseId)}`);
}

async function getPersonalizedForCase(caseId) {
  return fetchWithTimeout(`${API_ROOT}/personalized/by-case/${encodeURIComponent(caseId)}`, { timeout: 200000 });
}

// ✅ SSE 스트리밍 (개선)
async function* streamReactSimulation(params) {
  const qs = new URLSearchParams(params).toString();
  const response = await fetch(
    `${API_ROOT}/react-agent/simulation/stream?${qs}`,
    { method: "GET", headers: { Accept: "text/event-stream" } }
  );

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        try {
          const data = JSON.parse(line.slice(6).trim());
          yield data;
        } catch (e) {
          console.warn("SSE 파싱 실패:", line);
        }
      }
    }
  }
}

// ✅ 메시지 내용 정리 (JSON 파싱)
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
  return cleaned.replace(/[ \t]+/g, " ").replace(/\s*\n\s*/g, "\n").trim();
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
  const [simulationState, setSimulationState] = useState("IDLE");
  const [messages, setMessages] = useState([]);
  const [sessionResult, setSessionResult] = useState(null);
  const [progress, setProgress] = useState(0);

  // modal / decision flags
  const [showReportPrompt, setShowReportPrompt] = useState(false);
  const [hasInitialRun, setHasInitialRun] = useState(false);

  // refs
  const scrollContainerRef = useRef(null);

  // UI loading/error
  const [dataLoading, setDataLoading] = useState(true);
  const [dataError, setDataError] = useState(null);
  const [currentCaseId, setCurrentCaseId] = useState(null);

  /* 메시지 추가 유틸 */
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

  /* 스크롤 자동 하단 고정 */
  const stickToBottom = () => {
    const el = scrollContainerRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  };

  useLayoutEffect(() => {
    stickToBottom();
  }, [messages]);

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

  /* ✅ startSimulation - 실시간 SSE 처리 (개선) */
  const startSimulation = async () => {
    if (!selectedScenario || !selectedCharacter) {
      addSystem("시나리오와 캐릭터를 먼저 선택해주세요.");
      return;
    }

    setHasInitialRun(true);
    setSimulationState("PREPARE");
    setMessages([]);
    setProgress(0);
    setSessionResult(null);
    setCurrentCaseId(null);
    setShowReportPrompt(false);

    addSystem(`시뮬레이션 시작: ${selectedScenario.name} / ${selectedCharacter.name}`);

    try {
      const params = {
        victim_id: selectedCharacter.id,
        offender_id: selectedScenario.id,
        use_tavily: false,
        turns_per_round: 15,
        max_rounds: 5,
      };

      let caseId = null;
      const totalRounds = Number(params.max_rounds) || 5;
      let currentRound = 0;
      let turnCount = 0;

      setSimulationState("RUNNING");

      for await (const event of streamReactSimulation(params)) {
        console.log("[SSE Event]", event);

        if (event.type === "error") {
          throw new Error(event.message || "시뮬레이션 오류");
        }

        else if (event.type === "case_created") {
          caseId = event.case_id;
          setCurrentCaseId(caseId);
          addSystem(`케이스 생성: ${caseId}`);
        }
        
        else if (event.type === "round_start") {
          currentRound = event.round;
          addSystem(`📍 라운드 ${currentRound} 시작`);
          setProgress((currentRound / totalRounds) * 100);
        }

        // ✅ 핵심: new_message 이벤트로 실시간 대화 표시
        else if (event.type === "new_message") {
          turnCount++;
          
          const role = (event.role || "offender").toLowerCase();
          const rawContent = event.content || "";
          const content = extractDialogueOrPlainText(rawContent);

          const label = role === "offender"
            ? (selectedScenario?.name || "피싱범")
            : (selectedCharacter?.name || "피해자");

          const side = role === "offender" ? "left" : "right";
          const timestamp = event.created_kst
            ? new Date(event.created_kst).toLocaleTimeString()
            : new Date().toLocaleTimeString();

          // ✅ 즉시 화면에 추가
          addChat(role, content, timestamp, label, side, {
            run: event.round,
            turn: event.turn_index,
          });

          // 진행률 업데이트 (턴 기반)
          const estimatedTotalTurns = totalRounds * (params.turns_per_round || 15);
          setProgress(Math.min(95, (turnCount / estimatedTotalTurns) * 100));
        }

        // conversation_logs는 백업용으로만 사용 (누락 방지)
        else if (event.type === "conversation_logs") {
          // new_message로 이미 처리했으므로 건너뛰기
          console.log(`[Backup] 라운드 ${event.round} 로그 수신 (${event.logs?.length || 0}개)`);
        }
        
        else if (event.type === "round_complete") {
          addSystem(`✅ 라운드 ${event.round} 완료`);
        }
        
        else if (event.type === "judgement") {
          addSystem(
            `⚖️ 라운드 ${event.round} 판정: ${event.phishing ? "피싱 성공" : "피싱 실패"} - ${event.reason}`
          );
        }
        
        else if (event.type === "guidance_generated") {
          addSystem(
            `💡 라운드 ${event.round} 지침 생성 완료`
          );
        }
        
        else if (event.type === "complete") {
          setProgress(100);
          setSimulationState("IDLE");
          setShowReportPrompt(true);
          addSystem("🎉 시뮬레이션 완료!");
          
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
      addSystem(`❌ 시뮬레이션 실패: ${err.message}`);
      setSimulationState("IDLE");
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

  /* pageProps */
  const pageProps = {
    COLORS,
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

  function getVictimImage(photoPath) {
    if (!photoPath) return null;
    try {
      const fileName = photoPath.split("/").pop();
      if (fileName)
        return new URL(`./assets/victims/${fileName}`, import.meta.url).href;
    } catch (e) {
      console.warn("이미지 로드 실패:", e);
    }
    return null;
  }

  return (
    <div className="font-sans">
      {currentPage === "landing" && (
        <LandingPage setCurrentPage={setCurrentPage} />
      )}
      {currentPage === "simulator" && <SimulatorPage {...pageProps} />}
      {currentPage === "report" && (
        <ReportPage
          {...pageProps}
          apiRoot={API_ROOT}
          defaultCaseData={defaultCaseData}
        />
      )}
    </div>
  );
};

export default App;