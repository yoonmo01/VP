// import {
//   User,
//   Bot,
//   Terminal,
//   ExternalLink,
//   Shield,
//   AlertTriangle,
// } from "lucide-react";
// import { useEffect, useState, useMemo } from "react";
// import Badge from "./Badge";

// async function fetchWithTimeout(url, { timeout = 15000, ...opts } = {}) {
//   const ctrl = new AbortController();
//   const id = setTimeout(() => ctrl.abort(), timeout);
//   try {
//     const res = await fetch(url, { ...opts, signal: ctrl.signal });
//     if (!res.ok) {
//       const txt = await res.text().catch(() => "");
//       throw new Error(`HTTP ${res.status} ${res.statusText} ${txt}`);
//     }
//     const txt = await res.text();
//     return txt ? JSON.parse(txt) : null;
//   } finally {
//     clearTimeout(id);
//   }
// }

// const ReportPage = ({
//   COLORS,
//   setCurrentPage,
//   sessionResult,
//   scenarios,
//   defaultCaseData,
//   selectedScenario,
//   selectedCharacter,
//   currentCaseId, // ★ App에서 전달
//   victimImageUrl, // ✅ 피해자 이미지 URL 추가
// }) => {
//   // ---------- admin-case 실시간 조회 ----------
//   const [adminCase, setAdminCase] = useState(null);
//   const [adminCaseLoading, setAdminCaseLoading] = useState(false);
//   const [adminCaseError, setAdminCaseError] = useState(null);

//   useEffect(() => {
//     let mounted = true;
//     (async () => {
//       if (!currentCaseId) return;
//       setAdminCaseLoading(true);
//       setAdminCaseError(null);
//       try {
//         const data = await fetchWithTimeout(
//           `/api/admin-cases/${encodeURIComponent(currentCaseId)}`,
//           { timeout: 15000 },
//         );
//         if (!mounted) return;
//         setAdminCase(data || null);
//       } catch (e) {
//         if (!mounted) return;
//         setAdminCaseError(e.message || String(e));
//       } finally {
//         if (mounted) setAdminCaseLoading(false);
//       }
//     })();
//     return () => {
//       mounted = false;
//     };
//   }, [currentCaseId]);

//   // ---------- 표시값(우선순위: adminCase -> defaultCaseData -> sessionResult) ----------
//   const casePhishing = useMemo(() => {
//     const fromAdmin =
//       typeof adminCase?.phishing === "boolean" ? adminCase.phishing : undefined;
//     const fromDefault =
//       typeof defaultCaseData?.case?.phishing === "boolean"
//         ? defaultCaseData.case.phishing
//         : undefined;
//     const fromSessionPhishing =
//       typeof sessionResult?.phishing === "boolean"
//         ? sessionResult.phishing
//         : undefined;
//     const fromSessionIs =
//       typeof sessionResult?.isPhishing === "boolean"
//         ? sessionResult.isPhishing
//         : undefined;

//     return (
//       fromAdmin ?? fromDefault ?? fromSessionPhishing ?? fromSessionIs ?? false
//     );
//   }, [adminCase, defaultCaseData, sessionResult]);

//   const caseEvidence = useMemo(() => {
//     return (
//       adminCase?.evidence ??
//       defaultCaseData?.case?.evidence ??
//       sessionResult?.case?.evidence ??
//       sessionResult?.evidence ??
//       ""
//     );
//   }, [adminCase, defaultCaseData, sessionResult]);

//   // ---------- 피해자/부가정보 ----------
//   const victimFromSession = sessionResult
//     ? {
//         name: sessionResult.victimName ?? "알 수 없음",
//         meta: {
//           age: sessionResult.victimAge ?? "-",
//           gender: sessionResult.victimGender ?? "-",
//           address: sessionResult.victimAddress ?? "-",
//           education: sessionResult.victimEducation ?? "-",
//           job: sessionResult.victimJob ?? "-",
//         },
//         traits: { ocean: undefined, list: sessionResult.victimTraits ?? [] },
//         // ✅ 지식(비교 메모) – 다양한 키 폴백 처리
//         knowledge: {
//           comparative_notes: Array.isArray(sessionResult?.victimKnowledge)
//             ? sessionResult.victimKnowledge
//             : Array.isArray(sessionResult?.victimComparativeNotes)
//               ? sessionResult.victimComparativeNotes
//               : Array.isArray(sessionResult?.knowledge?.comparative_notes)
//                 ? sessionResult.knowledge.comparative_notes
//                 : [],
//         },
//       }
//     : null;

//   const victim = selectedCharacter ??
//     victimFromSession ?? {
//       name: "알 수 없음",
//       meta: { age: "-", gender: "-", address: "-", education: "-", job: "-" },
//       traits: { ocean: undefined, list: [] },
//       knowledge: { comparative_notes: [] }, // ✅ 기본값
//     };

