// src/App.jsx
import React, { useEffect, useLayoutEffect, useRef, useState } from "react";
import LandingPage from "./LandingPage";
import SimulatorPage from "./SimulatorPage";
import ReportPage from "./ReportPage";

/* ================== 색상 토큰 (원래 코드 유지) ================== */
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

/* ================== 설정(필수 확인) ================== */
/*
  ▶ API_BASE: 로컬백엔드 주소 (변경 금지: 로컬 개발시는 아래 상태 유지)
  ▶ API_PREFIX:
     - 만약 FastAPI에서 include_router(router, prefix="/api")로 등록했다면 "/api"
     - 라우터를 루트에 등록했다면 "" (빈 문자열)
*/
const API_BASE = "http://localhost:8000";
const API_PREFIX = "/api"; // ← 필요하면 ""로 바꿔주세요

/* ================== 공통 fetch 유틸 (timeout, JSON 파싱, 오류 처리) ================== */
async function fetchWithTimeout(
  url,
  { method = "GET", headers = {}, body = null, timeout = 100000 } = {}
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

/* ================== 백엔드 라우트별 헬퍼 ================== */
async function getOffenders() {
  return fetchWithTimeout(`${API_BASE}${API_PREFIX}/offenders/`);
}
async function getOffender(offenderId) {
  return fetchWithTimeout(
    `${API_BASE}${API_PREFIX}/offenders/${encodeURIComponent(offenderId)}`
  );
}
async function getVictims() {
  return fetchWithTimeout(`${API_BASE}${API_PREFIX}/victims`);
}
async function getVictim(victimId) {
  return fetchWithTimeout(
    `${API_BASE}${API_PREFIX}/victims/${encodeURIComponent(victimId)}`
  );
}
async function getCaseFull(caseId) {
  return fetchWithTimeout(
    `${API_BASE}${API_PREFIX}/${encodeURIComponent(caseId)}/full`
  );
}
async function getConversationBundle(caseId) {
  return fetchWithTimeout(
    `${API_BASE}${API_PREFIX}/conversations/${encodeURIComponent(caseId)}`
  );
}

// ✅ run_async 킥 (잡 시작)
async function runConversationAsync(offenderId, victimId, payload = {}) {
  return fetchWithTimeout(
    `${API_BASE}${API_PREFIX}/conversations/run_async/${encodeURIComponent(
      offenderId
    )}/${encodeURIComponent(victimId)}`,
    {
      method: "POST",
      body: payload, // fetchWithTimeout가 JSON.stringify 해줌
      timeout: 30000,
    }
  );
}

// ✅ 잡 상태 조회
async function getJobStatus(jobId) {
  return fetchWithTimeout(
    `${API_BASE}${API_PREFIX}/conversations/job/${encodeURIComponent(jobId)}`,
    { timeout: 15000 }
  );
}

// ✅ tail(증분) 조회
async function getConversationTail(caseId, afterTurnIndex = -1) {
  return fetchWithTimeout(
    `${API_BASE}${API_PREFIX}/conversations/${encodeURIComponent(
      caseId
    )}/tail?after=${afterTurnIndex}`,
    { timeout: 20000 }
  );
}

// (참고) 동기 전체 실행 버전 (남겨둠)
// async function runConversation(offenderId, victimId, payload = {}) {
//   return fetchWithTimeout(
//     `${API_BASE}${API_PREFIX}/conversations/run/${encodeURIComponent(
//       offenderId
//     )}/${encodeURIComponent(victimId)}`,
//     {
//       method: "POST",
//       headers: { "Content-Type": "application/json" },
//       body: JSON.stringify(payload),
//       timeout: 240000,
//     }
//   );
// }

/* ================== App 컴포넌트 (전체 통합) ================== */
const App = () => {
  const [currentPage, setCurrentPage] = useState("landing");

  // 데이터(서버에서 로드)
  const [scenarios, setScenarios] = useState([]); // backend의 offenders를 사용
  const [characters, setCharacters] = useState([]); // backend의 victims를 사용
  const [defaultCaseData, setDefaultCaseData] = useState(null);

  // 선택 및 시뮬레이션 상태
  const [selectedScenario, setSelectedScenario] = useState(null);
  const [selectedCharacter, setSelectedCharacter] = useState(null);
  const [simulationState, setSimulationState] = useState("IDLE");
  const [messages, setMessages] = useState([]);
  const [sessionResult, setSessionResult] = useState(null);
  const [progress, setProgress] = useState(0);
  const [agentModalVisible, setAgentModalVisible] = useState(false);
  const [agentUsed, setAgentUsed] = useState(null);
  const scrollContainerRef = useRef(null);

  // UI 로딩/에러
  const [dataLoading, setDataLoading] = useState(true);
  const [dataError, setDataError] = useState(null);

  // ✅ 실시간 폴링 관련 상태/레퍼런스
  const [currentCaseId, setCurrentCaseId] = useState(null);
  const jobPollRef = useRef(null);
  const tailPollRef = useRef(null);
  const lastTurnRef = useRef(-1);

  // (기존) 인터벌 클린업용 ref (시뮬레이터 재생용)
  const simIntervalRef = useRef(null);

  /* --------- 메시지 추가 유틸 --------- */
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
    sender, // "offender" | "victim"
    content,
    timestamp = null,
    senderLabel = null, // 화면에 표시될 이름
    side = null // "left" | "right"
  ) =>
    setMessages((prev) => [
      ...prev,
      {
        type: "chat",
        sender, // 정렬/스타일 기준
        senderLabel: senderLabel ?? sender, // 실제 표시 텍스트
        senderName: senderLabel ?? sender, // 혹시 컴포넌트가 senderName을 볼 때 대비
        side: side ?? (sender === "offender" ? "left" : "right"),
        content,
        timestamp: timestamp ?? new Date().toLocaleTimeString(),
      },
    ]);

  /* --------- 스크롤 자동 하단 고정 --------- */
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

  /* --------- 초기 데이터 로드 --------- */
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

        // 선택: 기본 케이스 불러오기
        // const maybeDefault = await getCaseFull(defaultCaseId);
        // setDefaultCaseData(maybeDefault ?? null);
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

  /* --------- (옵션) 서버에서 한 번에 받은 logs를 재생 --------- */
  const runSimulation = (caseObj = null) => {
    const data = caseObj ?? defaultCaseData;
    if (!data || !Array.isArray(data.logs) || data.logs.length === 0) {
      addSystem("대화 JSON(logs)이 없습니다.");
      return;
    }

    const logs = data.logs;
    setMessages([]);
    setProgress(0);
    setSimulationState("RUNNING");

    if (simIntervalRef.current) {
      clearInterval(simIntervalRef.current);
      simIntervalRef.current = null;
    }

    let i = 0;
    const total = logs.length;

    const interval = setInterval(() => {
      if (i >= total) {
        clearInterval(interval);
        simIntervalRef.current = null;
        finishSimulation();
        return;
      }

      const log = logs[i];
      const role = (log.role || "").toLowerCase();
      const offenderLabel =
        log.offender_name ||
        (selectedScenario ? `피싱범${selectedScenario.id}` : "피싱범");
      const victimLabel =
        log.victim_name ||
        (selectedCharacter ? `피해자${selectedCharacter.id}` : "피해자");
      const displayLabel = role === "offender" ? offenderLabel : victimLabel;
      const side = role === "offender" ? "left" : "right";

      const ts =
        log.created_kst && typeof log.created_kst === "string"
          ? new Date(log.created_kst).toLocaleTimeString()
          : log.created_kst;

      if (
        role === "analysis" ||
        role === "system" ||
        log.label === "analysis"
      ) {
        addAnalysis(log.content ?? "");
      } else {
        addChat(role || "offender", log.content ?? "", ts, displayLabel, side);
      }

      setProgress(((i + 1) / total) * 100);
      i += 1;
    }, 700);

    simIntervalRef.current = interval;
  };

  const finishSimulation = () => {
    setSimulationState("FINISH");
    setSessionResult((prev) =>
      prev ?? {
        isPhishing: true,
        technique: "기관사칭",
        confidence: 95,
      }
    );
  };

  /* ========= 실시간 폴링 로직 (job → case_id → tail) ========== */

  // tail 폴링 시작
  const startTailPolling = (caseId) => {
    if (tailPollRef.current) clearInterval(tailPollRef.current);
    lastTurnRef.current = -1;
    setSimulationState("RUNNING");
    setMessages([]);
    setProgress(0);

    tailPollRef.current = setInterval(async () => {
      try {
        const bundle = await getConversationTail(caseId, lastTurnRef.current);
        const newLogs = bundle?.logs ?? [];
        const totalTurns = bundle?.total_turns ?? null;

        if (newLogs.length) {
          newLogs.forEach((log) => {
            const role = (log.role || "").toLowerCase(); // "offender" | "victim"
            const offenderLabel =
              log.offender_name ||
              (selectedScenario ? `피싱범${selectedScenario.id}` : "피싱범");
            const victimLabel =
              log.victim_name ||
              (selectedCharacter ? `피해자${selectedCharacter.id}` : "피해자");
            const displayLabel = role === "offender" ? offenderLabel : victimLabel;
            const side = role === "offender" ? "left" : "right";

            const ts =
              log.created_kst && typeof log.created_kst === "string"
                ? new Date(log.created_kst).toLocaleTimeString()
                : log.created_kst;

            if (role === "analysis" || role === "system" || log.label === "analysis") {
              addAnalysis(log.content ?? "");
            } else {
              addChat(role || "offender", log.content ?? "", ts, displayLabel, side);
            }

            if (typeof log.turn_index === "number") {
              lastTurnRef.current = Math.max(lastTurnRef.current, log.turn_index);
            }
          });

          // 간단 프로그레스 계산(추정)
          if (typeof totalTurns === "number" && totalTurns >= 0) {
            const pct = Math.min(
              100,
              ((lastTurnRef.current + 1) / Math.max(1, totalTurns)) * 100
            );
            setProgress(pct);
          } else {
            setProgress((p) => Math.min(100, p + newLogs.length * 2));
          }
        }

        // 완료 판단
        if (
          typeof totalTurns === "number" &&
          totalTurns >= 0 &&
          lastTurnRef.current + 1 >= totalTurns
        ) {
          clearInterval(tailPollRef.current);
          tailPollRef.current = null;
          finishSimulation();
        }
      } catch (e) {
        console.warn("tail 폴링 실패:", e);
      }
    }, 1200);
  };

  // job 폴링 시작
const startJobPolling = (jobId) => {
  if (jobPollRef.current) clearInterval(jobPollRef.current);

  jobPollRef.current = setInterval(async () => {
    try {
      const st = await getJobStatus(jobId);
      if (!st) return;

      if (st.status === "error") {
        clearInterval(jobPollRef.current);
        jobPollRef.current = null;
        addSystem(`시뮬레이션 실패: ${st.error || "알 수 없는 오류"}`);
        setSimulationState("IDLE");
      } else if (st.status === "done" && st.case_id) {
        clearInterval(jobPollRef.current);
        jobPollRef.current = null;
        setCurrentCaseId(st.case_id);

        try {
          // ✅ 완료된 case_id 로 전체 로그 가져오기
          const full = await getConversationBundle(st.case_id);
          if (!full || !Array.isArray(full.logs)) {
            addSystem("대화 로그를 불러오지 못했습니다.");
            setSimulationState("IDLE");
            return;
          }

          // ✅ runSimulation 으로 ‘재생’ 실행
          runSimulation({
            logs: full.logs,
            case: {
              id: full.case_id,
              phishing: full.phishing,
              evidence: full.evidence,
            },
          });

          // ✅ 세션 결과 저장
          setSessionResult({
            phishing: full.phishing,
            isPhishing: full.phishing, // (호환용)
            evidence: full.evidence,
            totalTurns: full.total_turns,
            agentUsed, // 있으면 함께 저장
          });
        } catch (err) {
          console.error("로그 조회 실패:", err);
          addSystem("대화 로그 로딩 중 오류가 발생했습니다.");
          setSimulationState("IDLE");
        }
      } else if (st.status === "not_found") {
        clearInterval(jobPollRef.current);
        jobPollRef.current = null;
        addSystem("작업을 찾을 수 없습니다. 다시 시도해주세요.");
        setSimulationState("IDLE");
      }
      // running일 때는 그대로 폴링 유지
    } catch (e) {
      console.warn("job 폴링 실패:", e);
    }
  }, 1200);
};

  /* --------- startSimulation: run_async → job 폴링 → tail 폴링 --------- */
  const startSimulation = async () => {
    if (!selectedScenario || !selectedCharacter) {
      addSystem("시나리오와 캐릭터를 먼저 선택해주세요.");
      return;
    }
    if (agentUsed === null) {
      addSystem("먼저 AI 에이전트 사용 여부를 선택해주세요.");
      return;
    }

    // 기존 인터벌 정리
    if (simIntervalRef.current) {
      clearInterval(simIntervalRef.current);
      simIntervalRef.current = null;
    }
    if (jobPollRef.current) clearInterval(jobPollRef.current);
    if (tailPollRef.current) clearInterval(tailPollRef.current);

    setSimulationState("PREPARE");
    setMessages([]);
    setProgress(0);
    setSessionResult(null);
    setCurrentCaseId(null);
    lastTurnRef.current = -1;

    addSystem(
      `시뮬레이션 준비 완료\n시나리오: ${selectedScenario.name}\n피해자: ${selectedCharacter.name}`
    );

    try {
      const payload = {
        include_judgement: true,
        max_turns: 200,
        agent_mode: agentUsed ? "admin" : "off",
      };

      const kick = await runConversationAsync(
        selectedScenario.id,
        selectedCharacter.id,
        payload
      );

      if (!kick || !kick.job_id) {
        addSystem("시뮬레이션 시작 실패: job_id를 받지 못했습니다.");
        setSimulationState("IDLE");
        return;
      }

      startJobPolling(kick.job_id);
    } catch (err) {
      console.error("시뮬레이션 실행 실패:", err);
      addSystem("시뮬레이션 실행 실패 (콘솔 로그 확인).");
      setSimulationState("IDLE");
    }
  };

  /* --------- 리셋 및 유틸 --------- */
  const resetToSelection = () => {
    setSelectedScenario(null);
    setSelectedCharacter(null);
    setMessages([]);
    setSessionResult(null);
    setProgress(0);
    setSimulationState("IDLE");
    setAgentUsed(null);
    setAgentModalVisible(false);
    setCurrentPage("simulator");

    if (simIntervalRef.current) {
      clearInterval(simIntervalRef.current);
      simIntervalRef.current = null;
    }
    if (jobPollRef.current) {
      clearInterval(jobPollRef.current);
      jobPollRef.current = null;
    }
    if (tailPollRef.current) {
      clearInterval(tailPollRef.current);
      tailPollRef.current = null;
    }
    lastTurnRef.current = -1;
    setCurrentCaseId(null);
  };

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
      if (tailPollRef.current) {
        clearInterval(tailPollRef.current);
        tailPollRef.current = null;
      }
    };
  }, []);

  /* --------- 페이지에 전달할 props --------- */
  const pageProps = {
    COLORS,
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
    progress,
    resetToSelection,
    startSimulation,
    scenarios,
    characters,
    agentModalVisible,
    setAgentModalVisible,
    setAgentUsed,
    scrollContainerRef,
    defaultCaseData,
    dataLoading,
    dataError,
    currentCaseId, // 필요시 다른 컴포넌트에서 사용
  };

  /* --------- 렌더 --------- */
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
