// src/SimulatorPage.jsx
import { useState, useMemo, useEffect, useRef } from "react";
import { Play, Clock, Check, AlertTriangle, FileBarChart2, Terminal, Lightbulb } from "lucide-react";
import HudBar from "./HudBar";
import Badge from "./Badge";
import SelectedCard from "./SelectedCard";
import Chip from "./Chip";
import MessageBubble from "./MessageBubble";
import SpinnerMessage from "./SpinnerMessage";
import CustomCharacterCreate from "./CustomCharacterCreate";
import InvestigationBoard from "./InvestigationBoard";
import TTSModal from "./components/TTSModal";
import { THEME as BASE_THEME } from "./constants/colors";
import CustomScenarioButton from "./CustomScenarioButton";
import CustomScenarioModal from "./CustomScenarioModal";
import TerminalLog from "./components/TerminalLog";

const getVictimImage = (photoPath) => {
  if (!photoPath) return null;
  try {
    const fileName = photoPath.split("/").pop();
    if (fileName)
      return new URL(`./assets/victims/${fileName}`, import.meta.url).href;
  } catch (error) {
    console.warn("이미지 로드 실패:", error);
  }
  return null;
};

const countChatMessages = (messages = []) =>
  Array.isArray(messages)
    ? messages.filter((m) => (m?.type ?? m?._kind) === "chat").length
    : 0;