//   const oceanLabelMap = {
//     openness: "개방성",
//     neuroticism: "신경성",
//     extraversion: "외향성",
//     agreeableness: "친화성",
//     conscientiousness: "성실성",
//   };

//   const oceanEntries =
//     victim?.traits?.ocean && typeof victim.traits.ocean === "object"
//       ? Object.entries(victim.traits.ocean).map(([k, v]) => ({
//           label: oceanLabelMap[k] ?? k,
//           value: v,
//         }))
//       : [];

//   const traitList = Array.isArray(victim?.traits?.list)
//     ? victim.traits.list
//     : [];

//   const phishingTypeText =
//     selectedScenario?.type ??
//     (Array.isArray(scenarios)
//       ? (scenarios[0]?.type ?? "피싱 유형")
//       : "피싱 유형");

//   // ====== agent logs 안전 추출 및 use_agent 필터 ======
//   const rawAgentLogs = useMemo(() => {
//     return (
//       sessionResult?.agentLogs ??
//       defaultCaseData?.agent_logs ??
//       defaultCaseData?.agentLogs ??
//       defaultCaseData?.agent?.logs ??
//       adminCase?.agent_logs ??
//       adminCase?.agentLogs ??
//       []
//     );
//   }, [sessionResult, defaultCaseData, adminCase]);

//   const filteredAgentLogs = useMemo(() => {
//     if (!Array.isArray(rawAgentLogs)) return [];

//     return rawAgentLogs.filter((l) => {
//       // 문자열 로그는 agent 전용으로 인정 (서버가 이미 분리했을 가능성)
//       if (typeof l === "string") return true;

//       // 객체형 로그인 경우 use_agent 계열 필드 검사
//       const v =
//         l?.use_agent ??
//         l?.useAgent ??
//         l?.use_agent_flag ??
//         l?.use_agent_value ??
//         undefined;
//       if (v === true || v === "true" || v === 1 || v === "1") return true;

//       // 허용하지 않음
//       return false;
//     });
//   }, [rawAgentLogs]);

//   return (
//     <div className="min-h-screen bg-[#1E1F22] text-[#DCDDDE]">
//       <div className="mx-auto min-h-screen p-6 md:p-10 xl:p-12 flex flex-col">
//         <div className="flex items-center justify-between mb-10">
//           <h1 className="text-4xl font-bold">시뮬레이션 리포트</h1>
//           <button
//             onClick={() => setCurrentPage("simulator")}
//             className="px-6 py-3 rounded-lg text-lg font-medium"
//             style={{ backgroundColor: COLORS.blurple, color: COLORS.white }}
//           >
//             돌아가기
//           </button>
//         </div>

//         {sessionResult ? (
//           <div className="flex gap-10 flex-1 overflow-hidden">
//             {/* 왼쪽 패널 */}
//             <div
//               className="w-full lg:w-1/3 flex-shrink-0 space-y-8 pr-6"
//               style={{ borderRight: `1px solid ${COLORS.border}` }}
//             >
//               {/* 피싱 유형 */}
//               <div
//                 className="rounded-2xl p-8"
//                 style={{
//                   backgroundColor: COLORS.panel,
//                   border: `1px solid ${COLORS.border}`,
//                 }}
//               >
//                 <h2 className="text-2xl font-semibold mb-5 flex items-center">
//                   <Shield className="mr-3" size={26} />
//                   피싱 유형
//                 </h2>
//                 <div
//                   className="text-xl font-medium"
//                   style={{ color: COLORS.blurple }}
//                 >
//                   {phishingTypeText}
//                 </div>
//               </div>

//               {/* 피해자 정보 */}
//               <div
//                 className="rounded-2xl p-8"
//                 style={{
//                   backgroundColor: COLORS.panel,
//                   border: `1px solid ${COLORS.border}`,
//                 }}
//               >
//                 <h2 className="text-2xl font-semibold mb-5 flex items-center">
//                   <User className="mr-3" size={26} />
//                   피해자 정보
//                 </h2>

//                 <div className="space-y-5">
//                   <div className="flex justify-center">
//                     {victimImageUrl ? (
//                       <img
//                         src={victimImageUrl}
//                         alt={victim.name}
//                         className="w-24 h-24 rounded-full object-cover"
//                       />
//                     ) : (
//                       <div
//                         className="w-24 h-24 rounded-full flex items-center justify-center"
//                         style={{ backgroundColor: COLORS.border }}
//                       >
//                         <User size={48} color={COLORS.text} />
//                       </div>
//                     )}
//                   </div>

//                   <div className="text-center">
//                     <div className="font-semibold text-xl mb-3">
//                       {victim?.name}
//                     </div>
//                     <div className="text-base space-y-2">
//                       <div>나이: {victim?.meta?.age}</div>
//                       <div>성별: {victim?.meta?.gender}</div>
//                       <div>거주지: {victim?.meta?.address}</div>
//                       <div>학력: {victim?.meta?.education}</div>
//                       {victim?.meta?.job && <div>직업: {victim.meta.job}</div>}
//                     </div>
//                   </div>

