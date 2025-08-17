import {
    User,
    Bot,
    Terminal,
    ExternalLink,
    Shield,
    AlertTriangle,
    ChevronRight,
} from "lucide-react";
import Badge from "./Badge";

const ReportPage = ({
    COLORS,
    setCurrentPage,
    sessionResult,
    scenarios,
    defaultCaseData,
    selectedScenario,
    selectedCharacter,
}) => {
    // 1) case 기반 판정 (우선순위: defaultCaseData.case.phishing -> sessionResult.isPhishing -> false)
    const casePhishing =
        typeof defaultCaseData?.case?.phishing === "boolean"
            ? defaultCaseData.case.phishing
            : typeof sessionResult?.isPhishing === "boolean"
              ? sessionResult.isPhishing
              : false;

    // 2) evidence (우선 defaultCaseData.case.evidence -> sessionResult.case?.evidence -> sessionResult.evidence)
    const caseEvidence =
        defaultCaseData?.case?.evidence ??
        sessionResult?.case?.evidence ??
        sessionResult?.evidence ??
        null;

    // 3) 피해자 정보: selectedCharacter 우선, 없으면 sessionResult 폴백
    const victimFromSession = sessionResult
        ? {
              name: sessionResult.victimName ?? "알 수 없음",
              meta: {
                  age: sessionResult.victimAge ?? "-",
                  gender: sessionResult.victimGender ?? "-",
                  address: sessionResult.victimAddress ?? "-",
                  education: sessionResult.victimEducation ?? "-",
                  job: sessionResult.victimJob ?? "-",
              },
              traits: {
                  ocean: undefined,
                  list: sessionResult.victimTraits ?? [],
              },
          }
        : null;

    const victim = selectedCharacter ??
        victimFromSession ?? {
            name: "알 수 없음",
            meta: {
                age: "-",
                gender: "-",
                address: "-",
                education: "-",
                job: "-",
            },
            traits: { ocean: undefined, list: [] },
        };

    // 4) OCEAN 라벨 맵 및 항목 배열화
    const oceanLabelMap = {
        openness: "개방성",
        neuroticism: "신경성",
        extraversion: "외향성",
        agreeableness: "친화성",
        conscientiousness: "성실성",
    };

    const oceanEntries =
        victim?.traits?.ocean && typeof victim.traits.ocean === "object"
            ? Object.entries(victim.traits.ocean).map(([k, v]) => ({
                  label: oceanLabelMap[k] ?? k,
                  value: v,
              }))
            : [];

    const traitList = Array.isArray(victim?.traits?.list)
        ? victim.traits.list
        : [];

    // 5) 피싱 유형 텍스트 (selectedScenario 우선, 없으면 scenarios[0])
    const phishingTypeText =
        selectedScenario?.type ??
        (Array.isArray(scenarios)
            ? (scenarios[0]?.type ?? "피싱 유형")
            : "피싱 유형");

    return (
        <div className="min-h-screen bg-[#1E1F22] text-[#DCDDDE]">
            <div className="mx-auto min-h-screen p-6 md:p-10 xl:p-12 flex flex-col">
                <div className="flex items-center justify-between mb-10">
                    <h1 className="text-4xl font-bold">시뮬레이션 리포트</h1>
                    <button
                        onClick={() => setCurrentPage("simulator")}
                        className="px-6 py-3 rounded-lg text-lg font-medium"
                        style={{
                            backgroundColor: COLORS.blurple,
                            color: COLORS.white,
                        }}
                    >
                        돌아가기
                    </button>
                </div>

                {sessionResult ? (
                    <div className="flex gap-10 flex-1 overflow-hidden">
                        {/* 왼쪽 패널 */}
                        <div
                            className="w-full lg:w-1/3 flex-shrink-0 space-y-8 pr-6"
                            style={{
                                borderRight: `1px solid ${COLORS.border}`,
                            }}
                        >
                            {/* 피싱 유형 */}
                            <div
                                className="rounded-2xl p-8"
                                style={{
                                    backgroundColor: COLORS.panel,
                                    border: `1px solid ${COLORS.border}`,
                                }}
                            >
                                <h2 className="text-2xl font-semibold mb-5 flex items-center">
                                    <Shield className="mr-3" size={26} />
                                    피싱 유형
                                </h2>
                                <div
                                    className="text-xl font-medium"
                                    style={{ color: COLORS.blurple }}
                                >
                                    {phishingTypeText}
                                </div>
                            </div>

                            {/* 피해자 정보 */}
                            <div
                                className="rounded-2xl p-8"
                                style={{
                                    backgroundColor: COLORS.panel,
                                    border: `1px solid ${COLORS.border}`,
                                }}
                            >
                                <h2 className="text-2xl font-semibold mb-5 flex items-center">
                                    <User className="mr-3" size={26} />
                                    피해자 정보
                                </h2>

                                <div className="space-y-5">
                                    <div className="flex justify-center">
                                        <div
                                            className="w-24 h-24 rounded-full flex items-center justify-center"
                                            style={{
                                                backgroundColor: COLORS.border,
                                            }}
                                        >
                                            <User
                                                size={48}
                                                color={COLORS.text}
                                            />
                                        </div>
                                    </div>

                                    <div className="text-center">
                                        <div className="font-semibold text-xl mb-3">
                                            {victim?.name}
                                        </div>
                                        <div className="text-base space-y-2">
                                            <div>나이: {victim?.meta?.age}</div>
                                            <div>
                                                성별: {victim?.meta?.gender}
                                            </div>
                                            <div>
                                                거주지: {victim?.meta?.address}
                                            </div>
                                            <div>
                                                학력: {victim?.meta?.education}
                                            </div>
                                            {victim?.meta?.job && (
                                                <div>
                                                    직업: {victim.meta.job}
                                                </div>
                                            )}
                                        </div>
                                    </div>

                                    <div>
                                        <h3 className="font-semibold text-lg mb-3">
                                            성격 특성 (OCEAN)
                                        </h3>

                                        <div className="flex flex-wrap gap-3 mb-3">
                                            {oceanEntries.length > 0 ? (
                                                oceanEntries.map((e, idx) => (
                                                    <span
                                                        key={idx}
                                                        className="px-3 py-2 rounded-full text-sm font-medium"
                                                        style={{
                                                            backgroundColor:
                                                                COLORS.border,
                                                        }}
                                                    >
                                                        {e.label}: {e.value}
                                                    </span>
                                                ))
                                            ) : (
                                                <span className="text-sm text-[#B5BAC1]">
                                                    OCEAN 정보 없음
                                                </span>
                                            )}
                                        </div>

                                        <div className="flex flex-wrap gap-3">
                                            {traitList.length > 0 ? (
                                                traitList.map((t, i) => (
                                                    <span
                                                        key={i}
                                                        className="px-4 py-2 rounded-full text-sm font-medium"
                                                        style={{
                                                            backgroundColor:
                                                                COLORS.border,
                                                        }}
                                                    >
                                                        {t}
                                                    </span>
                                                ))
                                            ) : (
                                                <span className="text-sm text-[#B5BAC1]">
                                                    추가 성격 특성 없음
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            </div>

                            {/* AI 에이전트 사용 여부 */}
                            <div
                                className="rounded-2xl p-8"
                                style={{
                                    backgroundColor: COLORS.panel,
                                    border: `1px solid ${COLORS.border}`,
                                }}
                            >
                                <h2 className="text-2xl font-semibold mb-5 flex items-center">
                                    <Bot className="mr-3" size={26} />
                                    AI 에이전트
                                </h2>
                                <div className="flex items-center gap-4">
                                    <Badge
                                        tone={
                                            sessionResult.agentUsed
                                                ? "success"
                                                : "neutral"
                                        }
                                        COLORS={COLORS}
                                    >
                                        {sessionResult.agentUsed
                                            ? "사용"
                                            : "미사용"}
                                    </Badge>
                                    {sessionResult.agentUsed && (
                                        <span className="text-base text-gray-500">
                                            GPT-4 기반
                                        </span>
                                    )}
                                </div>
                            </div>
                        </div>

                        {/* 오른쪽 패널 */}
                        <div className="flex-1 min-h-0 overflow-y-auto space-y-8 pr-2">
                            {/* 피싱 판정 결과 (제목 + 배지를 같은 라인에 표시) */}
                            <div
                                className="rounded-2xl p-8"
                                style={{
                                    backgroundColor: COLORS.panel,
                                    border: `1px solid ${COLORS.border}`,
                                }}
                            >
                                <div className="flex items-center justify-between mb-5">
                                    <h2 className="text-2xl font-semibold flex items-center">
                                        <AlertTriangle
                                            className="mr-3"
                                            size={26}
                                        />
                                        피싱 판정 결과
                                    </h2>

                                    {/* 제목 오른쪽에 배지 표시 (casePhishing 사용) */}
                                    <div className="ml-4">
                                        <Badge
                                            tone={
                                                casePhishing
                                                    ? "danger"
                                                    : "success"
                                            }
                                            COLORS={COLORS}
                                        >
                                            {casePhishing
                                                ? "피싱 성공"
                                                : "피싱 실패"}
                                        </Badge>
                                    </div>
                                </div>

                                <div className="space-y-5">
                                    <div>
                                        {/* caseEvidence가 있으면 핵심 근거 바로 아래 표시 */}
                                        {caseEvidence && (
                                            <div
                                                className="mt-4 p-4 rounded"
                                                style={{
                                                    backgroundColor: COLORS.bg,
                                                    border: `1px solid ${COLORS.border}`,
                                                }}
                                            >
                                                <h4 className="font-semibold mb-2">
                                                    사례 근거
                                                </h4>
                                                <p className="text-sm leading-relaxed whitespace-pre-wrap">
                                                    {caseEvidence}
                                                </p>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>

                            {/* 예방책 및 대응 방법 */}
                            {sessionResult.agentUsed && (
                                <div
                                    className="rounded-2xl p-8"
                                    style={{
                                        backgroundColor: COLORS.panel,
                                        border: `1px solid ${COLORS.border}`,
                                    }}
                                >
                                    <h2 className="text-2xl font-semibold mb-5 flex items-center">
                                        <Shield className="mr-3" size={26} />
                                        예방책 및 대응 방법
                                    </h2>
                                    <ul className="space-y-4">
                                        {(
                                            sessionResult.prevention || [
                                                "개인정보를 요구하는 전화에 즉시 응답하지 말고 공식 채널로 확인",
                                                "금융 거래는 반드시 은행 공식 앱이나 방문을 통해 진행",
                                                "의심스러운 링크나 파일은 절대 클릭하지 않기",
                                                "가족이나 지인에게 상황을 공유하여 객관적 판단 받기",
                                            ]
                                        ).map((item, idx) => (
                                            <li
                                                key={idx}
                                                className="flex items-start gap-3"
                                            >
                                                <div
                                                    className="w-8 h-8 rounded-full flex items-center justify-center mt-1"
                                                    style={{
                                                        backgroundColor:
                                                            COLORS.blurple,
                                                    }}
                                                >
                                                    <span className="text-white text-base font-bold">
                                                        {idx + 1}
                                                    </span>
                                                </div>
                                                <span className="text-base leading-relaxed">
                                                    {item}
                                                </span>
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            )}

                            {/* 출처 및 참고자료 */}
                            {/* 사례 출처 및 참고자료 (수정본: selectedScenario/scenarios/defaultCaseData 우선순위로 source 사용) */}
                            <div
                                className="rounded-2xl p-8"
                                style={{
                                    backgroundColor: COLORS.panel,
                                    border: `1px solid ${COLORS.border}`,
                                }}
                            >
                                <h2 className="text-2xl font-semibold mb-5 flex items-center">
                                    <ExternalLink className="mr-3" size={26} />
                                    사례 출처 및 참고자료
                                </h2>

                                <div className="space-y-5">
                                    {/* source 선택: selectedScenario -> scenarios[0] -> defaultCaseData.case */}
                                    {(() => {
                                        const src =
                                            selectedScenario?.source ??
                                            (Array.isArray(scenarios)
                                                ? scenarios[0]?.source
                                                : null) ??
                                            defaultCaseData?.case?.source ??
                                            null;

                                        if (!src) {
                                            return (
                                                <div
                                                    className="p-5 rounded-lg"
                                                    style={{
                                                        backgroundColor:
                                                            COLORS.bg,
                                                    }}
                                                >
                                                    <h3 className="font-semibold text-lg mb-3">
                                                        참고 사례
                                                    </h3>
                                                    <p className="text-base mb-4 leading-relaxed">
                                                        출처 정보가 없습니다.
                                                    </p>
                                                </div>
                                            );
                                        }

                                        const { title, page, url } = src;

                                        return (
                                            <>
                                                <div
                                                    className="p-5 rounded-lg"
                                                    style={{
                                                        backgroundColor:
                                                            COLORS.bg,
                                                    }}
                                                >
                                                    <h3 className="font-semibold text-lg mb-3">
                                                        {title ?? "참고 사례"}
                                                    </h3>
                                                    {page && (
                                                        <div className="text-base mb-2">
                                                            페이지: {page}
                                                        </div>
                                                    )}
                                                    <p className="text-base mb-4 leading-relaxed">
                                                        {sessionResult?.caseSource ??
                                                            "본 시뮬레이션은 실제 보이스피싱 사례를 바탕으로 제작되었습니다."}
                                                    </p>
                                                    <div className="space-y-3">
                                                        <div className="flex items-center gap-3">
                                                            <span className="text-base font-medium">
                                                                출처:
                                                            </span>
                                                            {url ? (
                                                                <a
                                                                    href={url}
                                                                    target="_blank"
                                                                    rel="noopener noreferrer"
                                                                    className="text-base underline"
                                                                    aria-label="참고자료 링크 열기"
                                                                >
                                                                    {url}
                                                                </a>
                                                            ) : (
                                                                <span className="text-base">
                                                                    {sessionResult.source ??
                                                                        "-"}
                                                                </span>
                                                            )}
                                                        </div>
                                                        {/* {page && (
                                <div className="flex items-center gap-3">
                                <span className="text-base font-medium">권/쪽:</span>
                                <span className="text-base">{page}</span>
                                </div>
                            )} */}
                                                    </div>
                                                </div>

                                                {/* <div className="flex gap-3">
                            <button
                            className="flex-1 px-5 py-3 rounded-lg text-base font-medium"
                            style={{ backgroundColor: COLORS.border }}
                            onClick={() => {
                                // 선택사항: 상세보기 동작(필요 시 핸들러 추가)
                                console.log('상세 사례 보기 클릭');
                            }}
                            >
                            상세 사례 보기
                            </button>

                            <button
                            className="flex-1 px-5 py-3 rounded-lg text-base font-medium"
                            style={{ backgroundColor: COLORS.blurple, color: COLORS.white }}
                            onClick={() => {
                                console.log('관련 교육자료 클릭');
                            }}
                            >
                            관련 교육자료
                            </button>
                        </div> */}
                                            </>
                                        );
                                    })()}
                                </div>
                            </div>

                            {/* AI 에이전트 로그 */}
                            {sessionResult.agentUsed &&
                                sessionResult.agentLogs && (
                                    <div
                                        className="rounded-2xl p-8"
                                        style={{
                                            backgroundColor: COLORS.panel,
                                            border: `1px solid ${COLORS.border}`,
                                        }}
                                    >
                                        <h2 className="text-2xl font-semibold mb-5 flex items-center">
                                            <Terminal
                                                className="mr-3"
                                                size={26}
                                            />
                                            AI 에이전트 로그
                                        </h2>
                                        <div className="space-y-4">
                                            {(
                                                sessionResult.agentLogs || []
                                            ).map((log, i) => (
                                                <div
                                                    key={i}
                                                    className="text-sm"
                                                >
                                                    <div className="flex items-center gap-3 mb-2">
                                                        <span
                                                            className="text-xs px-3 py-2 rounded font-mono"
                                                            style={{
                                                                backgroundColor:
                                                                    COLORS.border,
                                                            }}
                                                        >
                                                            {log.timestamp}
                                                        </span>
                                                        <span
                                                            className="text-sm font-medium"
                                                            style={{
                                                                color: COLORS.blurple,
                                                            }}
                                                        >
                                                            {log.type}
                                                        </span>
                                                    </div>
                                                    <div
                                                        className="pl-5 py-3 rounded font-mono text-sm leading-relaxed"
                                                        style={{
                                                            backgroundColor:
                                                                COLORS.bg,
                                                            borderLeft: `3px solid ${COLORS.blurple}`,
                                                        }}
                                                    >
                                                        {log.message}
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                        <div
                                            className="mt-5 pt-4 border-t"
                                            style={{
                                                borderColor: COLORS.border,
                                            }}
                                        >
                                            <div className="flex items-center justify-between text-sm">
                                                <span>
                                                    총{" "}
                                                    {
                                                        sessionResult.agentLogs
                                                            .length
                                                    }
                                                    개 로그
                                                </span>
                                            </div>
                                        </div>
                                    </div>
                                )}
                        </div>
                    </div>
                ) : (
                    <div
                        className="rounded-2xl p-8"
                        style={{
                            backgroundColor: COLORS.panel,
                            border: `1px solid ${COLORS.border}`,
                        }}
                    >
                        <p className="text-base">
                            세션 결과가 없습니다. 시뮬레이션을 먼저
                            실행해주세요.
                        </p>
                    </div>
                )}
            </div>
        </div>
    );
};

export default ReportPage;
