import React, { useState, useEffect, useRef, useMemo, useLayoutEffect } from 'react';
import {
  Play, Settings, User, FileText, Download, AlertTriangle, Check, X,
  ChevronRight, Clock, MessageCircle, Eye, Shield, Search,
  Bot, Terminal, ExternalLink
} from 'lucide-react';
import bg from './assets/첫화면.png';

/**
 * Discord-like + Investigator palette
 * - bg:      #1E1F22
 * - panel:   #2B2D31
 * - border:  #3F4147
 * - text:    #DCDDDE
 * - sub:     #B5BAC1
 * - blurple: #5865F2 (primary)
 * - success: #57F287
 * - warn:    #FEE75C
 * - danger:  #ED4245
 */

const COLORS = {
  bg: '#1E1F22',
  panel: '#2B2D31',
  border: '#3F4147',
  text: '#DCDDDE',
  sub: '#B5BAC1',
  blurple: '#5865F2',
  success: '#57F287',
  warn: '#FEE75C',
  danger: '#ED4245',
  black: '#0A0A0A',
  white: '#FFFFFF'
};

// 시나리오 데이터
const scenarios = [
  {
    id: 1,
    name: '기관사칭 #1',
    type: '기관사칭',
    tags: ['기관사칭', '전화', 'URL유도'],
    description: '금융감독원을 사칭하여 계좌 보안 문제로 개인정보를 요구하는 시나리오',
    steps: ['신분 확인', '문제 제기', '해결책 제시', '정보 요구', '긴급성 조성']
  },
  {
    id: 2,
    name: '가족·지인사칭 #1',
    type: '가족·지인사칭',
    tags: ['가족·지인사칭', '카톡', '송금요구'],
    description: '자녀를 사칭하여 급전이 필요하다며 송금을 요구하는 시나리오',
    steps: ['가족 관계 확인', '긴급상황 연출', '송금 요구', '시간 압박', '확인 차단']
  },
  {
    id: 3,
    name: '대출빙자 #1',
    type: '대출빙자',
    tags: ['대출빙자', '저금리', '서류요구'],
    description: '저금리 대출 상품을 빙자하여 개인정보와 보증금을 요구하는 시나리오',
    steps: ['대출 제안', '조건 제시', '서류 요구', '보증금 요구', '계약 체결']
  }
];

// 캐릭터 데이터
const characters = [
  { id: 1, name: '김영희(20대)', age: '20대', literacy: '높음', personality: '신중형', avatar: '👩‍💼' },
  { id: 2, name: '박철수(30대)', age: '30대', literacy: '보통', personality: '활동형', avatar: '👨‍💼' },
  { id: 3, name: '이미영(40대)', age: '40대', literacy: '보통', personality: '협조형', avatar: '👩‍🏫' },
  { id: 4, name: '최민호(50대)', age: '50대', literacy: '낮음', personality: '조심형', avatar: '👨‍🔧' },
  { id: 5, name: '강순자(60대)', age: '60대', literacy: '낮음', personality: '순응형', avatar: '👵' },
  { id: 6, name: '한동수(70대)', age: '70대', literacy: '매우낮음', personality: '의존형', avatar: '👴' }
];