//                   {/* 성격 정보 (OCEAN) */}
//                   <div>
//                     <h3 className="font-semibold text-lg mb-3">
//                       성격 특성 (OCEAN)
//                     </h3>

//                     <div className="flex flex-wrap gap-3 mb-3">
//                       {oceanEntries.length > 0 ? (
//                         oceanEntries.map((e, idx) => (
//                           <span
//                             key={idx}
//                             className="px-3 py-2 rounded-full text-sm font-medium"
//                             style={{ backgroundColor: COLORS.border }}
//                           >
//                             {e.label}: {e.value}
//                           </span>
//                         ))
//                       ) : (
//                         <span className="text-sm text-[#B5BAC1]">
//                           OCEAN 정보 없음
//                         </span>
//                       )}
//                     </div>

//                     {/* ▶ 추가 성격 특성: 비어있으면 아예 렌더하지 않음 */}
//                     {traitList?.length > 0 && (
//                       <div className="flex flex-wrap gap-3">
//                         {traitList.map((t, i) => (
//                           <span
//                             key={i}
//                             className="px-4 py-2 rounded-full text-sm font-medium"
//                             style={{ backgroundColor: COLORS.border }}
//                           >
//                             {t}
//                           </span>
//                         ))}
//                       </div>
//                     )}
//                   </div>

//                   {/* ✅ 지식 정보 */}
//                   <div className="mt-6">
//                     <h3 className="font-semibold text-lg mb-3">지식</h3>
//                     <div className="space-y-1">
//                       {Array.isArray(victim?.knowledge?.comparative_notes) &&
//                       victim.knowledge.comparative_notes.length > 0 ? (
//                         victim.knowledge.comparative_notes.map((note, idx) => (
//                           <div
//                             key={idx}
//                             className="text-sm font-medium text-[#DCDDDE] leading-relaxed"
//                           >
//                             • {note}
//                           </div>
//                         ))
//                       ) : (
//                         <div className="text-sm text-[#B5BAC1]">비고 없음</div>
//                       )}
//                     </div>
//                   </div>
//                 </div>
//               </div>

//               {/* AI 에이전트 사용 여부 */}
//               <div
//                 className="rounded-2xl p-8"
//                 style={{
//                   backgroundColor: COLORS.panel,
//                   border: `1px solid ${COLORS.border}`,
//                 }}
//               >
//                 <h2 className="text-2xl font-semibold mb-5 flex items-center">
//                   <Bot className="mr-3" size={26} />
//                   AI 에이전트
//                 </h2>
//                 <div className="flex items-center gap-4">
//                   <Badge
//                     tone={sessionResult.agentUsed ? "success" : "neutral"}
//                     COLORS={COLORS}
//                   >
//                     {sessionResult.agentUsed ? "사용" : "미사용"}
//                   </Badge>
//                 </div>
//               </div>
//             </div>

//             {/* 오른쪽 패널 */}
//             <div className="flex-1 min-h-0 overflow-y-auto space-y-8 pr-2">
//               {/* 피싱 판정 결과 */}
//               <div
//                 className="rounded-2xl p-8"
//                 style={{
//                   backgroundColor: COLORS.panel,
//                   border: `1px solid ${COLORS.border}`,
//                 }}
//               >
//                 <div className="flex items-center justify-between mb-5">
//                   <h2 className="text-2xl font-semibold flex items-center">
//                     <AlertTriangle className="mr-3" size={26} />
//                     피싱 판정 결과
//                   </h2>

//                   {/* 성공=파랑(primary), 실패=빨강(danger) */}
//                   <div className="ml-4">
//                     <Badge
//                       tone={casePhishing ? "primary" : "danger"}
//                       COLORS={COLORS}
//                     >
//                       {casePhishing ? "피싱 성공" : "피싱 실패"}
//                     </Badge>
//                   </div>
//                 </div>

//                 {/* 상태/오류 보조 표시 */}
//                 {adminCaseLoading && (
//                   <div className="mb-3 text-sm" style={{ color: COLORS.sub }}>
//                     근거 불러오는 중…
//                   </div>
//                 )}
//                 {adminCaseError && (
//                   <div className="mb-3 text-sm" style={{ color: COLORS.warn }}>
//                     근거 조회 실패: {adminCaseError}
//                   </div>
//                 )}

