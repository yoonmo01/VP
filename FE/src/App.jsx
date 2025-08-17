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
  { method = "GET", headers = {}, body = null, timeout = 10000 } = {},
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
    `${API_BASE}${API_PREFIX}/offenders/${encodeURIComponent(offenderId)}`,
  );
}
async function getVictims() {
  return fetchWithTimeout(`${API_BASE}${API_PREFIX}/victims`);
}
async function getVictim(victimId) {
  return fetchWithTimeout(
    `${API_BASE}${API_PREFIX}/victims/${encodeURIComponent(victimId)}`,
  );
}
async function getCaseFull(caseId) {
  return fetchWithTimeout(
    `${API_BASE}${API_PREFIX}/${encodeURIComponent(caseId)}/full`,
  );
}
async function getConversationBundle(caseId) {
  return fetchWithTimeout(
    `${API_BASE}${API_PREFIX}/conversations/${encodeURIComponent(caseId)}`,
  );
}
async function runConversation(offenderId, victimId, payload = {}) {
  return fetchWithTimeout(
    `${API_BASE}${API_PREFIX}/run/${encodeURIComponent(offenderId)}/${encodeURIComponent(victimId)}`,
    {
      method: "POST",
      body: payload,
    },
  );
}

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

  // 인터벌 클린업용 ref
  const simIntervalRef = useRef(null);

  /* --------- 메시지 추가 유틸 (기존 로직과 호환) --------- */
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

  const addChat = (sender, content, timestamp = null, senderLabel = null) =>
    setMessages((prev) => [
      ...prev,
      {
        sender,
        senderLabel:
          senderLabel ??
          (sender === "offender"
            ? "피싱범"
            : sender === "victim"
              ? "피해자"
              : sender),
        content,
        timestamp: timestamp ?? new Date().toLocaleTimeString(),
      },
    ]);

  /* --------- 스크롤 자동 하단 고정 (원래 로직 유지) --------- */
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

  /* --------- 초기 데이터 로드: scenarios(offenders), characters(victims) --------- */
  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        setDataLoading(true);
        setDataError(null);

        // 병렬 로딩
        const [offList, vicList] = await Promise.all([
          getOffenders(),
          getVictims(),
        ]);
        if (!mounted) return;

        // backend가 배열을 반환한다고 가정
        setScenarios(Array.isArray(offList) ? offList : []);
        setCharacters(Array.isArray(vicList) ? vicList : []);

        // 선택적: 기본 케이스를 서버에서 가져올 경우 아래 주석을 풀어 사용 가능
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

  /* --------- 시뮬레이션: logs를 받아 차례대로 렌더링 --------- */
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
      const displayLabel =
        role === "offender"
          ? "피싱범"
          : role === "victim"
            ? "피해자"
            : log.offender_name || log.victim_name || "상대";

      // created_kst 가 문자열이면 Date로 변환(안정성)
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
        addChat(role || displayLabel, log.content ?? "", ts, displayLabel);
      }

      setProgress(((i + 1) / total) * 100);
      i += 1;
    }, 700);

    simIntervalRef.current = interval;
  };

  const finishSimulation = () => {
    setSimulationState("FINISH");
    // 기본 결과값 (필요시 서버에서 받은 결과로 대체 가능)
    setSessionResult({
      isPhishing: true,
      technique: "기관사칭",
      confidence: 95,
    });
  };

  /* --------- startSimulation: 서버에 run 요청 후 받은 logs로 runSimulation 호출 --------- */
  const startSimulation = async () => {
    if (!selectedScenario || !selectedCharacter) {
      addSystem("시나리오와 캐릭터를 먼저 선택해주세요.");
      return;
    }
    if (agentUsed === null) {
      addSystem("먼저 AI 에이전트 사용 여부를 선택해주세요.");
      return;
    }

    setSimulationState("PREPARE");
    addSystem(
      `시뮬레이션 준비 완료\n시나리오: ${selectedScenario.name}\n피해자: ${selectedCharacter.name}`,
    );

    try {
      // payload는 backend의 ConversationRunRequest 스펙에 맞게 조정하세요
      const payload = {
        include_judgement: true,
        max_turns: 200,
        agent_mode: agentUsed ? "on" : "off",
      };

      const res = await runConversation(
        selectedScenario.id,
        selectedCharacter.id,
        payload,
      );

      // 예상 응답: { case_id, total_turns, logs: [...], phishing, evidence }
      if (!res || !Array.isArray(res.logs)) {
        addSystem("서버에서 로그를 받지 못했습니다.");
        return;
      }

      // 서버 로그로 시뮬레이션 실행
      runSimulation({
        logs: res.logs,
        case: {
          id: res.case_id,
          phishing: res.phishing,
          evidence: res.evidence,
        },
      });

      // 판단 결과 UI에 사용하기 위해 세팅
      setSessionResult({
        phishing: res.phishing,
        evidence: res.evidence,
        totalTurns: res.total_turns,
      });
    } catch (err) {
      console.error("시뮬레이션 실행 실패:", err);
      addSystem("시뮬레이션 실행 실패 (콘솔 로그 확인).");
    }
  };

  /* --------- 리셋 및 유틸 함수들 (기존 로직 유지) --------- */
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
  };

  useEffect(() => {
    return () => {
      if (simIntervalRef.current) {
        clearInterval(simIntervalRef.current);
        simIntervalRef.current = null;
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