const SimulatorPage = ({
  COLORS,
  setCurrentPage,
  selectedScenario,
  setSelectedScenario,
  selectedCharacter,
  setSelectedCharacter,
  simulationState,
  messages,
  sessionResult,
  progress,
  setProgress, // 반드시 App에서 전달하세요
  resetToSelection,
  startSimulation,
  startAgentRun,
  declineAgentRun,
  scenarios,
  characters,
  scrollContainerRef,
  addSystem,
  pendingAgentDecision,
  showReportPrompt,
  setShowReportPrompt,
  hasInitialRun,
  hasAgentRun,
  agentRunning,
  victimImageUrl,
  agentVerbose, // ← 추가
  setAgentVerbose, // ← 추가

  // ⏱️ 조절 가능한 지연(초) - 두 번째 코드에서 가져옴
  boardDelaySec = 3,      // 오른쪽 보드 "내용" 등장 지연
  intermissionSec = 3,    // 두 번째 대화 직전 스피너 노출 시간
}) => {
  const needScenario = !selectedScenario;
  const needCharacter = !selectedCharacter;
  const [selectedTag, setSelectedTag] = useState(null);
  const [open, setOpen] = useState(false);

  // 커스텀 시나리오 관리
  const [customScenarios, setCustomScenarios] = useState([]);
  const [showCustomModal, setShowCustomModal] = useState(false);

  //커스텀 캐릭터
  const [customVictims, setCustomVictims] = useState([]);

  //수사보드 스위치 - 첫 번째 코드에서 가져옴
  const [activeAgentTab, setActiveAgentTab] = useState("log"); // "log" | "analysis"

  //에이전트 로그 - 첫 번째 코드에서 가져옴
  const agentLogText = `
Thought: 라운드 1을 시작하기 위해 시나리오와 피해자 정보를 확보해야 합니다. Action: sim.fetch_entities Action Input: {"data": {"offender_id": 1, "victim_id": 1, "scenario": {}}} {'scenario': {'steps': ['보이스피싱 조직원(1)이 금융기관 직원 사칭하여 피해자에게 전화(저금리 대출을 제안)', '저금리대출 제안하고 피해자의 대출 신청 유도함', '보이스피싱 조직원(2)이 피해자가 기존에 대출 받은 금융기관 직원을 사칭하여 다시 전화 걺', '기존 대출금 상환 요구', '피해자로부터 현금 혹은 계좌 송금을 통하여 돈을 교부받음'], 'purpose': '저금리 대출유도 후 기존 대출받은 기관 사칭하여 대출금 편취'}, 'victim_profile': {'meta': {'age': 47, 'gender': '남', 'address': '대전', 'education': '대졸'}, 'knowledge': {'competencies': [], 'comparative_notes': ['연령 대비(30대 제외) 금융이해력 높음', '디지털금융이해력은 20·30대를 제외하면 타 연령대보다 높음', '온라인 거래 시 웹사이트 보안 이해 높음', '온라인 공유 개인정보 활용 이해 높음']}, 'traits': {'ocean': {'openness': '높음', 'neuroticism': '낮음', 'extraversion': '낮음', 'agreeableness': '높음', 'conscientiousness': '낮음'}, 'vulnerability_notes': ['신경성 낮고 외향성 낮고 개방성 높고 친화성 높아 안전한 면도 존재하지만 성실성이 낮아 보이스피싱에 취약한 면']}}}Thought: 시나리오와 피해자 프로필을 바탕으로 프롬프트를 생성해야 합니다. Action: sim.compose_prompts Action Input: {"data": {"scenario": {"steps": ["보이스피싱 조직원(1)이 금융기관 직원 사칭하여 피해자에게 전화(저금리 대출을 제안)", "저금리대출 제안하고 피해자의 대출 신청 유도함", "보이스피싱 조직원(2)이 피해자가 기존에 대출 받은 금융기관 직원을 사칭하여 다시 전화 걺", "기존 대출금 상환 요구", "피해자로부터 현금 혹은 계좌 송금을 통하여 돈을 교부받음"], "purpose": "저금리 대출유도 후 기존 대출받은 기 관 사칭하여 대출금 편취"}, "victim_profile": {"meta": {"age": 47, "gender": "남", "address": "대전", "education": "대졸"}, "knowledge": {"competencies": [], "comparative_notes": ["연령 대비(30대 제외) 금융이해력 높음", "디지털금융이해력은 20·30대를 제외하면 타 연령대보다 높음", "온라인 거래 시 웹사이트 보안 이해 높음", "온라인 공유 개인정보 활용 이해 높음"]}, "traits": {"ocean": {"openness": "높음", "neuroticism": "낮음", "extraversion": "낮음", "agreeableness": "높음", "conscientiousness": "낮음"}, "vulnerability_notes": ["신경성 낮고 외향성 낮고 개방성 높고 친화성 높아 안전한 면도 존재하지만 성실성이 낮아 보이스피싱에 취약한 면"]}}}}{'attacker_prompt': "[보이스피싱 시뮬레이션]\n[규칙] 실제 기관/계좌/번호는 금지(가명 사용). 앱 설치/링크 요구는 명시적으로만 표현.\n[시나리오]\n{'steps': ['보이스피싱 조직원(1)이 금융기관 직원 사칭하여 피해자에게 전화(저금리 대출을 제안)', '저금리대출 제안하고 피해자의 대출 신청 유도함', '보이스피싱 조직원(2)이 피해자가 기존에 대출 받은 금융기관 직원을 사칭하여 다시 전화 걺', '기존 대출금 상환 요구', '피해자로부터 현금 혹은 계좌 송금을 통하여 돈을 교부받음'], 'purpose': '저금리 대출유도 후 기존 대출받은 기관 사칭하여 대출금 편취'}\n[역할] 너는 공격자다.", 'victim_prompt': "[보이스피싱 시뮬레이션]\n[규칙] 실제 기관/계좌/번호는 금지(가명 사용). 앱 설치/링크 요구는 명시적으로만 표현.\n[피해자 프로파일]\n메타: {'age': 47, 'gender': '남', 'address': '대전', 'education': '대졸'}\n지식: {'competencies': [], 'comparative_notes': ['연령 대비(30대 제외) 금융이해력 높음', '디지털금융이해력은 20·30대를 제외하면 타 연령대보다 높 음', '온라인 거래 시 웹사이트 보안 이해 높음', '온라인 공유 개인정보 활용 이해 높음']}\n성격: {'ocean': {'openness': '높음', 'neuroticism': '낮음', 'extraversion': '낮음', 'agreeableness': '높음', 'conscientiousness': '낮음'}, 'vulnerability_notes': ['신경성 낮고 외향성 낮고 개방성 높고 친화성 높아 안전한 면도 존재하지만 성실성이 낮아 보이스피싱에 취약한 면']}\n\n[역할] 너는 피해자다."}Thought: 시뮬레이션을 실행하여 첫 번째 라운드를 진행해야 합니다. Action: mcp.simulator_run Action Input: {"data": {"offender_id": 1, "victim_id": 1, "scenario": {"steps": ["보이스피싱 조직원(1)이 금융기관 직원 사칭하여 피해자에게 전화(저금리 대출을 제안)", "저금리대출 제안하고 피해자의 대출 신청 유도함", "보이스피싱 조직원(2)이 피해자가 기존에 대출 받은 금융기관 직원을 사칭하여 다시 전화 걺", "기존 대출금 상환 요구", "피해자로부터 현금 혹은 계좌 송금을 통하여 돈을 교부받음"], "purpose": " 저금리 대출유도 후 기존 대출받은 기관 사칭하여 대출금 편취"}, "victim_profile": {"meta": {"age": 47, "gender": "남", "address": "대전", "education": "대졸"}, "knowledge": {"competencies": [], "comparative_notes": ["연령 대비(30대 제외) 금융이해력 높음", "디지털금융이해력은 20·30대를 제외하면 타 연령대보다 높음", "온라인 거래 시 웹사이트 보안 이해 높음", "온라인 공유 개인정보 활용 이해 높음"]}, "traits": {"ocean": {"openness": "높음", "neuroticism": "낮음", "extraversion": "낮음", "agreeableness": "높음", "conscientiousness": "낮음"}, "vulnerability_notes": ["신경성 낮고 외향성 낮고 개방성 높고 친화 성 높아 안전한 면도 존재하지만 성실성이 낮아 보이스피싱에 취약한 면"]}}, "templates": {"attacker_prompt": "[보이스피싱 시뮬레이션]\n[규칙] 실제 기관/계좌/번호는 금지(가명 사용). 앱 설치/링크 요구는 명시적으로만 표현.\n[시나리오]\n{'steps': ['보이스피싱 조직원(1)이 금융기관 직원 사칭하여 피해자에게 전화(저금리 대출을 제안)', '저금리대출 제안하고 피해자의 대출 신청 유도함', '보이스피싱 조직원(2)이 피해 자가 기존에 대출 받은 금융기관 직원을 사칭하여 다시 전화 걺', '기존 대출금 상환 요구', '피해자로부터 현금 혹은 계좌 송금을 통하여 돈을 교부받음'], 'purpose': '저금리 대출유도 후 기존 대출받은 기관 사칭 하여 대출금 편취'}\n[역할] 너는 공격자다.", "victim_prompt": "[보이스피싱 시뮬레이션]\n[규칙] 실제 기관/계좌/번호는 금지(가명 사용). 앱 설치/링크 요구는 명시적으로만 표현.\n[피해자 프로파일]\n메타: {'age': 47, 'gender': '남', 'address': '대전', 'education': '대졸'}\n지식: {'competencies': [], 'comparative_notes': ['연령 대비(30대 제외) 금융이해력 높음', '디지털금융이해력은 20·30대를 제외하면 타 연령대보다 높음', '온라인 거래 시 웹사이트 보안 이해 높음', '온라인 공유 개인정보 활용 이해 높음']}\n성격: {'ocean': {'openness': '높음', 'neuroticism': '낮음', 'extraversion': '낮음', 'agreeableness': '높음', 'conscientiousness': '낮음'}, 'vulnerability_notes': ['신경성 낮고 외향성 낮고 개방성 높고 친화성 높아 안전한 면도 존재하지만 성실성이 낮아 보이스피싱에 취약한 면']}\n\n[역할] 너는 피해자다."}, "max_turns": 10}} E0000 00:00:1758366115.269466 18256 alts_credentials.cc:93] ALTS creds ignored. Not running on GCP and untrusted ALTS is not enabled. [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:1][turn:0][offender] 안녕하세요, 고객님. 저는 OO은행 대출팀 직원입니다. 최근 저희 은행에서 고객님께 저금리 대출 상품을 우선적으로 안내해드리고 있는데요, 간단한 심사만 거치면 최대 1억 원까지 대출이 가능합니다. 지금 바로 상담 도와드려도 될까요? 2025-09-20 20:01:57,862 | INFO | [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:1][turn:0][offender] 안녕하세요, 고객님. 저는 OO은행 대출팀 직원입니다. 최근 저희 은행에서 고객님께 저금리 대출 상품을 우선적으로 안내해드리고 있는데요, 간단한 심사만 거치면 최대 1억 원까지 대출이 가능합니다. 지금 바로 상담 도와드려도 될까요? [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:1][turn:1][victim]
json { "is_convinced": 2, "thoughts": "(OO은행? 갑자기 대출이라니 좀 이상하네. 나한테 왜? 근데 1억이면 솔깃한데... 일 단 좀 더 들어보자.)", "dialogue": "네, OO은행이요? 제가 대출이 필요한 건 아닌데, 혹시 어떤 상품인지 좀 더 자세히 설명해주실 수 있나요?" }
2025-09-20 20:01:58,986 | INFO | [Conversation][case:239c9de5-711f-4d0e-ba6c-eb8321bd91f3][run:1][turn:1][victim]
json { "is_convinced": 2, "thoughts": "(OO은행? 갑자기 대출이라니 좀 이상하네. 나한테 왜? 근데 1억이면 솔깃한데... 일단 좀 더 들어보자.)", "dialogue": "네, OO은행이요? 제가 대출이 필요한 건 아닌데, 혹시 어떤 상품인지 좀 더 자세히 설명해주실 수 있나요?" }
`;

  // --- 디자인 변경: 더 어두운 경찰 엠블럼 느낌 팔레트로 강제 덮어쓰기 ---
  const THEME = {
    ...(COLORS ?? BASE_THEME),
    bg: "#030617", // 더 어두운 네이비 배경 (눈 부담 감소)
    panel: "#061329", // 더 어두운 딥 블루 패널
    panelDark: "#04101f", // 보조 패널 (어둡게)
    panelDarker: "#020812", // 가장 어두운 패널
    border: "#A8862A", // 낮춘 골드(액센트)
    text: "#FFFFFF",
    sub: "#BFB38A", // 낮춘 연한 골드/베이지 (눈 부담 감소)
    blurple: "#A8862A", // primary 역할 -> 어두운 골드
    success: COLORS?.success ?? "#57F287",
    warn: COLORS?.warn ?? "#FF4757",
    white: "#FFFFFF",
  };
  // -------------------------------------------------------------------

  const filteredScenarios = useMemo(() => {
    if (!selectedTag) return scenarios;
    return scenarios.filter(
      (s) =>
        s.type === selectedTag ||
        (Array.isArray(s.tags) && s.tags.includes(selectedTag)),
    );
  }, [selectedTag, scenarios]);

  // 기본 + 커스텀 목록 결합 (커스텀은 태그가 선택되어 있으면 그 태그만 보여줌)
  const combinedScenarios = useMemo(() => {
    const base = filteredScenarios ?? [];
    const custom = selectedTag
      ? customScenarios.filter((c) => c.type === selectedTag)
      : customScenarios;
    return [...base, ...custom];
  }, [filteredScenarios, customScenarios, selectedTag]);

  const handleSaveCustomScenario = (scenario) => {
    setCustomScenarios((prev) => [...prev, scenario]); // 맨 끝에 추가
    setShowCustomModal(false);
  };
  const handleCloseCustomModal = () => setShowCustomModal(false);

  const normalizeMessage = (m) => {
    if (m?.type === "system" || m?.type === "analysis") {
      return {
        ...m,
        _kind: m.type,
        label: m.type === "system" ? "시스템" : "분석",
        side: "center",
        timestamp: m.timestamp,
      };
    }

    const role = (m?.sender || m?.role || "").toLowerCase();
    const offenderLabel =
      m?.offender_name ||
      (selectedScenario ? `피싱범${selectedScenario.id}` : "피싱범");
    const victimLabel =
      m?.victim_name ||
      (selectedCharacter ? `피해자${selectedCharacter.id}` : "피해자");

    const label =
      m?.senderLabel ??
      m?.senderName ??
      (role === "offender"
        ? offenderLabel
        : role === "victim"
          ? victimLabel
          : "상대");

    const side =
      m?.side ??
      (role === "offender" ? "left" : role === "victim" ? "right" : "left");

    const ts =
      typeof m?.timestamp === "string"
        ? m.timestamp
        : typeof m?.created_kst === "string"
          ? new Date(m.created_kst).toLocaleTimeString()
          : (m?.timestamp ?? null);

    return {
      ...m,
      _kind: "chat",
      role,
      label,
      side,
      timestamp: ts,
    };
  };

  // 버튼 비활성 조건
  const startDisabled =
    simulationState === "PREPARE" ||
    simulationState === "RUNNING" ||
    pendingAgentDecision ||
    hasInitialRun;

  // --- 핵심: 진행률 재계산을 위한 ref/효과들 ---
  const initialChatCountRef = useRef(0);
  const lastProgressRef = useRef(progress ?? 0);

  // 1) pendingAgentDecision이 활성화(초기 실행 끝)될 때 초기 채팅 수 저장 및 진행률 보정
  useEffect(() => {
    if (pendingAgentDecision) {
      const initialCount = countChatMessages(messages);
      initialChatCountRef.current = initialCount;

      const totalTurns = sessionResult?.totalTurns ?? initialCount;
      const pct = Math.min(
        100,
        Math.round((initialCount / Math.max(1, totalTurns)) * 100),
      );
      if (typeof setProgress === "function") {
        setProgress(pct);
        lastProgressRef.current = pct;
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingAgentDecision]);

  // 2) 메시지 / 에이전트 상태 변화에 따라 진행률 재계산
  useEffect(() => {
    if (typeof setProgress !== "function") return;

    const currentCount = countChatMessages(messages);
    const serverTotal = sessionResult?.totalTurns;

    if (typeof serverTotal === "number" && serverTotal > 0) {
      const pct = Math.min(
        100,
        Math.round((currentCount / Math.max(1, serverTotal)) * 100),
      );
      setProgress(pct);
      lastProgressRef.current = pct;
      return;
    }

    if (hasAgentRun && !agentRunning) {
      setProgress(100);
      lastProgressRef.current = 100;
      return;
    }

    const initialCount = Math.max(1, initialChatCountRef.current || 0);
    const estimatedTotal = Math.max(
      currentCount,
      Math.round(initialCount + (currentCount - initialCount) * 2) ||
        initialCount + 4,
    );

    const pct = Math.min(
      100,
      Math.round((currentCount / Math.max(1, estimatedTotal)) * 100),
    );

    const newPct = Math.max(lastProgressRef.current, pct);
    setProgress(newPct);
    lastProgressRef.current = newPct;
  }, [messages, hasAgentRun, agentRunning, sessionResult, setProgress]);

  // === ✅ 추가: "대화로그 페이지" 판별 (대화 메시지가 1개 이상일 때만 수사보드 표시) ===
  const hasChatLog = useMemo(() => countChatMessages(messages) > 0, [messages]);

  // ✅ 오른쪽 보드 "내용" 지연 (박스는 즉시 보임) - 두 번째 코드에서 가져옴
  const [showBoardContent, setShowBoardContent] = useState(false);
  const boardTimerRef = useRef(null);
  useEffect(() => {
    if (!hasChatLog) {
      setShowBoardContent(false);
      if (boardTimerRef.current) {
        clearTimeout(boardTimerRef.current);
        boardTimerRef.current = null;
      }
      return;
    }
    if (showBoardContent || boardTimerRef.current) return;
    boardTimerRef.current = setTimeout(() => {
      setShowBoardContent(true);
      boardTimerRef.current = null;
    }, Math.max(0, boardDelaySec) * 1000);
    return () => {
      if (boardTimerRef.current) {
        clearTimeout(boardTimerRef.current);
        boardTimerRef.current = null;
      }
    };
  }, [hasChatLog, boardDelaySec, showBoardContent]);

  // ✅ 두 번째 대화 직전 스피너를 intermissionSec 동안만 노출 - 두 번째 코드에서 가져옴
  const [intermissionVisible, setIntermissionVisible] = useState(false);
  useEffect(() => {
    if (simulationState === "INTERMISSION") {
      setIntermissionVisible(true);
      const t = setTimeout(() => setIntermissionVisible(false), Math.max(0, intermissionSec) * 1000);
      return () => clearTimeout(t);
    } else {
      setIntermissionVisible(false);
    }
  }, [simulationState, intermissionSec]);

  // === 표시 조건: 대화 완료 + 에이전트 의사결정 완료 ===
  // 대화 완전 종료 + 에이전트 의사결정 완료 + 에이전트 동작 중 아님
  const showTTSButton =
    simulationState === "FINISH" &&  // ✅ 끝났을 때만
    !pendingAgentDecision &&          // ✅ 에이전트 예/아니오 결정 끝
    !agentRunning &&                  // ✅ 에이전트 동작 중 아님
    !!sessionResult;                  // (안전장치) 결과 객체 존재

  // 이미 있는 hasChatLog 사용: 대화가 한 번이라도 진행됐는지
  const showResetButtonsNow = simulationState === "IDLE" && !pendingAgentDecision;

  // ✅ '대화 끝' + 재선택 두 버튼이 활성화(둘 다 선택됨) + 실제로 대화가 있었음
  const showTTSNow =
    showResetButtonsNow &&
    !!selectedScenario &&
    !!selectedCharacter &&
    hasChatLog;

  // 더미 데이터
  const dummyInsights = {
    isPhishing: true,
    reason: "피해자가 반복적으로 계좌번호를 확인하라는 요구에 망설임 없이 응답했습니다.",
    weakness: "권위적인 기관 사칭에 대한 의심 부족, 즉각적인 대응 습관 미비",
    riskScore: 78,
    riskLevel: "높음",
  };

  const isAnyModalOpen = showReportPrompt || showCustomModal || open;

  // 버튼 노출 조건: 세션 완료 + 진행 100% + 모달 안 떠 있음
  const shouldShowReportCTA = !!sessionResult && progress >= 100 && !isAnyModalOpen;

  return (
    <div
      className="min-h-screen"
      style={{ backgroundColor: THEME.bg, color: THEME.text }}
    >
      <div className="container mx-auto px-6 py-12">
        <div
          className="w-full max-w-[1400px] mx-auto h-[calc(100vh-3rem)] rounded-3xl shadow-2xl border flex flex-col min-h-0"
          style={{
            borderColor: THEME.border,
            backgroundColor: THEME.panel,
          }}
        >
          {/* 상단 HUD */}
          <HudBar COLORS={THEME} />

          {/* 상단 상태/버튼 바 */}
          <div
            className="px-6 py-4 flex items-center justify-between"
            style={{
              backgroundColor: THEME.panel,
              borderBottom: `1px dashed ${THEME.border}`,
            }}
          >
            <div className="flex items-center gap-3">
              <Badge
                tone={selectedScenario ? "primary" : "neutral"}
                COLORS={THEME}
              >
                {selectedScenario ? selectedScenario.name : "시나리오 미선택"}
              </Badge>
              <Badge
                tone={selectedCharacter ? "success" : "neutral"}
                COLORS={THEME}
              >
                {selectedCharacter ? selectedCharacter.name : "캐릭터 미선택"}
              </Badge>
            </div>

            <div className="flex items-center gap-2">
            {/* 시나리오 다시 선택 */}
            {selectedScenario && showResetButtonsNow && (
              <button
                onClick={() => {
                  setSelectedScenario(null);
                  setSelectedTag(null);
                  addSystem("시나리오를 다시 선택하세요.");
                }}
                className="px-3 py-2 rounded-md text-sm font-medium border hover:opacity-90 transition"
                style={{
                  backgroundColor: THEME.panelDark,
                  borderColor: THEME.border,
                  color: THEME.sub,
                }}
              >
                ← 시나리오 다시 선택
              </button>
            )}

            {/* 캐릭터 다시 선택 */}
            {selectedCharacter && showResetButtonsNow && (
              <button
                onClick={() => {
                  setSelectedCharacter(null);
                  addSystem("캐릭터를 다시 선택하세요.");
                }}
                className="px-3 py-2 rounded-md text-sm font-medium border hover:opacity-90 transition"
                style={{
                  backgroundColor: THEME.panelDark,
                  borderColor: THEME.border,
                  color: THEME.sub,
                }}
              >
                ← 캐릭터 다시 선택
              </button>
            )}

            {/* ✅ 두 버튼이 활성화 되는 조건에서만 TTS 버튼도 같이 노출 - 첫 번째 코드 텍스트 사용 */}
            {showTTSNow && (
              <button
                onClick={() => setOpen(true)}
                style={{
                  background: THEME.accent ?? THEME.border,
                  color: THEME.text,
                  padding: "6px 6px",
                  borderRadius: 8,
                  border: `1px solid ${THEME.border}`,
                  boxShadow: "0 6px 18px rgba(0,0,0,0.2)",
                  cursor: "pointer",
                  fontSize: "15px"
                }}
              >
                음성 대화 시뮬레이션
              </button>
            )}

            {/* 모달 컴포넌트는 그대로 두되, isOpen으로만 제어 */}
            <TTSModal isOpen={open} onClose={() => setOpen(false)} COLORS={THEME} />
          </div>
          </div>


          {/* ===== 메인 영역: 좌(대화/선택) / 우(수사보드) ===== */}
          <div className="flex-1 min-h-0 flex" style={{ backgroundColor: THEME.bg }}>
            {/* --- 왼쪽: 대화/선택 영역 --- */}
            <div
              className="flex flex-col min-h-0"
              style={{ flex: hasChatLog ? "0 0 70%" : "1 1 100%" }} // ✅ 대화로그 없으면 100%
            >
              <div className="px-6 py-6 flex-1 min-h-0">
                <div
                  ref={scrollContainerRef}
                  className="h-full overflow-y-auto space-y-6"
                >
                  {!messages.some((m) => m.type === "chat") && (
                    <SpinnerMessage
                      simulationState={simulationState}
                      COLORS={THEME}
                    />
                  )}

                  {messages.map((m, index) => {
                    const nm = normalizeMessage(m);
                    const victimImg = selectedCharacter
                      ? getVictimImage(selectedCharacter.photo_path)
                      : null;
                    return (
                      <MessageBubble
                        key={index}
                        message={nm}
                        selectedCharacter={selectedCharacter}
                        victimImageUrl={victimImg}
                        COLORS={THEME}
                        label={nm.label}
                        side={nm.side}
                        role={nm.role}
                      />
                    );
                  })}

                  {/* 두 번째 대화 직전 스피너 (정확히 intermissionSec초) - 두 번째 코드에서 가져옴 */}
                  {intermissionVisible && (
                    <SpinnerMessage simulationState="RUNNING" COLORS={THEME} />
                  )}

                  {/* 인라인 에이전트 결정 UI */}
                  {pendingAgentDecision &&
                    simulationState === "IDLE" &&
                    !hasAgentRun && (
                      <div className="flex justify-center mt-2">
                        <div
                          className="w-full max-w-[820px] p-4 rounded-md border"
                          style={{
                            backgroundColor: THEME.panel,
                            borderColor: THEME.border,
                          }}
                        >
                          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
                            <p className="text-sm" style={{ color: THEME.sub }}>
                              에이전트를 사용하여 대화를 이어보시겠습니까?
                              <span className="ml-2 text-xs" style={{ color: THEME.sub }}>
                                (에이전트는 추가 분석/판단을 포함합니다)
                              </span>
                            </p>

                            <div className="flex items-center gap-4 justify-end">
                              <label
                                className="inline-flex items-center gap-2 text-sm"
                                style={{ color: THEME.sub }}
                              >
                                <input
                                  type="checkbox"
                                  style={{ accentColor: THEME.blurple }}
                                  checked={!!agentVerbose}
                                  onChange={(e) => setAgentVerbose(e.target.checked)}
                                />
                                상세근거(verbose)
                              </label>

                              <button
                                onClick={declineAgentRun}
                                className="px-4 py-2 rounded"
                                style={{
                                  backgroundColor: THEME.panelDark,
                                  color: THEME.text,
                                }}
                              >
                                아니요
                              </button>

                              <button
                                onClick={startAgentRun}
                                disabled={agentRunning || hasAgentRun}
                                className="px-4 py-2 rounded text-white"
                                style={{
                                  backgroundColor: THEME.blurple,
                                  opacity: agentRunning ? 0.5 : 1,
                                  cursor: agentRunning ? "not-allowed" : undefined,
                                }}
                              >
                                {agentRunning ? "로딩..." : "예"}
                              </button>
                            </div>
                          </div>
                        </div>
                      </div>
                    )}

                  {/* 시나리오 선택 */}
                  {needScenario && (
                    <div className="flex justify-start">
                      <SelectedCard
                        title="시나리오 선택"
                        subtitle="유형 칩을 먼저 눌러 필터링한 뒤, 상세 시나리오를 선택하세요."
                        COLORS={THEME}
                      >
                        <div className="mb-4">
                          {["기관 사칭형", "가족·지인 사칭", "대출사기형"].map((t) => (
                            <Chip
                              key={t}
                              active={selectedTag === t}
                              label={`${t}`}
                              onClick={() =>
                                setSelectedTag(selectedTag === t ? null : t)
                              }
                              COLORS={THEME}
                            />
                          ))}
                        </div>

                       {/* ➕ 새 시나리오 추가 카드 */}
                        <div className="mb-4">
                          <CustomScenarioButton onClick={() => setShowCustomModal(true)} COLORS={THEME} />
                        </div>

                        <div
                          className="flex-1 min-h-0 space-y-4 overflow-y-auto pr-1"
                          style={{ maxHeight: "100%" }}
                        >
                          {combinedScenarios.map((s) => (
                            <button
                              key={s.id}
                              onClick={() => setSelectedScenario(s)}
                              className="w-full text-left rounded-lg p-4 hover:opacity-90"
                              style={{
                                backgroundColor: THEME.panelDark,
                                border: `1px solid ${THEME.border}`,
                                color: THEME.text,
                              }}
                            >
                              <div className="flex items-center justify-between mb-2">
                                <span className="font-semibold text-lg">{s.name}</span>
                                <Badge tone={s.type === "커스텀" ? "secondary" : "primary"} COLORS={THEME}>
                                  {s.type}
                                </Badge>
                              </div>
                              <p
                                className="text-base leading-relaxed"
                                style={{ color: THEME.sub }}
                              >
                                {s.profile?.purpose ?? ""}
                              </p>
                            </button>
                          ))}
                          {combinedScenarios.length === 0 && (
                            <div
                              className="w-full text-left rounded-lg p-4"
                              style={{
                                backgroundColor: THEME.panelDark,
                                border: `1px solid ${THEME.border}`,
                                color: THEME.sub,
                              }}
                            >
                              표시할 시나리오가 없습니다. "새 시나리오 추가"로 만들어 보세요.
                            </div>
                          )}
                        </div>
                      </SelectedCard>
                    </div>
                  )}

                  {/* 캐릭터 선택 */}
                  {!needScenario && needCharacter && (
                    <div
                      className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 flex-1 min-h-0 overflow-y-auto pr-1"
                      style={{ maxHeight: "100%" }}
                    >
                      <CustomCharacterCreate
                        theme={THEME}
                        onCreated={(createdVictim) => {
                          // 리스트 맨 끝에 추가
                          setCustomVictims((prev) => [...prev, createdVictim]);
                          // (옵션) 즉시 선택
                          setSelectedCharacter(createdVictim);
                          addSystem(`커스텀 캐릭터 저장 및 선택: ${createdVictim.name}`);
                        }}
                      />

                      {[...characters, ...customVictims].map((c) => (
                        <button key={c.id} onClick={() => setSelectedCharacter(c)}>
                          <div
                            className="flex flex-col h-full rounded-2xl overflow-hidden border hover:border-[rgba(168,134,42,.25)] transition-colors"
                            style={{
                              backgroundColor: THEME.panelDark,
                              borderColor: THEME.border,
                            }}
                          >
                            {getVictimImage(c.photo_path) ? (
                              <div
                                className="w-full h-44 bg-cover bg-center"
                                style={{
                                  backgroundImage: `url(${getVictimImage(c.photo_path)})`,
                                }}
                              />
                            ) : (
                              <div
                                className="w-full h-44 flex items-center justify-center text-6xl"
                                style={{ backgroundColor: THEME.panelDarker }}
                              >
                                {c.avatar ?? "👤"}
                              </div>
                            )}

                            <div className="p-4 flex flex-col gap-3">
                              <div className="flex items-center justify-between">
                                <span
                                  className="font-semibold text-lg"
                                  style={{ color: THEME.text }}
                                >
                                  {c.name}
                                </span>
                                <span
                                  className="text-xs px-2 py-1 rounded-md"
                                  style={{
                                    color: THEME.blurple,
                                    backgroundColor: "rgba(168,134,42,.08)",
                                    border: `1px solid rgba(168,134,42,.18)`,
                                  }}
                                >
                                  프로필
                                </span>
                              </div>

                              <div className="space-y-2 text-sm" style={{ color: THEME.sub }}>
                                <div className="flex justify-between items-center">
                                  <span className="text-[12px] opacity-70">나이</span>
                                  <span className="font-medium" style={{ color: THEME.text }}>
                                    {c.meta.age}
                                  </span>
                                </div>
                                <div className="flex justify-between items-center">
                                  <span className="text-[12px] opacity-70">성별</span>
                                  <span className="font-medium" style={{ color: THEME.text }}>
                                    {c.meta.gender}
                                  </span>
                                </div>
                                <div className="flex justify-between items-center">
                                  <span className="text-[12px] opacity-70">거주지</span>
                                  <span className="font-medium truncate ml-2" style={{ color: THEME.text }}>
                                    {c.meta.address}
                                  </span>
                                </div>
                                <div className="flex justify-between items-center">
                                  <span className="text-[12px] opacity-70">학력</span>
                                  <span className="font-medium truncate ml-2" style={{ color: THEME.text }}>
                                    {c.meta.education}
                                  </span>
                                </div>
                              </div>

                              <div>
                                <span className="block text-[12px] opacity-70 mb-2" style={{ color: THEME.sub }}>
                                  지식
                                </span>
                                <div className="space-y-1">
                                  {Array.isArray(c?.knowledge?.comparative_notes) &&
                                  c.knowledge.comparative_notes.length > 0 ? (
                                    c.knowledge.comparative_notes.map((note, idx) => (
                                      <div
                                        key={idx}
                                        className="text-sm font-medium leading-relaxed"
                                        style={{ color: THEME.text }}
                                      >
                                        • {note}
                                      </div>
                                    ))
                                  ) : (
                                    <div className="text-sm" style={{ color: THEME.sub }}>
                                      비고 없음
                                    </div>
                                  )}
                                </div>
                              </div>

                              <div>
                                <span className="block text-[12px] opacity-70 mb-2" style={{ color: THEME.sub }}>
                                  성격
                                </span>
                                <div className="space-y-1">
                                  {c?.traits?.ocean && typeof c.traits.ocean === "object" ? (
                                    Object.entries(c.traits.ocean).map(([key, val]) => {
                                      const labelMap = {
                                        openness: "개방성",
                                        neuroticism: "신경성",
                                        extraversion: "외향성",
                                        agreeableness: "친화성",
                                        conscientiousness: "성실성",
                                      };
                                      const label = labelMap[key] ?? key;
                                      return (
                                        <div key={key} className="flex justify-between items-center">
                                          <span className="text-[12px] opacity-70" style={{ color: THEME.sub }}>
                                            {label}
                                          </span>
                                          <span className="text-sm font-medium" style={{ color: THEME.text }}>
                                            {val}
                                          </span>
                                        </div>
                                      );
                                    })
                                  ) : (
                                    <div className="text-sm" style={{ color: THEME.sub }}>
                                      성격 정보 없음
                                    </div>
                                  )}
                                </div>
                              </div>
                            </div>
                          </div>
                        </button>
                      ))}
                    </div>
                  )}

                  {/* 시작 버튼 */}
                  {selectedScenario &&
                    selectedCharacter &&
                    simulationState === "IDLE" &&
                    !pendingAgentDecision &&
                    !showReportPrompt &&
                    !hasInitialRun && (
                      <div className="flex justify-center">
                        <button
                          onClick={startSimulation}
                          disabled={
                            simulationState === "PREPARE" ||
                            simulationState === "RUNNING" ||
                            pendingAgentDecision ||
                            hasInitialRun
                          }
                          className={`px-8 py-3 rounded-lg font-semibold text-lg ${
                            simulationState === "PREPARE" ||
                            simulationState === "RUNNING" ||
                            pendingAgentDecision ||
                            hasInitialRun
                              ? "opacity-60 cursor-not-allowed"
                              : ""
                          }`}
                          style={{
                            backgroundColor: THEME.blurple,
                            color: THEME.white,
                            boxShadow: "0 10px 24px rgba(0,0,0,.35)",
                          }}
                        >
                          <Play className="inline mr-3" size={20} /> 시뮬레이션 시작
                        </button>
                      </div>
                    )}
                </div>
              </div>
            </div>

            {/* --- 오른쪽: 에이전트 패널(로그/분석 스위치) - 첫 번째 코드 구조 + 두 번째 코드 타이밍 --- */}
{hasChatLog && (
  <div
    className="min-h-0 flex flex-col"
    style={{
      flex: "0 0 30%",
      borderLeft: `1px solid ${THEME.border}`,
      backgroundColor: THEME.panelDark,
      overflow: "hidden",
    }}
  >
    {/* 탭 바: 고정 높이 */}
    <div className="shrink-0 px-3 py-3" style={{ backgroundColor: THEME.panel }}>
      <div
        role="tablist"
        aria-label="에이전트 패널 전환"
        className="relative inline-flex items-center rounded-2xl border shadow-md overflow-hidden select-none"
        style={{
          borderColor: THEME.border,
          backgroundColor: THEME.panelDark,
        }}
      >
        {/* 하이라이트(선택된 탭 배경) - 수정된 transform 로직 */}
        <span
          aria-hidden="true"
          className="absolute inset-y-1 w-1/2 rounded-xl transition-transform duration-200 ease-out"
          style={{
            left: 6,
            backgroundColor: THEME.gold,
            transform:
              activeAgentTab === "insight" ? "translateX(0)" : "translateX(100%)",
            boxShadow: `0 6px 16px ${THEME.black}33`,
            zIndex: 0,
          }}
        />

        {/* 로그 탭 */}
        <button
          role="tab"
          aria-selected={activeAgentTab === "log"}
          onClick={() => setActiveAgentTab("log")}
          className="relative z-10 flex items-center gap-2 px-6 py-2.5 text-sm font-semibold whitespace-nowrap focus:outline-none transition-colors duration-200"
          style={{
            color: activeAgentTab === "log" ? THEME.blurple : THEME.text,
            background: "transparent",
          }}
        >
          <Terminal size={16} />
          <span>에이전트 로그</span>
        </button>

        {/* 분석 탭 */}
        <button
          role="tab"
          aria-selected={activeAgentTab === "insight"}
          onClick={() => setActiveAgentTab("insight")}
          className="relative z-10 flex items-center gap-2 px-6 py-2.5 text-sm font-semibold whitespace-nowrap focus:outline-none transition-colors duration-200"
          style={{
            color: activeAgentTab === "insight" ? THEME.blurple : THEME.text,
            background: "transparent",
          }}
        >
          <Lightbulb size={16} />
          <span>에이전트 분석</span>
        </button>
      </div>
    </div>

    {/* 콘텐츠 영역: 유동 높이 + 내부 스크롤 */}
    <div className="flex-1 min-h-0 overflow-hidden" style={{ backgroundColor: THEME.bg }}>
      <div className="h-full overflow-auto">
        {/* ⏳ 내용 지연: 스켈레톤 → boardDelaySec 후 실제 보드 - 두 번째 코드에서 가져옴 */}
        {showBoardContent ? (
          activeAgentTab === "log" ? (
            <TerminalLog data={agentLogText} />
          ) : (
            <InvestigationBoard COLORS={THEME} insights={dummyInsights} secondConvDelaySec={21} />
          )
        ) : (
          <div className="p-6 space-y-4">
            <div className="h-4 rounded animate-pulse" style={{ backgroundColor: THEME.panelDark }} />
            <div className="h-24 rounded animate-pulse" style={{ backgroundColor: THEME.panelDark }} />
            <div className="h-4 rounded animate-pulse" style={{ backgroundColor: THEME.panelDark }} />
            <div className="h-32 rounded animate-pulse" style={{ backgroundColor: THEME.panelDark }} />
            <div className="text-sm opacity-70" style={{ color: THEME.sub }}>
              분석 보드를 준비하고 있습니다…
            </div>
          </div>
        )}
      </div>
    </div>
  </div>
)}
            </div>


          {/* 하단 진행률 바 */}
          <div
            className="px-6 py-4 flex items-center justify-between rounded-bl-3xl rounded-br-3xl"
            style={{
              backgroundColor: THEME.panel,
              borderTop: `1px solid ${THEME.border}`,
            }}
          >
            <div className="flex items-center gap-4">
              <Clock size={18} color={THEME.sub} />
              <span className="text-base font-medium" style={{ color: THEME.sub }}>
                진행률: {Math.round(progress)}%
              </span>
              <div
                className="w-48 h-3 rounded-full overflow-hidden"
                style={{ backgroundColor: THEME.panelDark }}
              >
                <div
                  className="h-3 rounded-full transition-all duration-300"
                  style={{
                    width: `${progress}%`,
                    backgroundColor: THEME.blurple,
                  }}
                />
              </div>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-base font-medium" style={{ color: THEME.sub }}>
                상태: {simulationState}
              </span>
               {/* ✅ 리포트 보기 버튼 (첫 번째 코드 위치) */}
    {shouldShowReportCTA && (
      <button
        onClick={() => setCurrentPage("report")}
        disabled={pendingAgentDecision}
        aria-disabled={pendingAgentDecision}
        title={
          pendingAgentDecision
            ? "에이전트 사용 여부 결정 후에 리포트를 보실 수 있습니다."
            : "리포트 보기"
        }
        className="px-4 py-2 rounded-lg text-sm font-semibold transition-all duration-200 flex items-center gap-2"
        style={{
          backgroundColor: THEME.blurple,
          color: THEME.white,
          boxShadow: "0 6px 12px rgba(0,0,0,.25)",
          pointerEvents: pendingAgentDecision ? "none" : undefined,
          opacity: pendingAgentDecision ? 0.5 : 1,
        }}
      >
        <FileBarChart2 size={18} />
        리포트 보기
      </button>
    )}

    {simulationState === "FINISH" && (
      <button
        onClick={resetToSelection}
        className="px-4 py-2 rounded-lg text-sm font-semibold transition-all duration-200"
        style={{
          backgroundColor: THEME.blurple,
          color: THEME.white,
          boxShadow: "0 6px 12px rgba(0,0,0,.25)",
        }}
      >
        다시 선택하기
      </button>
    )}
            </div>
          </div>
        </div>
      </div>

      {/* 리포트 안내 모달 */}
      {showReportPrompt && (
        <div className="fixed inset-0 flex items-center justify-center bg-black bg-opacity-50 z-50">
          <div
            className="p-6 rounded-lg border"
            style={{
              borderColor: THEME.border,
              backgroundColor: THEME.panel,
            }}
          >
            <h3 className="text-xl font-semibold mb-3" style={{ color: THEME.text }}>
              시뮬레이션이 완료되었습니다
            </h3>
            <p className="text-sm" style={{ color: THEME.sub, marginBottom: 16 }}>
              결과 리포트를 확인하시겠습니까?
            </p>
            <div className="flex justify-end gap-4">
              <button
                onClick={() => setShowReportPrompt(false)}
                className="px-4 py-2 rounded"
                style={{ backgroundColor: THEME.panelDark, color: THEME.text }}
              >
                닫기
              </button>
              <button
                onClick={() => setCurrentPage("report")}
                disabled={pendingAgentDecision}
                aria-disabled={pendingAgentDecision}
                title={
                  pendingAgentDecision
                    ? "에이전트 사용 여부 결정 후에 리포트를 보실 수 있습니다."
                    : "리포트 보기"
                }
                className="px-4 py-2 rounded"
                style={{
                  backgroundColor: THEME.blurple,
                  color: THEME.white,
                  pointerEvents: pendingAgentDecision ? "none" : undefined,
                  opacity: pendingAgentDecision ? 0.5 : 1,
                }}
              >
                리포트 보기
              </button>
            </div>
          </div>
        </div>
      )}
      
      {/* 커스텀 시나리오 모달 */}
      <CustomScenarioModal
        open={showCustomModal}
        onClose={handleCloseCustomModal}
        onSave={handleSaveCustomScenario}
        COLORS={THEME}
        selectedTag={selectedTag}
      />
    </div>
  );
};

export default SimulatorPage;