//                 {/* 근거 박스: 항상 표시 (없으면 안내 문구) */}
//                 <div
//                   className="mt-2 p-4 rounded"
//                   style={{
//                     backgroundColor: COLORS.bg,
//                     border: `1px solid ${COLORS.border}`,
//                   }}
//                 >
//                   <h4 className="font-semibold mb-2">
//                     {casePhishing ? "피싱 성공 근거" : "피싱 실패 근거"}
//                   </h4>
//                   <p className="text-sm leading-relaxed whitespace-pre-wrap">
//                     {caseEvidence || "근거 정보가 없습니다."}
//                   </p>
//                 </div>
//               </div>

//               {/* 출처 및 참고자료 */}
//               <div
//                 className="rounded-2xl p-8"
//                 style={{
//                   backgroundColor: COLORS.panel,
//                   border: `1px solid ${COLORS.border}`,
//                 }}
//               >
//                 <h2 className="text-2xl font-semibold mb-5 flex items-center">
//                   <ExternalLink className="mr-3" size={26} />
//                   사례 출처 및 참고자료
//                 </h2>

//                 <div className="space-y-5">
//                   {(() => {
//                     const src =
//                       selectedScenario?.source ??
//                       (Array.isArray(scenarios)
//                         ? scenarios[0]?.source
//                         : null) ??
//                       defaultCaseData?.case?.source ??
//                       null;

//                     if (!src) {
//                       return (
//                         <div
//                           className="p-5 rounded-lg"
//                           style={{ backgroundColor: COLORS.bg }}
//                         >
//                           <h3 className="font-semibold text-lg mb-3">
//                             참고 사례
//                           </h3>
//                           <p className="text-base mb-4 leading-relaxed">
//                             출처 정보가 없습니다.
//                           </p>
//                         </div>
//                       );
//                     }

//                     const { title, page, url } = src;

//                     return (
//                       <div
//                         className="p-5 rounded-lg"
//                         style={{ backgroundColor: COLORS.bg }}
//                       >
//                         <h3 className="font-semibold text-lg mb-3">
//                           {title ?? "참고 사례"}
//                         </h3>
//                         {page && (
//                           <div className="text-base mb-2">페이지: {page}</div>
//                         )}
//                         <p className="text-base mb-4 leading-relaxed">
//                           {sessionResult?.caseSource ??
//                             "본 시뮬레이션은 실제 보이스피싱 사례를 바탕으로 제작되었습니다."}
//                         </p>
//                         <div className="space-y-3">
//                           <div className="flex items-center gap-3">
//                             <span className="text-base font-medium">출처:</span>
//                             {url ? (
//                               <a
//                                 href={url}
//                                 target="_blank"
//                                 rel="noopener noreferrer"
//                                 className="text-base underline"
//                                 aria-label="참고자료 링크 열기"
//                               >
//                                 {url}
//                               </a>
//                             ) : (
//                               <span className="text-base">
//                                 {sessionResult?.source ?? "-"}
//                               </span>
//                             )}
//                           </div>
//                         </div>
//                       </div>
//                     );
//                   })()}
//                 </div>
//               </div>

//               {/* AI 에이전트 로그 (use_agent === true인 항목만 렌더) */}
//               {filteredAgentLogs.length > 0 && (
//                 <div
//                   className="rounded-2xl p-8"
//                   style={{
//                     backgroundColor: COLORS.panel,
//                     border: `1px solid ${COLORS.border}`,
//                   }}
//                 >
//                   <h2 className="text-2xl font-semibold mb-5 flex items-center">
//                     <Terminal className="mr-3" size={26} />
//                     AI 에이전트 로그
//                   </h2>

//                   <div className="space-y-4">
//                     {filteredAgentLogs.map((log, i) => {
//                       // 로그 포맷이 다양할 수 있으므로 안전하게 파싱
//                       const ts =
//                         log?.timestamp ?? log?.time ?? log?.created_kst ?? "";
//                       const type = log?.type ?? log?.level ?? "agent";
//                       const message =
//                         typeof log === "string"
//                           ? log
//                           : (log?.message ??
//                             log?.text ??
//                             log?.content ??
//                             JSON.stringify(log));

//                       return (
//                         <div key={i} className="text-sm">
//                           <div className="flex items-center gap-3 mb-2">
//                             <span
//                               className="text-xs px-3 py-2 rounded font-mono"
//                               style={{ backgroundColor: COLORS.border }}
//                             >
//                               {ts}
//                             </span>
//                             <span
//                               className="text-sm font-medium"
//                               style={{ color: COLORS.blurple }}
//                             >
//                               {type}
//                             </span>
//                           </div>

//                           <div
//                             className="pl-5 py-3 rounded font-mono text-sm leading-relaxed"
//                             style={{
//                               backgroundColor: COLORS.bg,
//                               borderLeft: `3px solid ${COLORS.blurple}`,
//                             }}
//                           >
//                             {message}
//                           </div>
//                         </div>
//                       );
//                     })}
//                   </div>

