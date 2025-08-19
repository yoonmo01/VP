import { useState, useMemo } from "react";
import { Play, Clock, X, Check, AlertTriangle } from "lucide-react";
import HudBar from "./HudBar";
import Badge from "./Badge";
import SelectedCard from "./SelectedCard";
import Chip from "./Chip";
import MessageBubble from "./MessageBubble";
import SpinnerMessage from "./SpinnerMessage";

// Victims 이미지 동적 import 함수
const getVictimImage = (photoPath) => {
    if (!photoPath) return null;
    try {
        // "/static/images/victims/2.png" -> "2.png" 추출
        const fileName = photoPath.split("/").pop();
        if (fileName) {
            // 동적 import로 assets/victims 폴더의 이미지 로드
            return new URL(`./assets/victims/${fileName}`, import.meta.url)
                .href;
        }
    } catch (error) {
        console.warn("이미지 로드 실패:", error);
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
    resetToSelection,
    startSimulation,
    scenarios,
    characters,
    agentModalVisible,
    setAgentModalVisible,
    setAgentUsed,
    scrollContainerRef,
    addSystem,
}) => {
    const needScenario = !selectedScenario;
    const needCharacter = !selectedCharacter;
    const [selectedTag, setSelectedTag] = useState(null);

    const filteredScenarios = useMemo(() => {
        if (!selectedTag) return scenarios;
        return scenarios.filter(
            (s) =>
                s.type === selectedTag ||
                (Array.isArray(s.tags) && s.tags.includes(selectedTag)),
        );
    }, [selectedTag, scenarios]);

    // ✅ NEW: 메시지 → 렌더 정보 정규화 (라벨/사이드/타임스탬프 보정)
    const normalizeMessage = (m) => {
        // 시스템/분석 메시지는 그대로
        if (m?.type === "system" || m?.type === "analysis") {
            return {
                ...m,
                _kind: m.type,
                label: m.type === "system" ? "시스템" : "분석",
                side: "center",
                timestamp: m.timestamp,
            };
        }

        const role = (m?.sender || m?.role || "").toLowerCase(); // "offender"|"victim"
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
            (role === "offender"
                ? "left"
                : role === "victim"
                  ? "right"
                  : "left");

        // created_kst를 문자열로 받는 케이스 보정
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

    // ✅ NEW: 시작 버튼 보호 — 실행 중/준비 중엔 비활성화
    const startDisabled =
        simulationState === "PREPARE" || simulationState === "RUNNING";

    return (
        <div
            className="min-h-screen"
            style={{ backgroundColor: COLORS.bg, color: COLORS.text }}
        >
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
                    <HudBar COLORS={COLORS} />

                    <div
                        className="px-6 py-4 flex items-center justify-between"
                        style={{
                            backgroundColor: COLORS.panel,
                            borderBottom: `1px dashed ${COLORS.border}`,
                        }}
                    >
                        <div className="flex items-center gap-3">
                            <Badge
                                tone={selectedScenario ? "primary" : "neutral"}
                                COLORS={COLORS}
                            >
                                {selectedScenario
                                    ? selectedScenario.name
                                    : "시나리오 미선택"}
                            </Badge>
                            <Badge
                                tone={selectedCharacter ? "success" : "neutral"}
                                COLORS={COLORS}
                            >
                                {selectedCharacter
                                    ? selectedCharacter.name
                                    : "캐릭터 미선택"}
                            </Badge>
                        </div>
                        <div className="flex items-center gap-2">
                            {selectedScenario && simulationState === "IDLE" && (
                                <button
                                    onClick={() => {
                                        setSelectedScenario(null);
                                        setSelectedTag?.(null);
                                        addSystem(
                                            "시나리오를 다시 선택하세요.",
                                        );
                                    }}
                                    className="px-3 py-2 rounded-md text-sm font-medium border hover:opacity-90 transition"
                                    style={{
                                        backgroundColor: "#313338",
                                        borderColor: COLORS.border,
                                        color: COLORS.sub,
                                    }}
                                >
                                    ← 시나리오 다시 선택
                                </button>
                            )}
                            {selectedCharacter &&
                                simulationState === "IDLE" && (
                                    <button
                                        onClick={() => {
                                            setSelectedCharacter(null);
                                            addSystem(
                                                "캐릭터를 다시 선택하세요.",
                                            );
                                        }}
                                        className="px-3 py-2 rounded-md text-sm font-medium border hover:opacity-90 transition"
                                        style={{
                                            backgroundColor: "#313338",
                                            borderColor: COLORS.border,
                                            color: COLORS.sub,
                                        }}
                                    >
                                        ← 캐릭터 다시 선택
                                    </button>
                                )}
                        </div>
                    </div>

                    <div
                        className="px-6 py-6 flex-1 min-h-0"
                        style={{ backgroundColor: COLORS.bg }}
                    >
                        <div
                            ref={scrollContainerRef}
                            className="h-full overflow-y-auto space-y-6"
                        >
                            {/* 스피너 메시지 (로그가 없을 때만 표시) */}
                            {!messages.some((m) => m.type === "chat") && (
                                <SpinnerMessage
                                    simulationState={simulationState}
                                    COLORS={COLORS}
                                />
                            )}

                            {/* ✅ CHANGED: message를 normalize 해서 MessageBubble로 전달 */}
                            {messages.map((m, index) => {
                                const nm = normalizeMessage(m);
                                const victimImageUrl = selectedCharacter
                                    ? getVictimImage(
                                          selectedCharacter.photo_path,
                                      )
                                    : null;
                                return (
                                    <MessageBubble
                                        key={index}
                                        // 기존 props
                                        message={nm}
                                        selectedCharacter={selectedCharacter}
                                        victimImageUrl={victimImageUrl}
                                        COLORS={COLORS}
                                        // ✅ NEW: 명시적 전달 (MessageBubble이 이 필드들을 쓰도록)
                                        label={nm.label}
                                        side={nm.side}
                                        role={nm.role}
                                    />
                                );
                            })}

                            {needScenario && (
                                <div className="flex justify-start">
                                    <SelectedCard
                                        title="시나리오 선택"
                                        subtitle="유형 칩을 먼저 눌러 필터링한 뒤, 상세 시나리오를 선택하세요."
                                        COLORS={COLORS}
                                    >
                                        <div className="mb-4">
                                            {[
                                                "기관 사칭형",
                                                "가족·지인 사칭",
                                                "대출사기형",
                                            ].map((t) => (
                                                <Chip
                                                    key={t}
                                                    active={selectedTag === t}
                                                    label={`${t}`}
                                                    onClick={() =>
                                                        setSelectedTag(
                                                            selectedTag === t
                                                                ? null
                                                                : t,
                                                        )
                                                    }
                                                    COLORS={COLORS}
                                                />
                                            ))}
                                        </div>
                                        <div
                                            className="flex-1 min-h-0 space-y-4 overflow-y-auto pr-1"
                                            style={{ maxHeight: "100%" }}
                                        >
                                            {filteredScenarios.map((s) => (
                                                <button
                                                    key={s.id}
                                                    onClick={async () => {
                                                        setSelectedScenario(s);

                                                        try {
                                                            const res =
                                                                await fetch(
                                                                    `/api/offenders/by-type/${encodeURIComponent(
                                                                        s.type,
                                                                    )}`,
                                                                );
                                                            if (!res.ok)
                                                                throw new Error(
                                                                    "서버 오류",
                                                                );
                                                            const offenders =
                                                                await res.json();

                                                            console.log(
                                                                "조회된 offenders:",
                                                                offenders,
                                                            );

                                                            addSystem(
                                                                `${s.type} 유형 공격자 ${offenders.length}명 조회됨 (id: ${offenders
                                                                    .map(
                                                                        (o) =>
                                                                            o.id,
                                                                    )
                                                                    .join(
                                                                        ",",
                                                                    )})`,
                                                            );

                                                            // 필요 시 setCharacters(offenders) 로 교체 가능
                                                        } catch (err) {
                                                            console.error(err);
                                                            addSystem(
                                                                "공격자 조회 실패",
                                                            );
                                                        }
                                                    }}
                                                    className="w-full text-left rounded-lg p-4 hover:opacity-90"
                                                    style={{
                                                        backgroundColor:
                                                            "#313338",
                                                        border: `1px solid ${COLORS.border}`,
                                                        color: COLORS.text,
                                                    }}
                                                >
                                                    <div className="flex items-center justify-between mb-2">
                                                        <span className="font-semibold text-lg">
                                                            {s.name}
                                                        </span>
                                                        <Badge
                                                            tone="primary"
                                                            COLORS={COLORS}
                                                        >
                                                            {s.type}
                                                        </Badge>
                                                    </div>
                                                    <p
                                                        className="text-base leading-relaxed"
                                                        style={{
                                                            color: COLORS.sub,
                                                        }}
                                                    >
                                                        {s.profile.purpose}
                                                    </p>
                                                </button>
                                            ))}
                                        </div>
                                    </SelectedCard>
                                </div>
                            )}

                            {!needScenario && needCharacter && (
                                <div
                                    className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 flex-1 min-h-0 overflow-y-auto pr-1"
                                    style={{ maxHeight: "100%" }}
                                >
                                    {characters.map((c) => (
                                        <button
                                            key={c.id}
                                            onClick={() => {
                                                setSelectedCharacter(c);
                                                setTimeout(() => {
                                                    setAgentModalVisible(true);
                                                }, 0);
                                            }}
                                        >
                                            <div
                                                className="
                        flex flex-col h-full rounded-2xl overflow-hidden
                        border hover:border-[rgba(88,101,242,.45)] transition-colors
                    "
                                                style={{
                                                    backgroundColor: "#313338",
                                                    borderColor: COLORS.border,
                                                }}
                                            >
                                                {getVictimImage(
                                                    c.photo_path,
                                                ) ? (
                                                    <div
                                                        className="w-full h-44 bg-cover bg-center"
                                                        style={{
                                                            backgroundImage: `url(${getVictimImage(c.photo_path)})`,
                                                        }}
                                                    />
                                                ) : (
                                                    <div
                                                        className="w-full h-44 flex items-center justify-center text-6xl"
                                                        style={{
                                                            backgroundColor:
                                                                "#2A2C31",
                                                        }}
                                                    >
                                                        {c.avatar ?? "👤"}
                                                    </div>
                                                )}
                                                <div className="p-4 flex flex-col gap-3">
                                                    <div className="flex items-center justify-between">
                                                        <span className="font-semibold text-lg text-white">
                                                            {c.name}
                                                        </span>
                                                        <span
                                                            className="text-xs px-2 py-1 rounded-md"
                                                            style={{
                                                                color: COLORS.blurple,
                                                                backgroundColor:
                                                                    "rgba(88,101,242,.12)",
                                                                border: "1px solid rgba(88,101,242,.35)",
                                                            }}
                                                        >
                                                            프로필
                                                        </span>
                                                    </div>

                                                    {/* 기본 정보 - 한 줄에 하나씩 */}
                                                    <div
                                                        className="space-y-2 text-sm"
                                                        style={{
                                                            color: COLORS.sub,
                                                        }}
                                                    >
                                                        <div className="flex justify-between items-center">
                                                            <span className="text-[12px] opacity-70">
                                                                나이
                                                            </span>
                                                            <span className="font-medium text-[#DCDDDE]">
                                                                {c.meta.age}
                                                            </span>
                                                        </div>
                                                        <div className="flex justify-between items-center">
                                                            <span className="text-[12px] opacity-70">
                                                                성별
                                                            </span>
                                                            <span className="font-medium text-[#DCDDDE]">
                                                                {c.meta.gender}
                                                            </span>
                                                        </div>
                                                        <div className="flex justify-between items-center">
                                                            <span className="text-[12px] opacity-70">
                                                                거주지
                                                            </span>
                                                            <span className="font-medium text-[#DCDDDE] truncate ml-2">
                                                                {c.meta.address}
                                                            </span>
                                                        </div>
                                                        <div className="flex justify-between items-center">
                                                            <span className="text-[12px] opacity-70">
                                                                학력
                                                            </span>
                                                            <span className="font-medium text-[#DCDDDE] truncate ml-2">
                                                                {
                                                                    c.meta
                                                                        .education
                                                                }
                                                            </span>
                                                        </div>
                                                    </div>

                                                    {/* 지식 정보 */}
                                                    <div>
                                                        <span
                                                            className="block text-[12px] opacity-70 mb-2"
                                                            style={{
                                                                color: COLORS.sub,
                                                            }}
                                                        >
                                                            지식
                                                        </span>
                                                        <div className="space-y-1">
                                                            {Array.isArray(
                                                                c?.knowledge
                                                                    ?.comparative_notes,
                                                            ) &&
                                                            c.knowledge
                                                                .comparative_notes
                                                                .length > 0 ? (
                                                                c.knowledge.comparative_notes.map(
                                                                    (
                                                                        note,
                                                                        idx,
                                                                    ) => (
                                                                        <div
                                                                            key={
                                                                                idx
                                                                            }
                                                                            className="text-sm font-medium text-[#DCDDDE] leading-relaxed"
                                                                        >
                                                                            •{" "}
                                                                            {
                                                                                note
                                                                            }
                                                                        </div>
                                                                    ),
                                                                )
                                                            ) : (
                                                                <div className="text-sm text-[#B5BAC1]">
                                                                    비고 없음
                                                                </div>
                                                            )}
                                                        </div>
                                                    </div>

                                                    {/* 성격 정보 (OCEAN) */}
                                                    <div>
                                                        <span
                                                            className="block text-[12px] opacity-70 mb-2"
                                                            style={{
                                                                color: COLORS.sub,
                                                            }}
                                                        >
                                                            성격
                                                        </span>
                                                        <div className="space-y-1">
                                                            {c?.traits?.ocean &&
                                                            typeof c.traits
                                                                .ocean ===
                                                                "object" ? (
                                                                Object.entries(
                                                                    c.traits
                                                                        .ocean,
                                                                ).map(
                                                                    ([
                                                                        key,
                                                                        val,
                                                                    ]) => {
                                                                        const labelMap =
                                                                            {
                                                                                openness:
                                                                                    "개방성",
                                                                                neuroticism:
                                                                                    "신경성",
                                                                                extraversion:
                                                                                    "외향성",
                                                                                agreeableness:
                                                                                    "친화성",
                                                                                conscientiousness:
                                                                                    "성실성",
                                                                            };
                                                                        const label =
                                                                            labelMap[
                                                                                key
                                                                            ] ??
                                                                            key;
                                                                        return (
                                                                            <div
                                                                                key={
                                                                                    key
                                                                                }
                                                                                className="flex justify-between items-center"
                                                                            >
                                                                                <span className="text-[12px] opacity-70">
                                                                                    {
                                                                                        label
                                                                                    }
                                                                                </span>
                                                                                <span className="text-sm font-medium text-[#DCDDDE]">
                                                                                    {
                                                                                        val
                                                                                    }
                                                                                </span>
                                                                            </div>
                                                                        );
                                                                    },
                                                                )
                                                            ) : (
                                                                <div className="text-sm text-[#B5BAC1]">
                                                                    성격 정보
                                                                    없음
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
                            {agentModalVisible && (
                                <div className="fixed inset-0 flex items-center justify-center bg-black bg-opacity-50 z-50">
                                    <div
                                        className="bg-[#2B2D31] p-6 rounded-lg border"
                                        style={{ borderColor: COLORS.border }}
                                    >
                                        <h3 className="text-xl font-semibold mb-4 text-white">
                                            AI 에이전트를 사용하시겠습니까?
                                        </h3>
                                        <div className="flex justify-end gap-4">
                                            <button
                                                onClick={() => {
                                                    setAgentUsed(true);
                                                    setAgentModalVisible(false);
                                                }}
                                                className="px-4 py-2 rounded bg-[#5865F2] text-white"
                                            >
                                                예
                                            </button>
                                            <button
                                                onClick={() => {
                                                    setAgentUsed(false);
                                                    setAgentModalVisible(false);
                                                }}
                                                className="px-4 py-2 rounded bg-[#313338] text-[#DCDDDE]"
                                            >
                                                아니오
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            )}

                            {selectedScenario &&
                                selectedCharacter &&
                                simulationState === "IDLE" && (
                                    <div className="flex justify-center">
                                        <button
                                            onClick={startSimulation}
                                            disabled={startDisabled} // ✅ NEW: 실행 중엔 비활성화
                                            className={`px-8 py-3 rounded-lg font-semibold text-lg ${
                                                startDisabled
                                                    ? "opacity-60 cursor-not-allowed"
                                                    : ""
                                            }`}
                                            style={{
                                                backgroundColor: COLORS.blurple,
                                                color: COLORS.white,
                                                boxShadow:
                                                    "0 10px 24px rgba(88,101,242,.35)",
                                            }}
                                        >
                                            <Play
                                                className="inline mr-3"
                                                size={20}
                                            />
                                            시뮬레이션 시작
                                        </button>
                                    </div>
                                )}
                        </div>
                    </div>

                    <div
                        className="px-6 py-4 flex items-center justify-between rounded-bl-3xl rounded-br-3xl"
                        style={{
                            backgroundColor: COLORS.panel,
                            borderTop: `1px solid ${COLORS.border}`,
                        }}
                    >
                        <div className="flex items-center gap-4">
                            <Clock size={18} color={COLORS.sub} />
                            <span
                                className="text-base font-medium"
                                style={{ color: COLORS.sub }}
                            >
                                진행률: {Math.round(progress)}%
                            </span>
                            <div
                                className="w-48 h-3 rounded-full overflow-hidden"
                                style={{ backgroundColor: "#313338" }}
                            >
                                <div
                                    className="h-3 rounded-full transition-all duration-300"
                                    style={{
                                        width: `${progress}%`,
                                        backgroundColor: COLORS.blurple,
                                    }}
                                />
                            </div>
                        </div>
                        <div className="flex items-center gap-3">
                            <span
                                className="text-base font-medium"
                                style={{ color: COLORS.sub }}
                            >
                                상태: {simulationState}
                            </span>
                            {simulationState === "FINISH" && (
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

            {sessionResult && progress >= 100 && (
                <div className="fixed top-6 left-1/2 -translate-x-1/2 z-50">
                    <div
                        className="px-8 py-4 rounded-xl"
                        style={{
                            backgroundColor: COLORS.panel,
                            border: `1px solid ${COLORS.border}`,
                            boxShadow: "0 10px 24px rgba(0,0,0,.35)",
                            color: COLORS.text,
                        }}
                    >
                        <div className="flex items-center gap-5">
                            <div className="flex items-center gap-3">
                                {sessionResult.isPhishing ? (
                                    <AlertTriangle
                                        size={24}
                                        color={COLORS.warn}
                                    />
                                ) : (
                                    <Check size={24} color={COLORS.success} />
                                )}
                                <span
                                    className="font-semibold text-lg"
                                    style={{
                                        color: sessionResult.isPhishing
                                            ? COLORS.warn
                                            : COLORS.success,
                                    }}
                                >
                                    {sessionResult.isPhishing
                                        ? "피싱 감지"
                                        : "정상 대화"}
                                </span>
                            </div>
                            <button
                                onClick={() => setCurrentPage("report")}
                                className="px-6 py-2 rounded-md text-base font-medium"
                                style={{
                                    backgroundColor: COLORS.blurple,
                                    color: COLORS.white,
                                }}
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

export default SimulatorPage;
