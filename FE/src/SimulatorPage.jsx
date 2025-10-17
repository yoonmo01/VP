import { useState, useMemo, useEffect, useRef } from "react";
import {
  Play,
  Clock,
  FileBarChart2,
  Terminal,
  Lightbulb,
  Home,
} from "lucide-react";
import HudBar from "./HudBar";
import Badge from "./Badge";
import SelectedCard from "./SelectedCard";
import Chip from "./Chip";
import MessageBubble from "./MessageBubble";
import SpinnerMessage from "./SpinnerMessage";
import CustomCharacterCreate from "./CustomCharacterCreate";
import InvestigationBoard from "./InvestigationBoard";
import TTSModal from "./components/TTSModal";
import CustomScenarioButton from "./CustomScenarioButton";
import CustomScenarioModal from "./CustomScenarioModal";
import TerminalLog from "./TerminalLog";
import InlinePhishingSummaryBox from "./InlinePhishingSummaryBox";
import { THEME as BASE_THEME } from "./constants/colors";

const SIMPLE_BOARD_MODE = false;

/* 이미지 로드 유틸 */
const getVictimImage = (photoPath) => {
  if (!photoPath) return null;
  try {
    const fileName = photoPath.split("/").pop();
    if (fileName)
      return new URL(`./assets/victims/${fileName}`, import.meta.url).href;
  } catch {
    console.warn("이미지 로드 실패");
  }
  return null;
};

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
  setProgress,
  startSimulation,
  startAgentRun,
  declineAgentRun,
  scenarios,
  characters,
  scrollContainerRef: injectedScrollContainerRef,
  addSystem,
  pendingAgentDecision,
  showReportPrompt,
  setShowReportPrompt,
  hasInitialRun,
  hasAgentRun,
  agentRunning,
  agentVerbose,
  setAgentVerbose,
  boardDelaySec = 3,
  intermissionSec = 3,
  logTickMs = 200,
}) => {

  
  /* ----------------------------------------------------------
   🧩 상태
  ---------------------------------------------------------- */
  const needScenario = !selectedScenario;
  const needCharacter = !selectedCharacter;
  const [selectedTag, setSelectedTag] = useState(null);
  const [showCustomModal, setShowCustomModal] = useState(false);
  const [customScenarios, setCustomScenarios] = useState([]);
  const [customVictims, setCustomVictims] = useState([]);
  const [openTTS, setOpenTTS] = useState(false);

  // 🎯 백엔드 데이터 구조 기반 state
  const [agentLogText, setAgentLogText] = useState("");     // <TerminalLog />용
  const [insightsList, setInsightsList] = useState([]);     // <InvestigationBoard />용
  const localScrollContainerRef = useRef(null);
  const scrollRef = injectedScrollContainerRef ?? localScrollContainerRef;
  const [activeAgentTab, setActiveAgentTab] = useState("log");
  const [showBoardContent, setShowBoardContent] = useState(false);

  /* ----------------------------------------------------------
   🎨 테마
  ---------------------------------------------------------- */
  const THEME = {
    ...(COLORS ?? BASE_THEME),
    bg: "#030617",
    panel: "#061329",
    panelDark: "#04101f",
    panelDarker: "#020812",
    border: "#A8862A",
    text: "#FFFFFF",
    sub: "#BFB38A",
    blurple: "#A8862A",
  };
  // 진행률 계산
  const countChatMessages = (msgs = []) =>
    msgs.filter((m) => (m?.type ?? m?._kind) === "chat").length;

  useEffect(() => {
    if (typeof setProgress !== "function") return;
    const pct = Math.min(100, Math.round((countChatMessages(messages) / 10) * 100));
    setProgress(pct);
  }, [messages, setProgress]);

  // 보드 표시 지연
  useEffect(() => {
    const timer = setTimeout(() => setShowBoardContent(true), 3000);
    return () => clearTimeout(timer);
  }, []);
  
  /* ----------------------------------------------------------
   🏠 홈버튼 (초기화)
  ---------------------------------------------------------- */
  const handleGoHome = () => {
    setSelectedScenario(null);
    setSelectedCharacter(null);
    setProgress(0);
    setCurrentPage("landing");
  };

  /* ----------------------------------------------------------
   🎯 시나리오 필터링 + 커스텀 통합
  ---------------------------------------------------------- */
  const filteredScenarios = useMemo(() => {
    if (!selectedTag) return scenarios;
    return scenarios.filter(
      (s) =>
        s.type === selectedTag ||
        (Array.isArray(s.tags) && s.tags.includes(selectedTag))
    );
  }, [selectedTag, scenarios]);

  const combinedScenarios = useMemo(() => {
    const base = filteredScenarios ?? [];
    const custom = selectedTag
      ? customScenarios.filter((c) => c.type === selectedTag)
      : customScenarios;
    return [...base, ...custom];
  }, [filteredScenarios, customScenarios, selectedTag]);

  const handleSaveCustomScenario = (scenario) => {
    setCustomScenarios((prev) => [...prev, scenario]);
    setShowCustomModal(false);
  };

   // 🔻 임시: 백엔드 연결 전 더미 데이터 구조 (형태 맞춤) => 이런 느낌으로 맞춰야 함
    useEffect(() => {
      const mockLog = `
      Action: mcp.simulator_run
      Action Input: {"offender_id":1,"victim_id":1}
      ---
      Thought: 분석 실행 중...
      Result: OK
      `;
          const mockInsights = [
            {
              run_no: 1,
              phishing: true,
              evidence: "피해자가 계좌번호를 전달함.",
              risk: { score: 85, level: "high", rationale: "낯선 번호에 즉시 응답" },
              victim_vulnerabilities: ["낯선 전화 응답", "계좌번호 노출"],
            },
            {
              run_no: 2,
              phishing: false,
              evidence: "피해자가 의심하여 통화를 종료함.",
              risk: { score: 40, level: "low", rationale: "경계심 강화됨" },
              victim_vulnerabilities: [],
            },
          ];
          setAgentLogText(mockLog);
          setInsightsList(mockInsights);
      }, []);

       // 메시지 표준화
      const normalizeMessage = (m) => {
        const role = (m?.sender || m?.role || "").toLowerCase();
        return {
          ...m,
          label: role === "offender" ? "피싱범" : role === "victim" ? "피해자" : "시스템",
          side: role === "offender" ? "left" : role === "victim" ? "right" : "center",
          _kind: "chat",
        };
      };

  const hasChatLog = useMemo(() => countChatMessages(messages) > 0, [messages]);

  /* ----------------------------------------------------------
   🧠 에이전트 로그 (점진 표시)
  ---------------------------------------------------------- */
  const computedAgentLogText = useMemo(() => {
    if (!sessionResult?.agentLogs) return "";
    return sessionResult.agentLogs
      .map((log) => `[${log.role}] ${log.content}`)
      .join("\n");
  }, [sessionResult?.agentLogs]);

  const agentLogLines = useMemo(
    () =>
      computedAgentLogText
        .split(/\r?\n/)
        .map((l) => l.trim())
        .filter(Boolean),
    [computedAgentLogText]
  );
  const [displayedAgentLogText, setDisplayedAgentLogText] = useState("");
  const logIndexRef = useRef(0);

  useEffect(() => {
    if (!agentLogLines.length) return;
    const timer = setInterval(() => {
      if (logIndexRef.current >= agentLogLines.length)
        return clearInterval(timer);
      setDisplayedAgentLogText((prev) =>
        prev
          ? `${prev}\n${agentLogLines[logIndexRef.current]}`
          : agentLogLines[logIndexRef.current]
      );
      logIndexRef.current++;
    }, logTickMs);
    return () => clearInterval(timer);
  }, [agentLogLines, logTickMs]);

  /* ----------------------------------------------------------
   ⏳ 분석 보드 지연 표시
  ---------------------------------------------------------- */
  useEffect(() => {
    if (!hasChatLog) return setShowBoardContent(false);
    const t = setTimeout(() => setShowBoardContent(true), boardDelaySec * 1000);
    return () => clearTimeout(t);
  }, [hasChatLog, boardDelaySec]);

  /* ----------------------------------------------------------
   🧩 렌더링
  ---------------------------------------------------------- */
  return (
    <div className="min-h-screen" style={{ backgroundColor: THEME.bg }}>
      <div className="container mx-auto px-6 py-12">
        <div
          className="w-full max-w-[1400px] mx-auto h-[calc(100vh-3rem)] rounded-3xl shadow-2xl border flex flex-col"
          style={{ borderColor: THEME.border, backgroundColor: THEME.panel }}
        >
          {/* 상단 HUD */}
          <HudBar COLORS={THEME} />

          {/* 상단 상태 + 홈버튼 */}
          <div
            className="px-6 py-4 flex items-center justify-between border-b"
            style={{ borderColor: THEME.border }}
          >
            <div className="flex items-center gap-3">
              <Badge tone={selectedScenario ? "primary" : "neutral"} COLORS={THEME}>
                {selectedScenario ? selectedScenario.name : "시나리오 미선택"}
              </Badge>
              <Badge tone={selectedCharacter ? "success" : "neutral"} COLORS={THEME}>
                {selectedCharacter ? selectedCharacter.name : "캐릭터 미선택"}
              </Badge>
            </div>

            <button
              onClick={handleGoHome}
              className="px-3 py-2 rounded-md text-sm font-medium flex items-center gap-2 border"
              style={{
                backgroundColor: THEME.panelDark,
                borderColor: THEME.border,
                color: THEME.sub,
              }}
            >
              <Home size={16} />
              홈으로
            </button>
          </div>

          {/* 메인 */}
          <div className="flex-1 flex min-h-0" style={{ backgroundColor: THEME.bg }}>
            {/* 왼쪽: 시나리오 / 캐릭터 / 대화 */}
            <div
              className="flex flex-col flex-1 px-6 py-6 overflow-y-auto space-y-6"
              ref={scrollRef}
            >
              {/* 1️⃣ 시나리오 선택 */}
              {needScenario && (
                <SelectedCard
                  title="시나리오 선택"
                  subtitle="유형 칩을 눌러 필터링한 뒤, 상세 시나리오를 선택하세요."
                  COLORS={THEME}
                >
                  <div className="mb-4 flex gap-2">
                    {["기관 사칭형", "가족·지인 사칭", "대출사기형"].map((t) => (
                      <Chip
                        key={t}
                        active={selectedTag === t}
                        label={t}
                        onClick={() =>
                          setSelectedTag(selectedTag === t ? null : t)
                        }
                        COLORS={THEME}
                      />
                    ))}
                  </div>

                  <CustomScenarioButton
                    onClick={() => setShowCustomModal(true)}
                    COLORS={THEME}
                  />

                  <div className="space-y-4 mt-4">
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
                          <Badge
                            tone={s.type === "커스텀" ? "secondary" : "primary"}
                            COLORS={THEME}
                          >
                            {s.type}
                          </Badge>
                        </div>
                        <p style={{ color: THEME.sub }}>
                          {s.profile?.purpose ?? "설명 없음"}
                        </p>
                      </button>
                    ))}
                  </div>
                </SelectedCard>
              )}

              {/* 2️⃣ 캐릭터 선택 */}
              {!needScenario && needCharacter && (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 flex-1 min-h-0 overflow-y-auto pr-1">
                  <CustomCharacterCreate
                    theme={THEME}
                    onCreated={(v) => {
                      setCustomVictims((p) => [...p, v]);
                      setSelectedCharacter(v);
                      addSystem(`커스텀 캐릭터 생성: ${v.name}`);
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
                        {/* 프로필 이미지 */}
                        {getVictimImage(c.photo_path) ? (
                          <div
                            className="w-full h-44 bg-cover bg-center"
                            style={{
                              backgroundImage: `url(${getVictimImage(
                                c.photo_path
                              )})`,
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

                        {/* 피해자 상세정보 */}
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

                          {/* 기본 정보 */}
                          <div
                            className="space-y-2 text-sm"
                            style={{ color: THEME.sub }}
                          >
                            <div className="flex justify-between items-center">
                              <span className="text-[12px] opacity-70">나이</span>
                              <span
                                className="font-medium"
                                style={{ color: THEME.text }}
                              >
                                {c.meta.age}
                              </span>
                            </div>
                            <div className="flex justify-between items-center">
                              <span className="text-[12px] opacity-70">성별</span>
                              <span
                                className="font-medium"
                                style={{ color: THEME.text }}
                              >
                                {c.meta.gender}
                              </span>
                            </div>
                            <div className="flex justify-between items-center">
                              <span className="text-[12px] opacity-70">거주지</span>
                              <span
                                className="font-medium truncate ml-2"
                                style={{ color: THEME.text }}
                              >
                                {c.meta.address}
                              </span>
                            </div>
                            <div className="flex justify-between items-center">
                              <span className="text-[12px] opacity-70">학력</span>
                              <span
                                className="font-medium truncate ml-2"
                                style={{ color: THEME.text }}
                              >
                                {c.meta.education}
                              </span>
                            </div>
                          </div>

                          {/* 지식 */}
                          <div>
                            <span
                              className="block text-[12px] opacity-70 mb-2"
                              style={{ color: THEME.sub }}
                            >
                              지식
                            </span>
                            <div className="space-y-1">
                              {Array.isArray(c?.knowledge?.comparative_notes) &&
                              c.knowledge.comparative_notes.length > 0 ? (
                                c.knowledge.comparative_notes.map(
                                  (note, idx) => (
                                    <div
                                      key={idx}
                                      className="text-sm font-medium leading-relaxed"
                                      style={{ color: THEME.text }}
                                    >
                                      • {note}
                                    </div>
                                  )
                                )
                              ) : (
                                <div
                                  className="text-sm"
                                  style={{ color: THEME.sub }}
                                >
                                  비고 없음
                                </div>
                              )}
                            </div>
                          </div>

                          {/* 성격 */}
                          <div>
                            <span
                              className="block text-[12px] opacity-70 mb-2"
                              style={{ color: THEME.sub }}
                            >
                              성격
                            </span>
                            <div className="space-y-1">
                              {c?.traits?.ocean &&
                              typeof c.traits.ocean === "object" ? (
                                Object.entries(c.traits.ocean).map(
                                  ([key, val]) => {
                                    const labelMap = {
                                      openness: "개방성",
                                      neuroticism: "신경성",
                                      extraversion: "외향성",
                                      agreeableness: "친화성",
                                      conscientiousness: "성실성",
                                    };
                                    const label = labelMap[key] ?? key;
                                    return (
                                      <div
                                        key={key}
                                        className="flex justify-between items-center"
                                      >
                                        <span
                                          className="text-[12px] opacity-70"
                                          style={{ color: THEME.sub }}
                                        >
                                          {label}
                                        </span>
                                        <span
                                          className="text-sm font-medium"
                                          style={{ color: THEME.text }}
                                        >
                                          {val}
                                        </span>
                                      </div>
                                    );
                                  }
                                )
                              ) : (
                                <div
                                  className="text-sm"
                                  style={{ color: THEME.sub }}
                                >
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

              {/* 3️⃣ 시뮬레이션 대화 */}
              {/* {!needScenario && !needCharacter && (
                <>
                  {!messages.some((m) => m.type === "chat") ? (
                    <SpinnerMessage simulationState={simulationState} COLORS={THEME} />
                  ) : (
                    messages.map((m, i) => (
                      <MessageBubble
                        key={i}
                        message={m}
                        selectedCharacter={selectedCharacter}
                        victimImageUrl={selectedCharacter?.photo_path}
                        COLORS={THEME}
                      />
                    ))
                  )}
                  {sessionResult?.preview && !hasAgentRun && (
                    <InlinePhishingSummaryBox preview={sessionResult.preview} />
                  )}
                </>
              )} */}

               <div className="flex flex-1 min-h-0">
            {/* 왼쪽: 대화 */}
            <div className="flex-1 p-6 overflow-y-auto" ref={scrollRef}>
              {!messages.length && (
                <SpinnerMessage simulationState={simulationState} COLORS={THEME} />
              )}
              {messages.map((m, idx) => {
                const nm = normalizeMessage(m);
                return (
                  <MessageBubble
                    key={idx}
                    message={nm}
                    label={nm.label}
                    side={nm.side}
                    role={nm.role}
                    COLORS={THEME}
                  />
                );
              })}
            </div>

            {/* 오른쪽: 로그 / 분석 */}
            {hasChatLog && (
              <div
                className="flex flex-col w-[30%] border-l"
                style={{ borderColor: THEME.border, backgroundColor: THEME.panelDark }}
              >
                <div className="flex items-center border-b" style={{ borderColor: THEME.border }}>
                  <button
                    onClick={() => setActiveAgentTab("log")}
                    className={`flex-1 py-2 font-semibold ${
                      activeAgentTab === "log" ? "text-yellow-400" : "text-gray-400"
                    }`}
                  >
                    <Terminal size={14} className="inline mr-2" />
                    로그
                  </button>
                  <button
                    onClick={() => setActiveAgentTab("insight")}
                    className={`flex-1 py-2 font-semibold ${
                      activeAgentTab === "insight" ? "text-yellow-400" : "text-gray-400"
                    }`}
                  >
                    <Lightbulb size={14} className="inline mr-2" />
                    분석
                  </button>
                </div>

                <div className="flex-1 overflow-auto">
                  {activeAgentTab === "log" ? (
                    <TerminalLog logText={computedAgentLogText} COLORS={THEME} />
                  ) : showBoardContent ? (
                    <InvestigationBoard COLORS={THEME} insightsList={insightsList} />
                  ) : (
                    <div className="p-6 text-sm text-center" style={{ color: THEME.sub }}>
                      분석 보드를 준비 중입니다...
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

              {/* 시뮬레이션 시작 버튼 */}
              {selectedScenario &&
                selectedCharacter &&
                simulationState === "IDLE" &&
                !pendingAgentDecision &&
                !showReportPrompt &&
                !hasInitialRun && (
                  <div className="flex justify-center">
                    <button
                      onClick={startSimulation}
                      className="px-8 py-3 rounded-lg font-semibold text-lg"
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

            {/* 오른쪽: 에이전트 로그/분석 보드 */}
            {hasChatLog && (
              <div
                className="min-h-0 flex flex-col"
                style={{
                  flex: "0 0 30%",
                  borderLeft: `1px solid ${THEME.border}`,
                  backgroundColor: THEME.panelDark,
                }}
              >
                {/* 탭 선택 */}
                <div
                  className="px-3 py-3 border-b"
                  style={{ borderColor: THEME.border }}
                >
                  <div className="flex gap-4">
                    <button
                      className={`flex items-center gap-2 text-sm font-semibold ${
                        activeAgentTab === "log" ? "opacity-100" : "opacity-60"
                      }`}
                      onClick={() => setActiveAgentTab("log")}
                      style={{ color: THEME.text }}
                    >
                      <Terminal size={16} /> 에이전트 로그
                    </button>
                    <button
                      className={`flex items-center gap-2 text-sm font-semibold ${
                        activeAgentTab === "insight" ? "opacity-100" : "opacity-60"
                      }`}
                      onClick={() => setActiveAgentTab("insight")}
                      style={{ color: THEME.text }}
                    >
                      <Lightbulb size={16} /> 에이전트 분석
                    </button>
                  </div>
                </div>

                {/* 콘텐츠 */}
                <div className="flex-1 overflow-auto p-4">
                  {activeAgentTab === "log" ? (
                    <TerminalLog data={displayedAgentLogText} />
                  ) : showBoardContent ? (
                    <InvestigationBoard
                      COLORS={THEME}
                      insights={sessionResult?.insights}
                    />
                  ) : (
                    <div className="p-4 text-sm opacity-70" style={{ color: THEME.sub }}>
                      분석 데이터를 불러오는 중입니다...
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* 하단 진행률 */}
          <div
            className="px-6 py-4 flex items-center justify-between border-t"
            style={{ borderColor: THEME.border, backgroundColor: THEME.panel }}
          >
            <div className="flex items-center gap-3">
              <Clock size={18} color={THEME.sub} />
              <span style={{ color: THEME.sub }}>진행률: {Math.round(progress)}%</span>
            </div>
            {progress >= 100 && (
              <button
                onClick={() => setCurrentPage("report")}
                className="px-4 py-2 rounded-lg text-sm font-semibold"
                style={{
                  backgroundColor: THEME.blurple,
                  color: THEME.white,
                  boxShadow: "0 6px 12px rgba(0,0,0,.25)",
                }}
              >
                <FileBarChart2 size={18} className="inline mr-2" />
                리포트 보기
              </button>
            )}
          </div>
        </div>
      </div>

      {/* 모달들 */}
      <TTSModal isOpen={openTTS} onClose={() => setOpenTTS(false)} COLORS={THEME} />
      <CustomScenarioModal
        open={showCustomModal}
        onClose={() => setShowCustomModal(false)}
        onSave={handleSaveCustomScenario}
        COLORS={THEME}
        selectedTag={selectedTag}
      />
    </div>
  );
};

export default SimulatorPage;