//                   <div
//                     className="mt-5 pt-4 border-t"
//                     style={{ borderColor: COLORS.border }}
//                   >
//                     <div className="flex items-center justify-between text-sm">
//                       <span>총 {filteredAgentLogs.length}개 로그</span>
//                     </div>
//                   </div>
//                 </div>
//               )}
//             </div>
//           </div>
//         ) : (
//           <div
//             className="rounded-2xl p-8"
//             style={{
//               backgroundColor: COLORS.panel,
//               border: `1px solid ${COLORS.border}`,
//             }}
//           >
//             <p className="text-base">
//               세션 결과가 없습니다. 시뮬레이션을 먼저 실행해주세요.
//             </p>
//           </div>
//         )}
//       </div>
//     </div>
//   );
// };

// export default ReportPage;

import {
  User,
  Bot,
  Terminal,
  ExternalLink,
  Shield,
  AlertTriangle,
} from "lucide-react";
import { useEffect, useState, useMemo } from "react";
import Badge from "./Badge";

async function fetchWithTimeout(url, { timeout = 15000, ...opts } = {}) {
  const ctrl = new AbortController();
  const id = setTimeout(() => ctrl.abort(), timeout);
  try {
    const res = await fetch(url, { ...opts, signal: ctrl.signal });
    if (!res.ok) {
      const txt = await res.text().catch(() => "");
      throw new Error(`HTTP ${res.status} ${res.statusText} ${txt}`);
    }
    const txt = await res.text();
    return txt ? JSON.parse(txt) : null;
  } finally {
    clearTimeout(id);
  }
}