const App = () => {
  const [currentPage, setCurrentPage] = useState('landing');
  const [selectedScenario, setSelectedScenario] = useState(null);
  const [selectedCharacter, setSelectedCharacter] = useState(null);
  const [simulationState, setSimulationState] = useState('IDLE');
  const [messages, setMessages] = useState([]);
  const [sessionResult, setSessionResult] = useState(null);
  const [progress, setProgress] = useState(0);
  const resetToSelection = () => {
  setSelectedScenario(null);
  setSelectedCharacter(null);
  setMessages([]);
  setSessionResult(null);
  setProgress(0);
  setSimulationState('IDLE');
  setCurrentPage('simulator');
};


  // ── 대화로그 스크롤 컨테이너 ─────────────────
  const scrollContainerRef = useRef(null);
  const stickToBottom = () => {
    const el = scrollContainerRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  };
  useLayoutEffect(() => {
    stickToBottom();
  }, [messages, simulationState, selectedScenario, selectedCharacter, sessionResult]);
  useEffect(() => {
    const el = scrollContainerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => stickToBottom());
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // ── 핵심 수정 1: 시나리오 변경 시 캐릭터 초기화 ─────────────────
  useEffect(() => {
    setSelectedCharacter(null);
  }, [selectedScenario]);

  // 시뮬레이션 시작
  const startSimulation = () => {
    if (!selectedScenario || !selectedCharacter) {
      addSystem('시나리오와 캐릭터를 먼저 선택해주세요.');
      return;
    }
    setSimulationState('PREPARE');
    addSystem(
      `시뮬레이션 준비 완료\n시나리오: ${selectedScenario.name}\n피해자: ${selectedCharacter.name}`
    );
    setTimeout(() => {
      setSimulationState('RUNNING');
      runSimulation();
    }, 700);
  };

  // 메시지 헬퍼
  const addSystem = (content) =>
    setMessages((prev) => [...prev, { type: 'system', content, timestamp: new Date().toLocaleTimeString() }]);
  const addAnalysis = (content) =>
    setMessages((prev) => [...prev, { type: 'analysis', content, timestamp: new Date().toLocaleTimeString() }]);
  const addChat = (sender, content) =>
    setMessages((prev) => [...prev, { sender, content, timestamp: new Date().toLocaleTimeString() }]);

  // 시뮬레이션(Mock)
  const runSimulation = () => {
    const mock = [
      ['scammer', '안녕하세요, 금융감독원입니다. 고객님의 계좌에 이상 거래가 감지되어 연락드렸습니다.'],
      ['victim', '네? 이상 거래요? 무슨 일인가요?'],
      ['scammer', '불법 출금 시도가 있었고 즉시 본인 인증을 해주셔야 합니다.'],
      ['victim', '정말인가요? 그럼 어떻게 해야 하나요?'],
      ['analysis', '⚠️ 판정: 기관사칭 수법 감지 - 긴급성 조성/권위 어필/정보 요구 패턴 일치']
    ];

    let i = 0;
    const interval = setInterval(() => {
      if (i < mock.length) {
        const [role, text] = mock[i];
        if (role === 'analysis') addAnalysis(text);
        else addChat(role, text);
        setProgress(((i + 1) / mock.length) * 100);
        i += 1;
      } else {
        clearInterval(interval);
        finishSimulation();
      }
    }, 1500);
  };

  const finishSimulation = () => {
    setSimulationState('FINISH');
    setSessionResult({
      isPhishing: true,
      technique: '기관사칭',
      confidence: 95,
      reasons: ['권위기관 사칭', '긴급성 조성', '개인정보 요구'],
      victimResponse: '속음',
      metrics: {
        messageCount: 5,
        persuasionAttempts: 3,
        defenseStrategies: 0,
        suspicionLevel: 2
      },
      agentUsed: true,
      agentLogs: [
        { timestamp: '00:01', type: 'ANALYZE', message: '피해자의 첫 반응을 분석 중... 경계심 수준: 낮음' },
        { timestamp: '00:03', type: 'STRATEGY', message: '권위 기관 사칭을 통한 신뢰도 구축 전략 적용' },
        { timestamp: '00:05', type: 'DETECT', message: '긴급성 조성 패턴 감지 - 보이스피싱 가능성 70%' },
        { timestamp: '00:07', type: 'WARNING', message: '개인정보 요구 시도 감지 - 위험도 상승' }
      ]
    });
  };

  // ─────────────────────────────────────────
  // 공통 UI 조각
  // ─────────────────────────────────────────
  const HudBar = ({ children }) => (
    <div
      className="flex items-center justify-between px-6 py-4 rounded-tl-3xl rounded-tr-3xl"
      style={{ backgroundColor: COLORS.panel, borderBottom: `1px solid ${COLORS.border}` }}
    >
      <div className="flex items-center gap-3">
        <span
          className="text-xs tracking-widest px-3 py-2 rounded"
          style={{
            color: COLORS.blurple,
            backgroundColor: 'rgba(88,101,242,.12)',
            border: `1px solid rgba(88,101,242,.3)`
          }}
        >
          CASE LOG
        </span>
        <span className="text-base font-medium" style={{ color: COLORS.sub }}>
          사건번호: SIM-{new Date().toISOString().slice(2,10).replace(/-/g,'')}
        </span>
      </div>
      <div className="flex items-center gap-2">
        <Shield size={20} color={COLORS.sub} />
      </div>
    </div>
  );

  const Badge = ({ children, tone = 'neutral' }) => {
    const tones = {
      neutral: { bg: 'rgba(63,65,71,.5)', bd: COLORS.border, fg: COLORS.text },
      primary: { bg: 'rgba(88,101,242,.12)', bd: 'rgba(88,101,242,.3)', fg: COLORS.blurple },
      warn: { bg: 'rgba(254,231,92,.12)', bd: 'rgba(254,231,92,.35)', fg: COLORS.warn },
      danger: { bg: 'rgba(237,66,69,.12)', bd: 'rgba(237,66,69,.35)', fg: COLORS.danger },
      success: { bg: 'rgba(87,242,135,.12)', bd: 'rgba(87,242,135,.35)', fg: COLORS.success }
    };
    const t = tones[tone] || tones.neutral;
    return (
      <span
        className="text-sm px-3 py-2 rounded font-medium"
        style={{ backgroundColor: t.bg, border: `1px solid ${t.bd}`, color: t.fg }}
      >
        {children}
      </span>
    );
  };

  const SelectCard = ({ title, subtitle, children }) => (
    <div
      className="w-full max-w-6xl mx-auto rounded-xl p-6"
      style={{
        backgroundColor: COLORS.panel,
        border: `1px solid ${COLORS.border}`,
        color: COLORS.text
      }}
    >
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-xl">{title}</h3>
        <Badge tone="primary">SELECT</Badge>
      </div>
      {subtitle && <p className="text-base mb-4" style={{ color: COLORS.sub }}>{subtitle}</p>}
      {children}
    </div>
  );

  const Chip = ({ active, label, onClick }) => (
    <button
      onClick={onClick}
      className="text-base px-4 py-2 rounded-full mr-3 mb-3 font-medium"
      style={{
        backgroundColor: active ? 'rgba(88,101,242,.18)' : 'rgba(63,65,71,.5)',
        color: active ? COLORS.blurple : COLORS.text,
        border: `1px solid ${active ? 'rgba(88,101,242,.35)' : COLORS.border}`
      }}
    >
      {label}
    </button>
  );

  // ─────────────────────────────────────────
  // 랜딩 페이지
  // ─────────────────────────────────────────
  const LandingPage = () => (
    <div
      className="relative min-h-screen flex items-center justify-center"
      style={{
        backgroundImage: `url(${bg})`,
        backgroundSize: 'cover',
        backgroundPosition: 'center',
      }}
    >
      {/* 🔹 어두운 반투명 오버레이 */}
      <div className="absolute inset-0 bg-black opacity-60" />
      {/* 🔹 컨텐츠 */}
      <div className="relative z-10 text-center px-6">
        <h1 className="text-5xl md:text-7xl font-extrabold text-white mb-6">
          보이스피싱 시뮬레이션
        </h1>
        <p className="text-xl md:text-2xl text-gray-200">
          실제 사례와 AI 에이전트를 기반으로 제작되었습니다.
        </p>
        <button
          onClick={() => setCurrentPage('simulator')}
          className="
            mt-12 px-10 py-4 rounded-2xl font-semibold text-lg
            bg-[#5865F2] text-white shadow-lg
            hover:bg-[#4752C4] hover:scale-105
            transition-all duration-300
          "
        >
          <Play className="inline mr-3" size={22} />
          시작하기
        </button>
      </div>
    </div>
  );

  // ─────────────────────────────────────────
  // 시뮬레이터 페이지 (대화창 내부에서 선택)
  // ─────────────────────────────────────────
  const SimulatorPage = () => {
    const needScenario = !selectedScenario;
    const needCharacter = !selectedCharacter;
    const [selectedTag, setSelectedTag] = useState(null);
    const filteredScenarios = useMemo(() => {
      if (!selectedTag) return scenarios;
      return scenarios.filter(
        (s) => s.type === selectedTag || (Array.isArray(s.tags) && s.tags.includes(selectedTag))
      );
    }, [selectedTag]);

    return (
      <div className="min-h-screen" style={{ backgroundColor: COLORS.bg, color: COLORS.text }}>
        <div className="container mx-auto px-6 py-12">
          <div
            className="
              w-full max-w-[1400px] mx-auto
              h-[calc(100vh-3rem)] md:h-[calc(100vh-4rem)] xl:h-[calc(100vh-6rem)]
              rounded-3xl shadow-2xl
              border border-[#3F4147] bg-[#2B2D31]
              flex flex-col min-h-0
            "
          >
            <HudBar />

            {/* 상단 라벨(시나리오/캐릭터 상태) */}
            <div
              className="px-6 py-4 flex items-center justify-between"
              style={{ backgroundColor: COLORS.panel, borderBottom: `1px dashed ${COLORS.border}` }}
            >
              <div className="flex items-center gap-3">
                <Badge tone={selectedScenario ? 'primary' : 'neutral'}>
                  {selectedScenario ? selectedScenario.name : '시나리오 미선택'}
                </Badge>
                <Badge tone={selectedCharacter ? 'success' : 'neutral'}>
                  {selectedCharacter ? selectedCharacter.name : '캐릭터 미선택'}
                </Badge>
              </div>
              {/* <div className="text-sm font-medium" style={{ color: COLORS.sub }}>
                상태: {simulationState}
              </div> */}
              <div className="flex items-center gap-2">
                {selectedScenario && simulationState === 'IDLE' && (
                <button
                  onClick={() => {
                    setSelectedScenario(null);
                    setSelectedTag?.(null);
                    addSystem('시나리오를 다시 선택하세요.');
                  }}
                  className="px-3 py-2 rounded-md text-sm font-medium border hover:opacity-90 transition"
                  style={{ backgroundColor: '#313338', borderColor: COLORS.border, color: COLORS.sub }}
                >
                  ← 시나리오 다시 선택
                </button>
              )}


  {/* ▶ 추가: 캐릭터 다시 선택 버튼 (IDLE일 때만 노출) */}
  {selectedCharacter && simulationState === 'IDLE' && (
    <button
      onClick={() => {
        setSelectedCharacter(null);      // 캐릭터만 초기화
        addSystem('캐릭터를 다시 선택하세요.');
      }}
      className="px-3 py-2 rounded-md text-sm font-medium border hover:opacity-90 transition"
      style={{ backgroundColor: '#313338', borderColor: COLORS.border, color: COLORS.sub }}
    >
      ← 캐릭터 다시 선택
    </button>
  )}

  {/* <span className="text-sm font-medium" style={{ color: COLORS.sub }}>
    상태: {simulationState}
  </span> */}
</div>

            </div>

            {/* 대화 영역 */}
            <div className="px-6 py-6 flex-1 min-h-0" style={{ backgroundColor: COLORS.bg }}>
              {/* ✅ 대화로그: 고정 높이 + 스크롤 */}
              <div
                ref={scrollContainerRef}
                className="h-full overflow-y-auto space-y-6"
              >
                {/* 시스템/채팅 메시지 렌더 */}
                {messages.map((message, index) => {
                  const isVictim = message.sender === 'victim';
                  const isScammer = message.sender === 'scammer';
                  const isSystem = message.type === 'system';
                  const isAnalysis = message.type === 'analysis';
                  return (
                    <div key={index} className={`flex ${isVictim ? 'justify-end' : 'justify-start'}`}>
                      <div
                        className={[
                          'max-w-md lg:max-w-lg px-5 py-3 rounded-2xl border',
                          isSystem ? 'mx-auto text-center' : ''
                        ].join(' ')}
                        style={{
                          backgroundColor: isSystem
                            ? 'rgba(88,101,242,.12)'
                            : isAnalysis
                              ? 'rgba(254,231,92,.12)'
                              : isVictim
                                ? COLORS.white
                                : '#313338',
                          color: isVictim ? COLORS.black : (isAnalysis ? COLORS.warn : COLORS.text),
                          border: `1px solid ${
                            isSystem ? 'rgba(88,101,242,.35)'
                              : isAnalysis ? 'rgba(254,231,92,.35)'
                              : COLORS.border
                          }`
                        }}
                      >
                        {/* 라벨 */}
                        {isScammer && (
                          <div className="flex items-center mb-2" style={{ color: COLORS.warn }}>
                            <span className="mr-2 text-lg">🎭</span>
                            <span className="text-sm font-medium" style={{ color: COLORS.sub }}>피싱범</span>
                          </div>
                        )}
                        {isVictim && selectedCharacter && (
                          <div className="flex items-center mb-2">
                            <span className="mr-2 text-lg">{selectedCharacter.avatar}</span>
                            <span className="text-sm font-medium" style={{ color: '#687078' }}>피해자</span>
                          </div>
                        )}
                        <p className="whitespace-pre-line text-base leading-relaxed">{message.content}</p>
                        <div className="text-xs mt-2 opacity-70" style={{ color: COLORS.sub }}>{message.timestamp}</div>
                      </div>
                    </div>
                  );
                })}

                {/* 대화창 내부 선택 UI - 시나리오 */}
                {needScenario && (
                  <div className="flex justify-start">
                    <SelectCard
                      title="시나리오 선택"
                      subtitle="유형 칩을 먼저 눌러 필터링한 뒤, 상세 시나리오를 선택하세요."
                    >
                      <div className="mb-4">
                        {['기관사칭', '가족·지인사칭', '대출빙자'].map((t) => (
                          <Chip
                            key={t}
                            active={selectedTag === t}
                            label={`#${t}`}
                            onClick={() => setSelectedTag(selectedTag === t ? null : t)}
                          />
                        ))}
                      </div>

                      {/* ✅ 시나리오 목록: 독립 스크롤 영역 */}
                      <div
                        className="
                          flex-1 min-h-0
                          space-y-4
                          overflow-y-auto pr-1
                        "
                        style={{ maxHeight: '100%' }}
                      >
                        {filteredScenarios.map((s) => (
                          <button
                            key={s.id}
                            onClick={() => {
                              setSelectedScenario(s);
                              addSystem(`시나리오 선택: ${s.name}\n이제 캐릭터를 선택하세요.`);
                            }}
                            className="w-full text-left rounded-lg p-4 hover:opacity-90"
                            style={{
                              backgroundColor: '#313338',
                              border: `1px solid ${COLORS.border}`,
                              color: COLORS.text
                            }}
                          >
                            <div className="flex items-center justify-between mb-2">
                              <span className="font-semibold text-lg">{s.name}</span>
                              <Badge tone="primary">{s.type}</Badge>
                            </div>
                            <p className="text-base leading-relaxed" style={{ color: COLORS.sub }}>
                              {s.description}
                            </p>
                          </button>
                        ))}
                      </div>
                    </SelectCard>
                  </div>
                )}

                {/* ── 핵심 수정 2: 캐릭터 목록은 ‘시나리오 선택 이후 & 캐릭터 미선택’에서만 렌더 ── */}
                {!needScenario && needCharacter && (
                  <div
                    className="
                      grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5
                      flex-1 min-h-0 overflow-y-auto pr-1
                    "
                    style={{ maxHeight: '100%' }}
                  >
                    {characters.map((c) => (
                      <button
                        key={c.id}
                        onClick={() => {
                          setSelectedCharacter(c);
                          addSystem(`캐릭터 선택: ${c.name}`);
                        }}
                        className="text-left group h-full"
                      >
                        <div
                          className="
                            flex flex-col h-full rounded-2xl overflow-hidden
                            border hover:border-[rgba(88,101,242,.45)] transition-colors
                          "
                          style={{ backgroundColor: '#313338', borderColor: COLORS.border }}
                        >
                          {/* 프로필 이미지 영역 */}
                          {c.photo ? (
                            <div
                              className="w-full h-44 bg-cover bg-center"
                              style={{ backgroundImage: `url(${c.photo})` }}
                            />
                          ) : (
                            <div
                              className="w-full h-44 flex items-center justify-center text-6xl"
                              style={{ backgroundColor: '#2A2C31' }}
                            >
                              {c.avatar ?? '👤'}
                            </div>
                          )}

                          {/* 본문(이름 + 메타) */}
                          <div className="p-4 flex flex-col gap-3">
                            <div className="flex items-center justify-between">
                              <span className="font-semibold text-lg text-white">{c.name}</span>
                              {/* 태그/배지(선택) */}
                              <span
                                className="text-xs px-2 py-1 rounded-md"
                                style={{
                                  color: COLORS.blurple,
                                  backgroundColor: 'rgba(88,101,242,.12)',
                                  border: '1px solid rgba(88,101,242,.35)'
                                }}
                              >
                                프로필
                              </span>
                            </div>

                            <div className="grid grid-cols-3 gap-2 text-sm" style={{ color: COLORS.sub }}>
                              <div className="truncate">
                                <span className="block text-[12px] opacity-70">연령</span>
                                <span className="font-medium text-[#DCDDDE]">{c.age}</span>
                              </div>
                              <div className="truncate">
                                <span className="block text-[12px] opacity-70">리터러시</span>
                                <span className="font-medium text-[#DCDDDE]">{c.literacy}</span>
                              </div>
                              <div className="truncate">
                                <span className="block text-[12px] opacity-70">성격</span>
                                <span className="font-medium text-[#DCDDDE]">{c.personality}</span>
                              </div>
                            </div>

                            {/* (선택) 요약/소개 문구 */}
                            {c.summary && (
                              <p className="text-sm leading-relaxed mt-1 line-clamp-2" style={{ color: COLORS.sub }}>
                                {c.summary}
                              </p>
                            )}
                          </div>
                        </div>
                      </button>
                    ))}
                  </div>
                )}

                {/* 선택 완료 → 시작 버튼 */}
                {selectedScenario && selectedCharacter && simulationState === 'IDLE' && (
                  <div className="flex justify-center">
                    <button
                      onClick={startSimulation}
                      className="px-8 py-3 rounded-lg font-semibold text-lg"
                      style={{
                        backgroundColor: COLORS.blurple,
                        color: COLORS.white,
                        boxShadow: '0 10px 24px rgba(88,101,242,.35)'
                      }}
                    >
                      <Play className="inline mr-3" size={20} />
                      시뮬레이션 시작
                    </button>
                  </div>
                )}
              </div>
            </div>

            {/* 하단 상태 바 */}
            <div
              className="px-6 py-4 flex items-center justify-between rounded-bl-3xl rounded-br-3xl"
              style={{ backgroundColor: COLORS.panel, borderTop: `1px solid ${COLORS.border}` }}
            >
              <div className="flex items-center gap-4">
                <Clock size={18} color={COLORS.sub} />
                <span className="text-base font-medium" style={{ color: COLORS.sub }}>
                  진행률: {Math.round(progress)}%
                </span>
                <div className="w-48 h-3 rounded-full overflow-hidden" style={{ backgroundColor: '#313338' }}>
                  <div
                    className="h-3 rounded-full transition-all duration-300"
                    style={{ width: `${progress}%`, backgroundColor: COLORS.blurple }}
                  />
                </div>
              </div>
              {/* <div className="text-base font-medium" style={{ color: COLORS.sub }}>
                상태: {simulationState}
              </div> */}
              <div className="flex items-center gap-3">
              <span className="text-base font-medium" style={{ color: COLORS.sub }}>
                상태: {simulationState}
                </span>
                {simulationState === 'FINISH' && (
              <button
              onClick={resetToSelection}
              className="px-4 py-2 rounded-lg text-sm font-semibold transition-all duration-200
              bg-[#5865F2] text-white hover:bg-[#4752C4] hover:shadow-lg"
              >
              다시 선택하기
              </button>
              )}
              </div>
            </div>
          </div>
        </div>

        {/* 결과 배너 */}
        {sessionResult && (
          <div className="fixed top-6 left-1/2 -translate-x-1/2 z-50">
            <div
              className="px-8 py-4 rounded-xl"
              style={{
                backgroundColor: COLORS.panel,
                border: `1px solid ${COLORS.border}`,
                boxShadow: '0 10px 24px rgba(0,0,0,.35)',
                color: COLORS.text
              }}
            >
              <div className="flex items-center gap-5">
                <div className="flex items-center gap-3">
                  {sessionResult.isPhishing ? (
                    <AlertTriangle size={24} color={COLORS.warn} />
                  ) : (
                    <Check size={24} color={COLORS.success} />
                  )}
                  <span
                    className="font-semibold text-lg"
                    style={{ color: sessionResult.isPhishing ? COLORS.warn : COLORS.success }}
                  >
                    {sessionResult.isPhishing ? '피싱 감지' : '정상 대화'}
                  </span>
                </div>
                <button
                  onClick={() => setCurrentPage('report')}
                  className="px-6 py-2 rounded-md text-base font-medium"
                  style={{ backgroundColor: COLORS.blurple, color: COLORS.white }}
                >
                  리포트 보기
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  };

  // ─────────────────────────────────────────
  // 리포트 페이지
  // ─────────────────────────────────────────
  const ReportPage = () => (
  <div className="min-h-screen bg-[#1E1F22] text-[#DCDDDE]">
    {/* 페이지 컨테이너를 flex-col로 전환 */}
    <div className="mx-auto min-h-screen p-6 md:p-10 xl:p-12 flex flex-col">
      {/* 상단 헤더 */}
      <div className="flex items-center justify-between mb-10">
        <h1 className="text-4xl font-bold">시뮬레이션 리포트</h1>
        <button
          onClick={() => setCurrentPage('simulator')}
          className="px-6 py-3 rounded-lg text-lg font-medium"
          style={{ backgroundColor: COLORS.blurple, color: COLORS.white }}
        >
          돌아가기
        </button>
      </div>

      {sessionResult && (
        /* 핵심: 남은 세로공간을 꽉 채우고, 오른쪽만 스크롤 */
        <div className="flex gap-10 flex-1 overflow-hidden">
          {/* ───────── 왼쪽: 고정(스크롤 없음) ───────── */}
          <div
            className="w-full lg:w-1/3 flex-shrink-0 space-y-8 pr-6"
            style={{ borderRight: `1px solid ${COLORS.border}` }}
          >
            {/* 피싱 유형 */}
            <div
              className="rounded-2xl p-8"
              style={{ backgroundColor: COLORS.panel, border: `1px solid ${COLORS.border}` }}
            >
              <h2 className="text-2xl font-semibold mb-5 flex items-center">
                <Shield className="mr-3" size={26} />
                피싱 유형
              </h2>
              <div className="text-xl font-medium" style={{ color: COLORS.blurple }}>
                {sessionResult.phishingType || '음성 피싱'}
              </div>
            </div>

            {/* 피해자 메타 정보 */}
            <div
              className="rounded-2xl p-8"
              style={{ backgroundColor: COLORS.panel, border: `1px solid ${COLORS.border}` }}
            >
              <h2 className="text-2xl font-semibold mb-5 flex items-center">
                <User className="mr-3" size={26} />
                피해자 정보
              </h2>
              <div className="space-y-5">
                <div className="flex justify-center">
                  <div
                    className="w-24 h-24 rounded-full flex items-center justify-center"
                    style={{ backgroundColor: COLORS.border }}
                  >
                    <User size={48} color={COLORS.text} />
                  </div>
                </div>
                <div className="text-center">
                  <div className="font-semibold text-xl mb-3">
                    {sessionResult.victimName || '김철수'}
                  </div>
                  <div className="text-base space-y-2">
                    <div>나이: {sessionResult.victimAge || '45세'}</div>
                    <div>직업: {sessionResult.victimJob || '회사원'}</div>
                  </div>
                </div>
                <div>
                  <h3 className="font-semibold text-lg mb-3">성격 특성</h3>
                  <div className="flex flex-wrap gap-3">
                    {(sessionResult.victimTraits || ['신중함', '호기심 많음', '기술에 익숙하지 않음']).map((trait, i) => (
                      <span
                        key={i}
                        className="px-4 py-2 rounded-full text-sm font-medium"
                        style={{ backgroundColor: COLORS.border }}
                      >
                        {trait}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* 에이전트 사용 여부 */}
            <div
              className="rounded-2xl p-8"
              style={{ backgroundColor: COLORS.panel, border: `1px solid ${COLORS.border}` }}
            >
              <h2 className="text-2xl font-semibold mb-5 flex items-center">
                <Bot className="mr-3" size={26} />
                AI 에이전트
              </h2>
              <div className="flex items-center gap-4">
                <Badge tone={sessionResult.agentUsed ? 'success' : 'neutral'}>
                  {sessionResult.agentUsed ? '사용' : '미사용'}
                </Badge>
                {sessionResult.agentUsed && (
                  <span className="text-base text-gray-500">GPT-4 기반</span>
                )}
              </div>
            </div>
          </div>

          {/* ───────── 오른쪽: 스크롤 영역 ───────── */}
          {/* 핵심: min-h-0 + overflow-y-auto */}
          <div className="flex-1 min-h-0 overflow-y-auto space-y-8 pr-2">
            {/* 피싱 판정 결과 */}
            <div
              className="rounded-2xl p-8"
              style={{ backgroundColor: COLORS.panel, border: `1px solid ${COLORS.border}` }}
            >
              <h2 className="text-2xl font-semibold mb-5 flex items-center">
                <AlertTriangle className="mr-3" size={26} />
                피싱 판정 결과
              </h2>
              <div className="space-y-5">
                <div className="flex items-center gap-5">
                  <Badge tone={sessionResult.isPhishing ? 'danger' : 'success'}>
                    {sessionResult.isPhishing ? '피싱 감지' : '정상 대화'}
                  </Badge>
                  <div className="text-3xl font-bold">신뢰도 {sessionResult.confidence}%</div>
                </div>
                <div>
                  <h3 className="font-semibold text-lg mb-4">핵심 근거</h3>
                  <ul className="space-y-3">
                    {sessionResult.reasons.map((r, i) => (
                      <li key={i} className="flex items-start gap-3">
                        <ChevronRight size={18} color={COLORS.blurple} className="mt-1 flex-shrink-0" />
                        <span className="text-base">{r}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>

            {/* 예방책 */}
            <div
              className="rounded-2xl p-8"
              style={{ backgroundColor: COLORS.panel, border: `1px solid ${COLORS.border}` }}
            >
              <h2 className="text-2xl font-semibold mb-5 flex items-center">
                <Shield className="mr-3" size={26} />
                예방책 및 대응 방법
              </h2>
              <ul className="space-y-4">
                {(sessionResult.prevention || [
                  '개인정보를 요구하는 전화에 즉시 응답하지 말고 공식 채널로 확인',
                  '금융 거래는 반드시 은행 공식 앱이나 방문을 통해 진행',
                  '의심스러운 링크나 파일은 절대 클릭하지 않기',
                  '가족이나 지인에게 상황을 공유하여 객관적 판단 받기'
                ]).map((prevention, i) => (
                  <li key={i} className="flex items-start gap-3">
                    <div
                      className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 mt-1"
                      style={{ backgroundColor: COLORS.blurple }}
                    >
                      <span className="text-white text-base font-bold">{i + 1}</span>
                    </div>
                    <span className="text-base leading-relaxed">{prevention}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* 사례 출처 */}
            <div
              className="rounded-2xl p-8"
              style={{ backgroundColor: COLORS.panel, border: `1px solid ${COLORS.border}` }}
            >
              <h2 className="text-2xl font-semibold mb-5 flex items-center">
                <ExternalLink className="mr-3" size={26} />
                사례 출처 및 참고자료
              </h2>
              <div className="space-y-5">
                <div className="p-5 rounded-lg" style={{ backgroundColor: COLORS.bg }}>
                  <h3 className="font-semibold text-lg mb-3">참고 사례</h3>
                  <p className="text-base mb-4 leading-relaxed">
                    {sessionResult.caseSource || '본 시뮬레이션은 실제 보이스피싱 사례를 바탕으로 제작되었습니다.'}
                  </p>
                  <div className="space-y-3">
                    <div className="flex items-center gap-3">
                      <span className="text-base font-medium">출처:</span>
                      <span className="text-base">{sessionResult.source || '금융감독원 보이스피싱 사례집'}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-base font-medium">날짜:</span>
                      <span className="text-base">{sessionResult.sourceDate || '2024.03.15'}</span>
                    </div>
                  </div>
                </div>
                <div className="flex gap-3">
                  <button className="flex-1 px-5 py-3 rounded-lg text-base font-medium" style={{ backgroundColor: COLORS.border }}>
                    상세 사례 보기
                  </button>
                  <button className="flex-1 px-5 py-3 rounded-lg text-base font-medium" style={{ backgroundColor: COLORS.blurple, color: COLORS.white }}>
                    관련 교육자료
                  </button>
                </div>
              </div>
            </div>

            {/* 에이전트 로그 (오른쪽 전체 스크롤을 사용하므로 내부 max-h/스크롤 제거) */}
            {sessionResult.agentUsed && sessionResult.agentLogs && (
              <div
                className="rounded-2xl p-8"
                style={{ backgroundColor: COLORS.panel, border: `1px solid ${COLORS.border}` }}
              >
                <h2 className="text-2xl font-semibold mb-5 flex items-center">
                  <Terminal className="mr-3" size={26} />
                  AI 에이전트 로그
                </h2>
                <div className="space-y-4">
                  {sessionResult.agentLogs.map((log, i) => (
                    <div key={i} className="text-sm">
                      <div className="flex items-center gap-3 mb-2">
                        <span
                          className="text-xs px-3 py-2 rounded font-mono"
                          style={{ backgroundColor: COLORS.border }}
                        >
                          {log.timestamp || `${String(i + 1).padStart(2, '0')}:00`}
                        </span>
                        <span className="text-sm font-medium" style={{ color: COLORS.blurple }}>
                          {log.type || 'THINKING'}
                        </span>
                      </div>
                      <div
                        className="pl-5 py-3 rounded font-mono text-sm leading-relaxed"
                        style={{
                          backgroundColor: COLORS.bg,
                          borderLeft: `3px solid ${COLORS.blurple}`
                        }}
                      >
                        {log.message || log}
                      </div>
                    </div>
                  ))}
                </div>
                <div className="mt-5 pt-4 border-t" style={{ borderColor: COLORS.border }}>
                  <div className="flex items-center justify-between text-sm">
                    <span>총 {sessionResult.agentLogs.length}개 로그</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  </div>
);


  return (
    <div className="font-sans">
      {currentPage === 'landing' && <LandingPage />}
      {currentPage === 'simulator' && <SimulatorPage />}
      {currentPage === 'report' && <ReportPage />}
    </div>
  );
};

export default App;