const ReportPage = ({
  COLORS,
  setCurrentPage,
  sessionResult,
  scenarios,
  defaultCaseData,
  selectedScenario,
  selectedCharacter,
  currentCaseId, // ★ App에서 전달
  victimImageUrl, // ✅ 피해자 이미지 URL 추가
}) => {
  // ---------- admin-case 실시간 조회 ----------
  const [adminCase, setAdminCase] = useState(null);
  const [adminCaseLoading, setAdminCaseLoading] = useState(false);
  const [adminCaseError, setAdminCaseError] = useState(null);

  useEffect(() => {
    let mounted = true;
    (async () => {
      if (!currentCaseId) return;
      setAdminCaseLoading(true);
      setAdminCaseError(null);
      try {
        const data = await fetchWithTimeout(
          `/api/admin-cases/${encodeURIComponent(currentCaseId)}`,
          { timeout: 15000 },
        );
        if (!mounted) return;
        setAdminCase(data || null);
      } catch (e) {
        if (!mounted) return;
        setAdminCaseError(e.message || String(e));
      } finally {
        if (mounted) setAdminCaseLoading(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, [currentCaseId]);

  // ---------- 표시값(우선순위: adminCase -> defaultCaseData -> sessionResult) ----------
  const casePhishing = useMemo(() => {
    const fromAdmin =
      typeof adminCase?.phishing === "boolean" ? adminCase.phishing : undefined;
    const fromDefault =
      typeof defaultCaseData?.case?.phishing === "boolean"
        ? defaultCaseData.case.phishing
        : undefined;
    const fromSessionPhishing =
      typeof sessionResult?.phishing === "boolean"
        ? sessionResult.phishing
        : undefined;
    const fromSessionIs =
      typeof sessionResult?.isPhishing === "boolean"
        ? sessionResult.isPhishing
        : undefined;

    return (
      fromAdmin ?? fromDefault ?? fromSessionPhishing ?? fromSessionIs ?? false
    );
  }, [adminCase, defaultCaseData, sessionResult]);

  const caseEvidence = useMemo(() => {
    return (
      adminCase?.evidence ??
      defaultCaseData?.case?.evidence ??
      sessionResult?.case?.evidence ??
      sessionResult?.evidence ??
      ""
    );
  }, [adminCase, defaultCaseData, sessionResult]);

  // ---------- 피해자/부가정보 ----------
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
        traits: { ocean: undefined, list: sessionResult.victimTraits ?? [] },
        // ✅ 지식(비교 메모) – 다양한 키 폴백 처리
        knowledge: {
          comparative_notes: Array.isArray(sessionResult?.victimKnowledge)
            ? sessionResult.victimKnowledge
            : Array.isArray(sessionResult?.victimComparativeNotes)
              ? sessionResult.victimComparativeNotes
              : Array.isArray(sessionResult?.knowledge?.comparative_notes)
                ? sessionResult.knowledge.comparative_notes
                : [],
        },
      }
    : null;

  const victim = selectedCharacter ??
    victimFromSession ?? {
      name: "알 수 없음",
      meta: { age: "-", gender: "-", address: "-", education: "-", job: "-" },
      traits: { ocean: undefined, list: [] },
      knowledge: { comparative_notes: [] }, // ✅ 기본값
    };

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

  const phishingTypeText =
    selectedScenario?.type ??
    (Array.isArray(scenarios)
      ? (scenarios[0]?.type ?? "피싱 유형")
      : "피싱 유형");

  // ====== agent logs 안전 추출 및 use_agent 필터 ======
  const rawAgentLogs = useMemo(() => {
    return (
      sessionResult?.agentLogs ??
      defaultCaseData?.agent_logs ??
      defaultCaseData?.agentLogs ??
      defaultCaseData?.agent?.logs ??
      adminCase?.agent_logs ??
      adminCase?.agentLogs ??
      []
    );
  }, [sessionResult, defaultCaseData, adminCase]);

  const filteredAgentLogs = useMemo(() => {
    if (!Array.isArray(rawAgentLogs)) return [];
    return rawAgentLogs.filter((l) => {
      if (typeof l === "string") return true;
      const v =
        l?.use_agent ??
        l?.useAgent ??
        l?.use_agent_flag ??
        l?.use_agent_value ??
        undefined;
      if (v === true || v === "true" || v === 1 || v === "1") return true;
      return false;
    });
  }, [rawAgentLogs]);

  // ====== 개인화 예방법 (Personalized) ======
  const [personalized, setPersonalized] = useState(null);
  const [personalizedLoading, setPersonalizedLoading] = useState(false);
  const [personalizedError, setPersonalizedError] = useState(null);

  function pickLatestPersonalized(items = []) {
    if (!Array.isArray(items) || items.length === 0) return null;
    return items.slice().sort((a, b) => {
      const ra = typeof a.run === "number" ? a.run : -1;
      const rb = typeof b.run === "number" ? b.run : -1;
      if (rb !== ra) return rb - ra;
      const ta = Date.parse(a.created_at || 0);
      const tb = Date.parse(b.created_at || 0);
      return tb - ta;
    })[0];
  }

  useEffect(() => {
    let mounted = true;
    (async () => {
      if (!currentCaseId) {
        setPersonalized(null);
        return;
      }
      setPersonalizedLoading(true);
      setPersonalizedError(null);
      try {
        const data = await fetchWithTimeout(
          `/api/personalized/by-case/${encodeURIComponent(currentCaseId)}`,
          { timeout: 200000 },
        );
        if (!mounted) return;
        const picked = pickLatestPersonalized(data || []);
        setPersonalized(picked);
      } catch (e) {
        if (!mounted) return;
        setPersonalizedError(e.message || String(e));
        setPersonalized(null);
      } finally {
        if (mounted) setPersonalizedLoading(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, [currentCaseId]);

  function RiskBadge({ level }) {
    const lv = String(level || "").toLowerCase(); // low / medium / high
    let toneBg = COLORS.border;
    if (lv.includes("high")) toneBg = COLORS.danger;
    else if (lv.includes("medium")) toneBg = COLORS.warn;
    else if (lv.includes("low")) toneBg = COLORS.success;

    return (
      <span
        className="text-xs px-3 py-1 rounded font-semibold"
        style={{ backgroundColor: toneBg, color: COLORS.black }}
      >
        위험도: {level ?? "-"}
      </span>
    );
  }

  return (
    <div className="min-h-screen bg-[#1E1F22] text-[#DCDDDE]">
      <div className="mx-auto min-h-screen p-6 md:p-10 xl:p-12 flex flex-col">
        <div className="flex items-center justify-between mb-10">
          <h1 className="text-4xl font-bold">시뮬레이션 리포트</h1>
          <button
            onClick={() => setCurrentPage("simulator")}
            className="px-6 py-3 rounded-lg text-lg font-medium"
            style={{ backgroundColor: COLORS.blurple, color: COLORS.white }}
          >
            돌아가기
          </button>
        </div>

        {sessionResult ? (
          <div className="flex gap-10 flex-1 overflow-hidden">
            {/* 왼쪽 패널 */}
            <div
              className="w-full lg:w-1/3 flex-shrink-0 space-y-8 pr-6"
              style={{ borderRight: `1px solid ${COLORS.border}` }}
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
                    {victimImageUrl ? (
                      <img
                        src={victimImageUrl}
                        alt={victim.name}
                        className="w-24 h-24 rounded-full object-cover"
                      />
                    ) : (
                      <div
                        className="w-24 h-24 rounded-full flex items-center justify-center"
                        style={{ backgroundColor: COLORS.border }}
                      >
                        <User size={48} color={COLORS.text} />
                      </div>
                    )}
                  </div>

                  <div className="text-center">
                    <div className="font-semibold text-xl mb-3">
                      {victim?.name}
                    </div>
                    <div className="text-base space-y-2">
                      <div>나이: {victim?.meta?.age}</div>
                      <div>성별: {victim?.meta?.gender}</div>
                      <div>거주지: {victim?.meta?.address}</div>
                      <div>학력: {victim?.meta?.education}</div>
                      {victim?.meta?.job && <div>직업: {victim.meta.job}</div>}
                    </div>
                  </div>

                  {/* 성격 정보 (OCEAN) */}
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
                            style={{ backgroundColor: COLORS.border }}
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

                    {/* ▶ 추가 성격 특성: 비어있으면 아예 렌더하지 않음 */}
                    {traitList?.length > 0 && (
                      <div className="flex flex-wrap gap-3">
                        {traitList.map((t, i) => (
                          <span
                            key={i}
                            className="px-4 py-2 rounded-full text-sm font-medium"
                            style={{ backgroundColor: COLORS.border }}
                          >
                            {t}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* ✅ 지식 정보 */}
                  <div className="mt-6">
                    <h3 className="font-semibold text-lg mb-3">지식</h3>
                    <div className="space-y-1">
                      {Array.isArray(victim?.knowledge?.comparative_notes) &&
                      victim.knowledge.comparative_notes.length > 0 ? (
                        victim.knowledge.comparative_notes.map((note, idx) => (
                          <div
                            key={idx}
                            className="text-sm font-medium text-[#DCDDDE] leading-relaxed"
                          >
                            • {note}
                          </div>
                        ))
                      ) : (
                        <div className="text-sm text-[#B5BAC1]">비고 없음</div>
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
                    tone={sessionResult.agentUsed ? "success" : "neutral"}
                    COLORS={COLORS}
                  >
                    {sessionResult.agentUsed ? "사용" : "미사용"}
                  </Badge>
                </div>
              </div>
            </div>

            {/* 오른쪽 패널 */}
            <div className="flex-1 min-h-0 overflow-y-auto space-y-8 pr-2">
              {/* 피싱 판정 결과 */}
              <div
                className="rounded-2xl p-8"
                style={{
                  backgroundColor: COLORS.panel,
                  border: `1px solid ${COLORS.border}`,
                }}
              >
                <div className="flex items-center justify-between mb-5">
                  <h2 className="text-2xl font-semibold flex items-center">
                    <AlertTriangle className="mr-3" size={26} />
                    피싱 판정 결과
                  </h2>

                  {/* 성공=파랑(primary), 실패=빨강(danger) */}
                  <div className="ml-4">
                    <Badge
                      tone={casePhishing ? "primary" : "danger"}
                      COLORS={COLORS}
                    >
                      {casePhishing ? "피싱 성공" : "피싱 실패"}
                    </Badge>
                  </div>
                </div>

                {/* 상태/오류 보조 표시 */}
                {adminCaseLoading && (
                  <div className="mb-3 text-sm" style={{ color: COLORS.sub }}>
                    근거 불러오는 중…
                  </div>
                )}
                {adminCaseError && (
                  <div className="mb-3 text-sm" style={{ color: COLORS.warn }}>
                    근거 조회 실패: {adminCaseError}
                  </div>
                )}

                {/* 근거 박스: 항상 표시 (없으면 안내 문구) */}
                <div
                  className="mt-2 p-4 rounded"
                  style={{
                    backgroundColor: COLORS.bg,
                    border: `1px solid ${COLORS.border}`,
                  }}
                >
                  <h4 className="font-semibold mb-2">
                    {casePhishing ? "피싱 성공 근거" : "피싱 실패 근거"}
                  </h4>
                  <p className="text-sm leading-relaxed whitespace-pre-wrap">
                    {caseEvidence || "근거 정보가 없습니다."}
                  </p>
                </div>
              </div>

              {/* 개인화 예방법 */}
              <div
                className="rounded-2xl p-8"
                style={{
                  backgroundColor: COLORS.panel,
                  border: `1px solid ${COLORS.border}`,
                }}
              >
                <div className="flex items-center justify-between mb-5">
                  <h2 className="text-2xl font-semibold flex items-center">
                    <Shield className="mr-3" size={26} />
                    개인화 예방법
                  </h2>
                  {personalized?.content?.analysis?.risk_level && (
                    <RiskBadge
                      level={personalized.content.analysis.risk_level}
                    />
                  )}
                </div>

                {personalizedLoading && (
                  <div className="text-sm" style={{ color: COLORS.sub }}>
                    개인화 예방법 불러오는 중…
                  </div>
                )}
                {personalizedError && (
                  <div className="text-sm" style={{ color: COLORS.warn }}>
                    조회 실패: {personalizedError}
                  </div>
                )}

                {!personalizedLoading && !personalizedError && (
                  <>
                    {/* 요약 */}
                    <div
                      className="p-4 rounded mb-6"
                      style={{
                        backgroundColor: COLORS.bg,
                        border: `1px solid ${COLORS.border}`,
                      }}
                    >
                      <h3 className="font-semibold mb-2">요약</h3>
                      <p className="text-sm leading-relaxed whitespace-pre-wrap">
                        {personalized?.content?.summary ??
                          "요약 정보가 없습니다."}
                      </p>
                    </div>

                    {/* 실천 단계 */}
                    <div className="mb-6">
                      <h3 className="font-semibold mb-3">실천 단계 (steps)</h3>
                      {Array.isArray(personalized?.content?.steps) &&
                      personalized.content.steps.length > 0 ? (
                        <ul className="list-disc pl-6 space-y-1 text-sm">
                          {personalized.content.steps.map((s, i) => (
                            <li key={i}>{s}</li>
                          ))}
                        </ul>
                      ) : (
                        <div className="text-sm" style={{ color: COLORS.sub }}>
                          단계 정보 없음
                        </div>
                      )}
                    </div>

                    {/* 팁 */}
                    <div className="mb-6">
                      <h3 className="font-semibold mb-3">핵심 팁 (tips)</h3>
                      {Array.isArray(personalized?.content?.tips) &&
                      personalized.content.tips.length > 0 ? (
                        <ul className="list-disc pl-6 space-y-1 text-sm">
                          {personalized.content.tips.map((t, i) => (
                            <li key={i}>{t}</li>
                          ))}
                        </ul>
                      ) : (
                        <div className="text-sm" style={{ color: COLORS.sub }}>
                          팁 정보 없음
                        </div>
                      )}
                    </div>

                    {/* 판단 흔적 */}
                    <div>
                      <h3 className="font-semibold mb-3">판단 근거 (trace)</h3>
                      {Array.isArray(
                        personalized?.content?.trace?.decision_notes,
                      ) &&
                      personalized.content.trace.decision_notes.length > 0 ? (
                        <ul className="list-disc pl-6 space-y-1 text-sm">
                          {personalized.content.trace.decision_notes.map(
                            (n, i) => (
                              <li key={i}>{n}</li>
                            ),
                          )}
                        </ul>
                      ) : (
                        <div className="text-sm" style={{ color: COLORS.sub }}>
                          판단 흔적 없음
                        </div>
                      )}
                    </div>
                  </>
                )}
              </div>

              {/* 출처 및 참고자료 */}
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
                          style={{ backgroundColor: COLORS.bg }}
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
                      <div
                        className="p-5 rounded-lg"
                        style={{ backgroundColor: COLORS.bg }}
                      >
                        <h3 className="font-semibold text-lg mb-3">
                          {title ?? "참고 사례"}
                        </h3>
                        {page && (
                          <div className="text-base mb-2">페이지: {page}</div>
                        )}
                        <p className="text-base mb-4 leading-relaxed">
                          {sessionResult?.caseSource ??
                            "본 시뮬레이션은 실제 보이스피싱 사례를 바탕으로 제작되었습니다."}
                        </p>
                        <div className="space-y-3">
                          <div className="flex items-center gap-3">
                            <span className="text-base font-medium">출처:</span>
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
                                {sessionResult?.source ?? "-"}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })()}
                </div>
              </div>

              {/* AI 에이전트 로그 (숨김 처리) */}
              {false && filteredAgentLogs.length > 0 && (
                <div
                  className="rounded-2xl p-8"
                  style={{
                    backgroundColor: COLORS.panel,
                    border: `1px solid ${COLORS.border}`,
                  }}
                >
                  <h2 className="text-2xl font-semibold mb-5 flex items-center">
                    <Terminal className="mr-3" size={26} />
                    AI 에이전트 로그
                  </h2>

                  <div className="space-y-4">
                    {filteredAgentLogs.map((log, i) => {
                      const ts =
                        log?.timestamp ?? log?.time ?? log?.created_kst ?? "";
                      const type = log?.type ?? log?.level ?? "agent";
                      const message =
                        typeof log === "string"
                          ? log
                          : (log?.message ??
                            log?.text ??
                            log?.content ??
                            JSON.stringify(log));

                      return (
                        <div key={i} className="text-sm">
                          <div className="flex items-center gap-3 mb-2">
                            <span
                              className="text-xs px-3 py-2 rounded font-mono"
                              style={{ backgroundColor: COLORS.border }}
                            >
                              {ts}
                            </span>
                            <span
                              className="text-sm font-medium"
                              style={{ color: COLORS.blurple }}
                            >
                              {type}
                            </span>
                          </div>

                          <div
                            className="pl-5 py-3 rounded font-mono text-sm leading-relaxed"
                            style={{
                              backgroundColor: COLORS.bg,
                              borderLeft: `3px solid ${COLORS.blurple}`,
                            }}
                          >
                            {message}
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  <div
                    className="mt-5 pt-4 border-t"
                    style={{ borderColor: COLORS.border }}
                  >
                    <div className="flex items-center justify-between text-sm">
                      <span>총 {filteredAgentLogs.length}개 로그</span>
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
              세션 결과가 없습니다. 시뮬레이션을 먼저 실행해주세요.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

export default ReportPage;
