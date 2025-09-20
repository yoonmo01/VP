// // // src/App.jsx
// // import { useEffect, useLayoutEffect, useRef, useState } from "react";
// // import LandingPage from "./LandingPage";
// // import SimulatorPage from "./SimulatorPage";
// // import ReportPage from "./ReportPage";

// // /* ================== 색상 토큰 ================== */
// // const COLORS = {
// //   bg: "#1E1F22",
// //   panel: "#2B2D31",
// //   border: "#3F4147",
// //   text: "#DCDDDE",
// //   sub: "#B5BAC1",
// //   blurple: "#5865F2",
// //   success: "#57F287",
// //   warn: "#FEE75C",
// //   danger: "#ED4245",
// //   black: "#0A0A0A",
// //   white: "#FFFFFF",
// // };

// // const RAW_API_BASE = import.meta.env?.VITE_API_URL || window.location.origin;
// // const API_BASE = RAW_API_BASE.replace(/\/$/, "");
// // const API_PREFIX = "/api";
// // export const API_ROOT = `${API_BASE}${API_PREFIX}`;

// // console.log("VITE_API_URL =", import.meta.env.VITE_API_URL);
// // console.log("API_ROOT =", API_ROOT);

// // /* ================== 공통 fetch 유틸 ================== */
// // async function fetchWithTimeout(
// //   url,
// //   { method = "GET", headers = {}, body = null, timeout = 100000 } = {},
// // ) {
// //   const controller = new AbortController();
// //   const id = setTimeout(() => controller.abort(), timeout);

// //   const opts = { method, headers: { ...headers }, signal: controller.signal };
// //   if (body != null) {
// //     opts.body = typeof body === "string" ? body : JSON.stringify(body);
// //     opts.headers["Content-Type"] =
// //       opts.headers["Content-Type"] || "application/json";
// //   }

// //   try {
// //     const res = await fetch(url, opts);
// //     clearTimeout(id);
// //     if (!res.ok) {
// //       const txt = await res.text().catch(() => "");
// //       throw new Error(`HTTP ${res.status} ${res.statusText} ${txt}`);
// //     }
// //     const txt = await res.text();
// //     return txt ? JSON.parse(txt) : null;
// //   } catch (err) {
// //     if (err.name === "AbortError") throw new Error("요청 타임아웃 또는 취소됨");
// //     throw err;
// //   } finally {
// //     clearTimeout(id);
// //   }
// // }

// // /* ================== API 헬퍼 ================== */
// // async function getOffenders() {
// //   return fetchWithTimeout(`${API_ROOT}/offenders/`);
// // }
// // async function getVictims() {
// //   return fetchWithTimeout(`${API_ROOT}/victims/`);
// // }
// // async function getConversationBundle(caseId) {
// //   return fetchWithTimeout(
// //     `${API_ROOT}/conversations/${encodeURIComponent(caseId)}`,
// //   );
// // }
// // async function runConversationAsync(offenderId, victimId, payload = {}) {
// //   return fetchWithTimeout(
// //     `${API_ROOT}/conversations/run_async/${encodeURIComponent(offenderId)}/${encodeURIComponent(victimId)}`,
// //     { method: "POST", body: payload, timeout: 300000 },
// //   );
// // }
// // async function getJobStatus(jobId) {
// //   return fetchWithTimeout(
// //     `${API_ROOT}/conversations/job/${encodeURIComponent(jobId)}`,
// //     { timeout: 15000 },
// //   );
// // }
// // async function runAgentForCase(caseId, payload = {}, { verbose = false } = {}) {
// //   return fetchWithTimeout(
// //     `${API_ROOT}/agent/run/${encodeURIComponent(caseId)}?verbose=${verbose ? "true" : "false"}`,
// //     {
// //       method: "POST",
// //       body: payload,
// //       timeout: 120000, // 에이전트 작업은 길어질 수 있어 타임아웃 확대
// //     },
// //   );
// // }
// // /* ---------- 새로 추가 (에이전트 비동기 실행 + 폴링) ---------- */
// // async function runAgentForCaseAsync(
// //   caseId,
// //   { verbose = false, timeout = 1200000 } = {},
// // ) {
// //   const url = `${API_ROOT}/agent/run_async/${encodeURIComponent(caseId)}?verbose=${verbose ? "true" : "false"}`;
// //   return fetchWithTimeout(url, {
// //     method: "POST",
// //     timeout,
// //   });
// // }
// // async function getAgentJobStatus(jobId) {
// //   return fetchWithTimeout(
// //     `${API_ROOT}/agent/job/${encodeURIComponent(jobId)}`,
// //     { timeout: 300000 },
// //   );
// // }

// // /* ---------- 새로 추가 (개인화 예방법 fetch — 백엔드 라우터가 있다면 사용) ---------- */
// // async function getPersonalizedForCase(caseId) {
// //   // 백엔드에 /cases/{id}/personalized 엔드포인트가 있다면 사용하세요.
// //   // 없다면 이 함수는 호출하지 않거나, agent/run 완료 응답(result.personalized)에서 직접 읽으세요.
// //   return fetchWithTimeout(
// //     `${API_ROOT}/personalized/by-case/${encodeURIComponent(caseId)}`,
// //     { timeout: 200000 },
// //   );
// // }

// // // ==== use_agent 판별 및 로그 필터 유틸 ====
// // function isUseAgentTrue(log) {
// //   if (!log) return false;
// //   // 가능한 후보 필드들을 모두 검사 (서버가 어떤 형태를 쓰는지 모를 때 안전)
// //   const v =
// //     log?.use_agent ??
// //     log?.useAgent ??
// //     log?.use_agent_flag ??
// //     log?.use_agent_value;
// //   if (v === true) return true;
// //   if (v === "true") return true;
// //   if (v === 1 || v === "1") return true;
// //   return false;
// // }

// // function filterLogsByAgentFlag(logs = [], { forAgent = false } = {}) {
// //   if (!Array.isArray(logs)) return [];
// //   if (forAgent) {
// //     return logs.filter((l) => isUseAgentTrue(l));
// //   } else {
// //     return logs.filter((l) => !isUseAgentTrue(l));
// //   }
// // }

// // // === 요약 박스 컴포넌트 (미리보기 preview를 그대로 표시) ======================
// // function mapOutcomeToKorean(outcome) {
// //   switch (outcome) {
// //     case "attacker_fail":
// //       return "공격자 실패";
// //     case "attacker_success":
// //       return "공격자 성공";
// //     case "inconclusive":
// //       return "판단 불가";
// //     default:
// //       return outcome || "-";
// //   }
// // }
// // function toArrayReasons(reason, reasons) {
// //   if (Array.isArray(reasons) && reasons.length) return reasons;
// //   if (Array.isArray(reason)) return reason;
// //   if (typeof reason === "string" && reason.trim()) return [reason];
// //   return [];
// // }

// // function InlinePhishingSummaryBox({ preview }) {
// //   if (!preview) return null;
// //   const outcome = mapOutcomeToKorean(preview.outcome);
// //   const reasons = toArrayReasons(preview.reason, preview.reasons);
// //   const guidanceTitle = preview?.guidance?.title || "-";

// //   return (
// //     <div className="max-w-3xl mx-auto my-4">
// //       <div className="rounded-2xl border border-gray-200 bg-white/60 shadow-sm backdrop-blur p-4 md:p-5">
// //         <h3 className="text-base md:text-lg font-semibold mb-3">
// //           요약(대화 1 분석)
// //         </h3>
// //         <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
// //           <div>
// //             <div className="text-xs text-gray-500 mb-1">피싱여부</div>
// //             <div className="text-sm md:text-base text-gray-900">{outcome}</div>
// //           </div>
// //           <div>
// //             <div className="text-xs text-gray-500 mb-1">적용 지침</div>
// //             <div className="text-sm md:text-base text-gray-900 line-clamp-2">
// //               {guidanceTitle}
// //             </div>
// //           </div>
// //           <div>
// //             <div className="text-xs text-gray-500 mb-1">피싱여부 근거</div>
// //             {reasons.length === 0 ? (
// //               <div className="text-sm text-gray-500">-</div>
// //             ) : (
// //               <ul className="list-disc pl-5 space-y-1">
// //                 {reasons.map((r, i) => (
// //                   <li key={i} className="text-sm leading-6">
// //                     {r}
// //                   </li>
// //                 ))}
// //               </ul>
// //             )}
// //           </div>
// //         </div>
// //       </div>
// //     </div>
// //   );
// // }

// // /* ================== App 컴포넌트 ================== */
// // const App = () => {
// //   const [currentPage, setCurrentPage] = useState("landing");

// //   // data
// //   const [scenarios, setScenarios] = useState([]);
// //   const [characters, setCharacters] = useState([]);
// //   const [defaultCaseData, setDefaultCaseData] = useState(null);

// //   // selection / simulation
// //   const [selectedScenario, setSelectedScenario] = useState(null);
// //   const [selectedCharacter, setSelectedCharacter] = useState(null);
// //   const [simulationState, setSimulationState] = useState("IDLE"); // IDLE, PREPARE, RUNNING, FINISH
// //   const [messages, setMessages] = useState([]);
// //   const [sessionResult, setSessionResult] = useState(null);
// //   const [progress, setProgress] = useState(0);

// //   // modal / decision flags
// //   const [pendingAgentDecision, setPendingAgentDecision] = useState(false);
// //   const [showReportPrompt, setShowReportPrompt] = useState(false);

// //   // run control flags (요청하신 동작)
// //   const [hasInitialRun, setHasInitialRun] = useState(false); // 초기(Agent OFF) 실행했는지
// //   const [hasAgentRun, setHasAgentRun] = useState(false); // 에이전트 실행했는지
// //   const [agentRunning, setAgentRunning] = useState(false); // 에이전트 요청 중인지(로더)

// //   // refs for intervals / scrolling
// //   const scrollContainerRef = useRef(null);
// //   const jobPollRef = useRef(null);
// //   const simIntervalRef = useRef(null);
// //   const lastTurnRef = useRef(-1);

// //   // UI loading/error
// //   const [dataLoading, setDataLoading] = useState(true);
// //   const [dataError, setDataError] = useState(null);
// //   const [currentCaseId, setCurrentCaseId] = useState(null);

// //   const [agentPreviewShown, setAgentPreviewShown] = useState(false);

// //   // NEW: verbose 토글
// //   const [agentVerbose, setAgentVerbose] = useState(false);

// //   // victim image helper
// //   const getVictimImage = (photoPath) => {
// //     if (!photoPath) return null;
// //     try {
// //       const fileName = photoPath.split("/").pop();
// //       if (fileName)
// //         return new URL(`./assets/victims/${fileName}`, import.meta.url).href;
// //     } catch (e) {
// //       console.warn("이미지 로드 실패:", e);
// //     }
// //     return null;
// //   };

// //   /* 메시지 추가 유틸 */
// //   const addSystem = (content) =>
// //     setMessages((prev) => [
// //       ...prev,
// //       { type: "system", content, timestamp: new Date().toLocaleTimeString() },
// //     ]);
// //   const addAnalysis = (content) =>
// //     setMessages((prev) => [
// //       ...prev,
// //       { type: "analysis", content, timestamp: new Date().toLocaleTimeString() },
// //     ]);
// //   const addChat = (
// //     sender,
// //     content,
// //     timestamp = null,
// //     senderLabel = null,
// //     side = null,
// //   ) =>
// //     setMessages((prev) => [
// //       ...prev,
// //       {
// //         type: "chat",
// //         sender,
// //         senderLabel: senderLabel ?? sender,
// //         senderName: senderLabel ?? sender,
// //         side: side ?? (sender === "offender" ? "left" : "right"),
// //         content,
// //         timestamp: timestamp ?? new Date().toLocaleTimeString(),
// //       },
// //     ]);

// //   /* 스크롤 자동 하단 고정 */
// //   const stickToBottom = () => {
// //     const el = scrollContainerRef.current;
// //     if (el) el.scrollTop = el.scrollHeight;
// //   };
// //   useLayoutEffect(() => {
// //     stickToBottom();
// //   }, [
// //     messages,
// //     simulationState,
// //     selectedScenario,
// //     selectedCharacter,
// //     sessionResult,
// //   ]);

// //   useEffect(() => {
// //     const el = scrollContainerRef.current;
// //     if (!el) return;
// //     const ro = new ResizeObserver(() => stickToBottom());
// //     ro.observe(el);
// //     return () => ro.disconnect();
// //   }, []);

// //   /* 초기 데이터 로드 */
// //   useEffect(() => {
// //     let mounted = true;
// //     (async () => {
// //       try {
// //         setDataLoading(true);
// //         setDataError(null);
// //         const [offList, vicList] = await Promise.all([
// //           getOffenders(),
// //           getVictims(),
// //         ]);
// //         if (!mounted) return;
// //         setScenarios(Array.isArray(offList) ? offList : []);
// //         setCharacters(Array.isArray(vicList) ? vicList : []);
// //       } catch (err) {
// //         console.error("초기 데이터 로드 실패:", err);
// //         if (!mounted) return;
// //         setDataError(err.message || String(err));
// //       } finally {
// //         if (mounted) setDataLoading(false);
// //       }
// //     })();
// //     return () => {
// //       mounted = false;
// //     };
// //   }, []);

// //   /* playLogs: append 옵션 + onComplete 콜백 지원 */
// //   const playLogs = (
// //     logs = [],
// //     { append = false, speed = 1500 } = {},
// //     onComplete = null,
// //   ) => {
// //     if (!Array.isArray(logs) || logs.length === 0) {
// //       onComplete && onComplete();
// //       return;
// //     }

// //     if (!append) setMessages([]);
// //     setProgress((p) => (append ? p : 0));
// //     setSimulationState("RUNNING");

// //     if (simIntervalRef.current) {
// //       clearInterval(simIntervalRef.current);
// //       simIntervalRef.current = null;
// //     }

// //     let i = 0;
// //     const total = logs.length;
// //     const interval = setInterval(() => {
// //       if (i >= total) {
// //         clearInterval(interval);
// //         simIntervalRef.current = null;
// //         // 재생이 끝난 시점에 IDLE로 복귀
// //         setSimulationState("IDLE");
// //         onComplete && onComplete();
// //         return;
// //       }

// //       const log = logs[i];
// //       const role = (log.role || "").toLowerCase();
// //       const offenderLabel =
// //         log.offender_name ||
// //         (selectedScenario ? `피싱범${selectedScenario.id}` : "피싱범");
// //       const victimLabel =
// //         log.victim_name ||
// //         (selectedCharacter ? `피해자${selectedCharacter.id}` : "피해자");
// //       const displayLabel = role === "offender" ? offenderLabel : victimLabel;
// //       const side = role === "offender" ? "left" : "right";

// //       const ts =
// //         log.created_kst && typeof log.created_kst === "string"
// //           ? new Date(log.created_kst).toLocaleTimeString()
// //           : (log.created_kst ?? new Date().toLocaleTimeString());

// //       if (
// //         role === "analysis" ||
// //         role === "system" ||
// //         log.label === "analysis"
// //       ) {
// //         addAnalysis(log.content ?? "");
// //       } else {
// //         addChat(role || "offender", log.content ?? "", ts, displayLabel, side);
// //       }

// //       if (!append) {
// //         setProgress(((i + 1) / total) * 100);
// //       } else {
// //         setProgress((p) => Math.min(100, p + 100 / Math.max(1, total)));
// //       }

// //       i += 1;
// //     }, speed);

// //     simIntervalRef.current = interval;
// //   };

// //   /* job 폴링: job이 done 되면 bundle을 onDone으로 전달 (play는 호출하지 않음) */
// //   const startJobPollingForKick = (
// //     jobId,
// //     {
// //       intervalMs = 1200,
// //       timeoutMs = 120000,
// //       onProgress = null,
// //       onDone = null,
// //       onError = null,
// //     } = {},
// //   ) => {
// //     if (!jobId) {
// //       onError && onError(new Error("jobId 없음"));
// //       return;
// //     }
// //     if (jobPollRef.current) {
// //       clearInterval(jobPollRef.current);
// //       jobPollRef.current = null;
// //     }

// //     const start = Date.now();
// //     jobPollRef.current = setInterval(async () => {
// //       try {
// //         if (Date.now() - start > timeoutMs) {
// //           clearInterval(jobPollRef.current);
// //           jobPollRef.current = null;
// //           onError && onError(new Error("폴링 타임아웃"));
// //           return;
// //         }

// //         const st = await getJobStatus(jobId).catch((e) => {
// //           throw e;
// //         });
// //         onProgress && onProgress(st);

// //         if (!st) return;

// //         if (st.status === "error") {
// //           clearInterval(jobPollRef.current);
// //           jobPollRef.current = null;
// //           onError && onError(new Error(st.error || "job error"));
// //         } else if (st.status === "not_found") {
// //           clearInterval(jobPollRef.current);
// //           jobPollRef.current = null;
// //           onError && onError(new Error("job not_found"));
// //         } else if (st.status === "done" && st.case_id) {
// //           clearInterval(jobPollRef.current);
// //           jobPollRef.current = null;
// //           setCurrentCaseId(st.case_id);
// //           try {
// //             const bundle = await getConversationBundle(st.case_id);
// //             onDone && onDone(bundle, st.case_id);
// //           } catch (err) {
// //             onError && onError(err);
// //           }
// //         }
// //         // running이면 그냥 대기
// //       } catch (err) {
// //         console.warn("job 폴링 실패:", err);
// //       }
// //     }, intervalMs);
// //   };

// //   /* --------- startSimulation: 초기 실행 (agent_mode: "off") --------- */
// //   const startSimulation = async () => {
// //     if (!selectedScenario || !selectedCharacter) {
// //       addSystem("시나리오와 캐릭터를 먼저 선택해주세요.");
// //       return;
// //     }
// //     setAgentPreviewShown(false);

// //     if (hasAgentRun || agentRunning) return;
// //     // 최초 실행 표시 (한 번만 실행되게 함)
// //     setHasInitialRun(true);
// //     setAgentRunning(false);

// //     // 기존 정리
// //     if (simIntervalRef.current) {
// //       clearInterval(simIntervalRef.current);
// //       simIntervalRef.current = null;
// //     }
// //     if (jobPollRef.current) {
// //       clearInterval(jobPollRef.current);
// //       jobPollRef.current = null;
// //     }

// //     setSimulationState("PREPARE");
// //     setMessages([]);
// //     setProgress(0);
// //     setSessionResult(null);
// //     setCurrentCaseId(null);
// //     lastTurnRef.current = -1;
// //     setPendingAgentDecision(false);
// //     setShowReportPrompt(false);

// //     addSystem(
// //       `시뮬레이션(초기 대화) 시작: ${selectedScenario.name} / ${selectedCharacter.name}`,
// //     );

// //     try {
// //       const payload = {
// //         include_judgement: true,
// //         max_turns: 200,
// //         agent_mode: "off",
// //       };
// //       const kick = await runConversationAsync(
// //         selectedScenario.id,
// //         selectedCharacter.id,
// //         payload,
// //       );

// //       if (!kick || !kick.job_id) {
// //         addSystem("시뮬레이션 시작 실패: job_id를 받지 못했습니다.");
// //         setSimulationState("IDLE");
// //         return;
// //       }

// //       // job이 done 되면 bundle 받아 재생 -> 재생 완료 후 에이전트 결정 UI 노출
// //       startJobPollingForKick(kick.job_id, {
// //         onProgress: (st) => {
// //           /* optional */
// //         },
// //         onDone: (bundle) => {
// //           // 리포트용 전체 번들 저장
// //           setDefaultCaseData(bundle);
// //           setSessionResult((prev) => ({
// //             ...(prev || {}),
// //             phishing: bundle.phishing ?? prev?.phishing ?? null,
// //             isPhishing: bundle.phishing ?? prev?.isPhishing ?? null,
// //             evidence: bundle.evidence ?? prev?.evidence ?? null,
// //             totalTurns: bundle.total_turns ?? prev?.totalTurns ?? null,
// //           }));

// //           // 초기 재생은 use_agent === true 인 항목을 제외
// //           const initialLogs = filterLogsByAgentFlag(bundle.logs || [], {
// //             forAgent: false,
// //           });

// //           if (initialLogs.length === 0) {
// //             addSystem(
// //               "표시할 초기 대화 로그가 없습니다 (use_agent=false 필터 적용).",
// //             );
// //             setPendingAgentDecision(true);
// //             return;
// //           }

// //           playLogs(initialLogs, { append: false, speed: 700 }, () => {
// //             setPendingAgentDecision(true);
// //             addSystem(
// //               "대화 재생이 완료되었습니다. 에이전트 사용 여부를 선택해주세요.",
// //             );
// //           });
// //         },

// //         onError: (err) => {
// //           console.error("초기 job 오류:", err);
// //           addSystem("초기 시뮬레이션 중 오류가 발생했습니다.");
// //           setSimulationState("IDLE");
// //         },
// //       });
// //     } catch (err) {
// //       console.error("시뮬레이션 실행 실패:", err);
// //       addSystem("시뮬레이션 실행 실패 (콘솔 로그 확인).");
// //       setSimulationState("IDLE");
// //     }
// //   };

// //   /* --------- declineAgentRun: '아니요' 처리 (추가 실행 없음) --------- */
// //   const declineAgentRun = () => {
// //     setPendingAgentDecision(false);
// //     setShowReportPrompt(true);
// //     addSystem("에이전트 사용을 건너뜁니다. 리포트를 확인할 수 있습니다.");
// //     // hasInitialRun remains true; no further runs allowed unless resetToSelection()
// //   };

// //   /* --------- startAgentRun: '예' 처리 (append 재생, 에이전트 한번만) --------- */
// //   // 기존 startAgentRun 함수 전체를 아래로 교체하세요
// //   const startAgentRun = async () => {
// //     if (!currentCaseId) {
// //       addSystem(
// //         "case_id가 없습니다. 초기 시뮬레이션이 정상적으로 완료되었는지 확인하세요.",
// //       );
// //       return;
// //     }
// //     if (hasAgentRun || agentRunning) return;

// //     setPendingAgentDecision(false);
// //     setSimulationState("PREPARE");
// //     setAgentRunning(true);
// //     addSystem(
// //       `에이전트 시뮬레이션을 시작합니다... (verbose=${agentVerbose ? "on" : "off"})`,
// //     );

// //     try {
// //       // 1) 비동기 실행 kick
// //       const kick = await runAgentForCaseAsync(currentCaseId, {
// //         verbose: agentVerbose,
// //         timeout: 120000,
// //       });
// //       if (!kick || !kick.job_id) {
// //         addSystem("에이전트 실행 실패: job_id를 받지 못했습니다.");
// //         setAgentRunning(false);
// //         setSimulationState("IDLE");
// //         return;
// //       }

// //       // 2) /agent/job/{id} 폴링
// //       const jobId = kick.job_id;
// //       const start = Date.now();
// //       const POLL_INTERVAL = 1200;
// //       const POLL_TIMEOUT = 180000; // 3분

// //       const poll = async () => {
// //         // 타임아웃
// //         if (Date.now() - start > POLL_TIMEOUT)
// //           throw new Error("에이전트 폴링 타임아웃");

// //         const st = await getAgentJobStatus(jobId);
// //         if (!st) return null;

// //         // ✅ result.preview 우선, 없으면 st.preview (서버 래핑 차이 흡수)
// //         const preview = st?.result?.preview ?? st?.preview ?? null;
// //         if (preview && !agentPreviewShown) {
// //           addSystem(
// //             [
// //               "🔎 에이전트 사전 판정(미리보기)",
// //               `- 피싱 여부: ${preview.phishing ? "성공(공격자 우세)" : "실패(피해자 우세)"}`,
// //               Array.isArray(preview.reasons) && preview.reasons.length
// //                 ? `- 이유: ${preview.reasons.slice(0, 3).join(" / ")}`
// //                 : "",
// //               preview.guidance?.title
// //                 ? `- 지침: ${preview.guidance.title}`
// //                 : "",
// //             ]
// //               .filter(Boolean)
// //               .join("\n"),
// //           );
// //           setSessionResult((prev) => ({ ...(prev || {}), preview }));
// //           setAgentPreviewShown(true);
// //         }

// //         if (st.status === "error")
// //           throw new Error(st.error || "agent job error");
// //         if (st.status === "not_found") throw new Error("agent job not_found");
// //         if (st.status === "running") return null;

// //         // done
// //         return st.result || st; // 라우터 구현에 따라 result 랩핑/직접일 수 있음
// //       };

// //       let result = null;
// //       while (true) {
// //         const r = await poll();
// //         if (r) {
// //           result = r;
// //           break;
// //         }
// //         await new Promise((res) => setTimeout(res, POLL_INTERVAL));
// //       }

// //       // 3) 결과 처리: case_id로 번들 가져오기
// //       const cid = result.case_id || currentCaseId;
// //       setCurrentCaseId(cid);
// //       const bundle = await getConversationBundle(cid);

// //       setDefaultCaseData(bundle);

// //       // personalized가 번들에 없으면(백엔드 구현에 따라),
// //       // 필요 시 별도 조회 시도 (엔드포인트가 있을 때만)
// //       let personalized =
// //         bundle.personalized || bundle.personalized_preventions || null;
// //       if (!personalized) {
// //         try {
// //           const pj = await getPersonalizedForCase(cid);
// //           if (pj) personalized = pj;
// //         } catch (_) {}
// //       }

// //       // 세션 상태 업데이트
// //       const agentOnlyLogs = filterLogsByAgentFlag(bundle.logs || [], {
// //         forAgent: true,
// //       });
// //       setSessionResult((prev) => ({
// //         ...(prev || {}),
// //         phishing: bundle.phishing ?? prev?.phishing ?? null,
// //         isPhishing: bundle.phishing ?? prev?.isPhishing ?? null,
// //         evidence: bundle.evidence ?? prev?.evidence ?? null,
// //         totalTurns: bundle.total_turns ?? prev?.totalTurns ?? null,
// //         agentUsed: true,
// //         agentLogs: agentOnlyLogs,
// //         personalized, // 리포트에서 쓰세요
// //       }));

// //       // 4) 에이전트 로그만 append 재생
// //       if (!agentOnlyLogs.length) {
// //         addSystem("에이전트 전용 로그(use_agent=true)가 없습니다.");
// //         setHasAgentRun(true);
// //         setAgentRunning(false);
// //         setShowReportPrompt(true);
// //         return;
// //       }

// //       playLogs(agentOnlyLogs, { append: true, speed: 1500 }, () => {
// //         setHasAgentRun(true);
// //         setAgentRunning(false);
// //         setShowReportPrompt(true);
// //         addSystem(
// //           "에이전트 대화 재생이 완료되었습니다. 리포트를 확인할 수 있습니다.",
// //         );
// //       });
// //     } catch (err) {
// //       console.error("에이전트 실행 실패:", err);
// //       addSystem(`에이전트 실행 실패: ${err.message || String(err)}`);
// //       setAgentRunning(false);
// //       setSimulationState("IDLE");
// //     }
// //   };

// //   /* --------- resetToSelection: 모든 플래그 초기화 --------- */
// //   const resetToSelection = () => {
// //     setSelectedScenario(null);
// //     setSelectedCharacter(null);
// //     setMessages([]);
// //     setSessionResult(null);
// //     setProgress(0);
// //     setSimulationState("IDLE");
// //     // setPendingAgentDecision(false);
// //     // setShowReportPrompt(false);

// //     // setHasInitialRun(false);
// //     // setHasAgentRun(false);
// //     // setAgentRunning(false);

// //     // setCurrentCaseId(null);
// //     setCurrentPage("simulator");

// //     // if (simIntervalRef.current) {
// //     //   clearInterval(simIntervalRef.current);
// //     //   simIntervalRef.current = null;
// //     // }
// //     // if (jobPollRef.current) {
// //     //   clearInterval(jobPollRef.current);
// //     //   jobPollRef.current = null;
// //     // }
// //     // lastTurnRef.current = -1;
// //   };

// //    /* --------- onBack 핸들러 추가 --------- */
// //   const handleBack = () => {
// //     setCurrentPage("landing");
// //   };

// //   // cleanup on unmount
// //   useEffect(() => {
// //     return () => {
// //       if (simIntervalRef.current) {
// //         clearInterval(simIntervalRef.current);
// //         simIntervalRef.current = null;
// //       }
// //       if (jobPollRef.current) {
// //         clearInterval(jobPollRef.current);
// //         jobPollRef.current = null;
// //       }
// //     };
// //   }, []);

// //   /* --------- pageProps 전달 --------- */
// //   const pageProps = {
// //     COLORS,
// //     apiRoot: API_ROOT,     // ✅ 추가
// //     onBack: handleBack,    // ✅ 추가
// //     setCurrentPage,
// //     selectedScenario,
// //     setSelectedScenario,
// //     selectedCharacter,
// //     setSelectedCharacter,
// //     simulationState,
// //     setSimulationState,
// //     messages,
// //     addSystem,
// //     addAnalysis,
// //     addChat,
// //     sessionResult,
// //     resetToSelection,
// //     startSimulation,
// //     startAgentRun,
// //     declineAgentRun,
// //     scenarios,
// //     characters,
// //     scrollContainerRef,
// //     defaultCaseData,
// //     dataLoading,
// //     dataError,
// //     currentCaseId,
// //     pendingAgentDecision,
// //     showReportPrompt,
// //     hasInitialRun,
// //     hasAgentRun,
// //     agentRunning,
// //     progress,
// //     setProgress,
// //     setShowReportPrompt,
// //     agentVerbose, // NEW
// //     setAgentVerbose, // NEW
// //     victimImageUrl: selectedCharacter
// //       ? getVictimImage(selectedCharacter.photo_path)
// //       : null,
// //   };

// //   return (
// //     <div className="font-sans">
// //       {currentPage === "landing" && (
// //         <LandingPage setCurrentPage={setCurrentPage} />
// //       )}
// //       {currentPage === "simulator" && <SimulatorPage {...pageProps} />}
// //       {currentPage === "report" && (
// //         <ReportPage {...pageProps} defaultCaseData={defaultCaseData} />
// //       )}
// //     </div>
// //   );
// // };

// // export default App;


// // src/App.jsx
// import { useEffect, useLayoutEffect, useRef, useState, useCallback} from "react";
// import LandingPage from "./LandingPage";
// import SimulatorPage from "./SimulatorPage";
// import ReportPage from "./ReportPage";

// /* ================== 색상 토큰 ================== */
// const COLORS = {
//   bg: "#1E1F22",
//   panel: "#2B2D31",
//   border: "#3F4147",
//   text: "#DCDDDE",
//   sub: "#B5BAC1",
//   blurple: "#5865F2",
//   success: "#57F287",
//   warn: "#FEE75C",
//   danger: "#ED4245",
//   black: "#0A0A0A",
//   white: "#FFFFFF",
// };

// const RAW_API_BASE = import.meta.env?.VITE_API_URL || window.location.origin;
// const API_BASE = RAW_API_BASE.replace(/\/$/, "");
// const API_PREFIX = "/api";
// export const API_ROOT = `${API_BASE}${API_PREFIX}`;

// console.log("VITE_API_URL =", import.meta.env.VITE_API_URL);
// console.log("API_ROOT =", API_ROOT);

// /* ================== MOCK MODE (더미 JSONL 주입) ================== */
// // 더미 켜기: true / 실제 API로: false
// const MOCK_MODE = true;

// // public의 JSONL을 줄단위로 읽기
// async function loadJsonlFromPublic(path) {
//   const res = await fetch(path, { cache: "no-store" });
//   if (!res.ok) throw new Error(`JSONL 로드 실패: ${res.status} ${res.statusText}`);
//   const text = await res.text();
//   return text
//     .split(/\r?\n/)
//     .filter(Boolean)
//     .map((line) => JSON.parse(line));
// }

// // JSONL → 프론트가 기대하는 번들 스키마로 변환
// function jsonlToConversationBundle(rows) {
//   const case_id = "dummy-case-1";
//   if (!Array.isArray(rows) || rows.length === 0) {
//     return { case_id, logs: [], total_turns: 0 };
//   }
//   const t0 = Date.now();
//   const logs = rows.map((r, i) => {
//     const role = (r.role || "").toLowerCase(); // "offender" | "victim"
//      const textFromRow =
//       typeof r.text === "string" ? r.text : "";

//     const jr = r.json_reply || {};
//     const vThoughts = typeof jr.thoughts === "string" ? jr.thoughts.trim() : "";
//     const vDialogue = typeof jr.dialogue === "string" ? jr.dialogue.trim() : "";

//     const content =
//       role === "victim"
//         ? [vThoughts, vDialogue].filter(Boolean).join("\n")
//         : textFromRow;

//     return {
//       run: r.run_no ?? 1,
//       turn_index: r.turn ?? i,
//       role,
//       content,
//       created_kst: new Date(t0 + i * 700).toISOString(),
//       offender_name: "사칭 콜센터",
//       victim_name: "피해자",
//       use_agent: (r.run_no ?? 1) !== 1,    // 1라운드만 false, 나머지 true처럼 표시
//       guidance_type: null,
//       guideline: null,
//       thoughts: vThoughts || null,
//     };
//   });

//   // 정렬(안전)
//   logs.sort((a, b) => {
//     const ra = (a.run ?? 0) - (b.run ?? 0);
//     if (ra !== 0) return ra;
//     const ta = (a.turn_index ?? 0) - (b.turn_index ?? 0);
//     if (ta !== 0) return ta;
//     return new Date(a.created_kst) - new Date(b.created_kst);
//   });

//   const total_turns = Math.max(...logs.map((x) => x.turn_index ?? 0), 0) + 1;

//   return {
//     case_id,
//     scenario: {
//       methods_used: [],
//       last_analysis: {
//         outcome: "inconclusive",
//         reasons: [],
//         guidance: { type: null, title: null, category: null },
//         phishing: null,
//       },
//     },
//     offender: { id: 1, name: "사칭 콜센터", type: "더미", is_active: true },
//     victim: {
//       id: 1,
//       name: "피해자",
//       is_active: true,
//       photo_path: "/static/images/victims/1.png",
//     },
//     logs,
//     total_turns,
//     phishing: null,
//     evidence: null,
//   };
// }

// // JSONL 캐시 (불필요한 fetch 방지)
// let __dummyBundleCache = null;
// async function getDummyBundle() {
//   if (__dummyBundleCache) return __dummyBundleCache;
//   const rows = await loadJsonlFromPublic("/dummy/sim_convo_rounds1_2_full.jsonl");
//   __dummyBundleCache = jsonlToConversationBundle(rows);
//   return __dummyBundleCache;
// }

// /* ================== 공통 fetch 유틸 ================== */


// async function fetchWithTimeout(
//   url,
//   { method = "GET", headers = {}, body = null, timeout = 100000 } = {},
// ) {
//   const controller = new AbortController();
//   const id = setTimeout(() => controller.abort(), timeout);

//   const opts = { method, headers: { ...headers }, signal: controller.signal };
//   if (body != null) {
//     opts.body = typeof body === "string" ? body : JSON.stringify(body);
//     opts.headers["Content-Type"] =
//       opts.headers["Content-Type"] || "application/json";
//   }

//   try {
//     const res = await fetch(url, opts);
//     clearTimeout(id);
//     if (!res.ok) {
//       const txt = await res.text().catch(() => "");
//       throw new Error(`HTTP ${res.status} ${res.statusText} ${txt}`);
//     }
//     const txt = await res.text();
//     return txt ? JSON.parse(txt) : null;
//   } catch (err) {
//     if (err.name === "AbortError") throw new Error("요청 타임아웃 또는 취소됨");
//     throw err;
//   } finally {
//     clearTimeout(id);
//   }
// }

// /* ================== API 헬퍼 ================== */

// /* 얘가 위주*/
// async function runReactSimulation(body) {
//   if (MOCK_MODE) {
//     // 실제 서버 대신 case_id만 즉시 돌려줌
//     return { case_id: (await getDummyBundle()).case_id };
//   }
//   // body는 SimulationStartRequest 스키마에 맞춤
//   return fetchWithTimeout(`${API_ROOT}/react-agent/simulation`, {
//     method: "POST",
//     body,
//     timeout: 600000, // 넉넉히
//   });
// }


// async function getOffenders() {
  
//   return fetchWithTimeout(`${API_ROOT}/offenders/`);
// }
// async function getVictims() {
  
//   return fetchWithTimeout(`${API_ROOT}/victims/`);
// }
// async function getConversationBundle(caseId) {
//   if (MOCK_MODE) {
//     // 어떤 caseId가 오든 동일 더미 번들을 반환 (선택과 무관하게 항상 같은 데이터)
//     return await getDummyBundle();
//   }
//   return fetchWithTimeout(
//     `${API_ROOT}/conversations/${encodeURIComponent(caseId)}`,
//   );
// }
// async function runConversationAsync(offenderId, victimId, payload = {}) {
//   return fetchWithTimeout(
//     `${API_ROOT}/conversations/run_async/${encodeURIComponent(offenderId)}/${encodeURIComponent(victimId)}`,
//     { method: "POST", body: payload, timeout: 300000 },
//   );
// }
// async function getJobStatus(jobId) {
//   return fetchWithTimeout(
//     `${API_ROOT}/conversations/job/${encodeURIComponent(jobId)}`,
//     { timeout: 15000 },
//   );
// }
// async function runAgentForCase(caseId, payload = {}, { verbose = false } = {}) {
//   return fetchWithTimeout(
//     `${API_ROOT}/agent/run/${encodeURIComponent(caseId)}?verbose=${verbose ? "true" : "false"}`,
//     {
//       method: "POST",
//       body: payload,
//       timeout: 120000, // 에이전트 작업은 길어질 수 있어 타임아웃 확대
//     },
//   );
// }
// /* ---------- 새로 추가 (에이전트 비동기 실행 + 폴링) ---------- */
// async function runAgentForCaseAsync(
//   caseId,
//   { verbose = false, timeout = 1200000 } = {},
// ) {
//   const url = `${API_ROOT}/agent/run_async/${encodeURIComponent(caseId)}?verbose=${verbose ? "true" : "false"}`;
//   return fetchWithTimeout(url, {
//     method: "POST",
//     timeout,
//   });
// }
// async function getAgentJobStatus(jobId) {
//   return fetchWithTimeout(
//     `${API_ROOT}/agent/job/${encodeURIComponent(jobId)}`,
//     { timeout: 300000 },
//   );
// }

// /* ---------- 새로 추가 (개인화 예방법 fetch — 백엔드 라우터가 있다면 사용) ---------- */
// async function getPersonalizedForCase(caseId) {
//   // 백엔드에 /cases/{id}/personalized 엔드포인트가 있다면 사용하세요.
//   // 없다면 이 함수는 호출하지 않거나, agent/run 완료 응답(result.personalized)에서 직접 읽으세요.
//   return fetchWithTimeout(
//     `${API_ROOT}/personalized/by-case/${encodeURIComponent(caseId)}`,
//     { timeout: 200000 },
//   );
// }

// // ==== use_agent 판별 및 로그 필터 유틸 ====
// function isUseAgentTrue(log) {
//   if (!log) return false;
//   // 가능한 후보 필드들을 모두 검사 (서버가 어떤 형태를 쓰는지 모를 때 안전)
//   const v =
//     log?.use_agent ??
//     log?.useAgent ??
//     log?.use_agent_flag ??
//     log?.use_agent_value;
//   if (v === true) return true;
//   if (v === "true") return true;
//   if (v === 1 || v === "1") return true;
//   return false;
// }

// function filterLogsByAgentFlag(logs = [], { forAgent = false } = {}) {
//   if (!Array.isArray(logs)) return [];
//   if (forAgent) {
//     return logs.filter((l) => isUseAgentTrue(l));
//   } else {
//     return logs.filter((l) => !isUseAgentTrue(l));
//   }
// }

// // === 요약 박스 컴포넌트 (미리보기 preview를 그대로 표시) ======================
// function mapOutcomeToKorean(outcome) {
//   switch (outcome) {
//     case "attacker_fail":
//       return "공격자 실패";
//     case "attacker_success":
//       return "공격자 성공";
//     case "inconclusive":
//       return "판단 불가";
//     default:
//       return outcome || "-";
//   }
// }
// function toArrayReasons(reason, reasons) {
//   if (Array.isArray(reasons) && reasons.length) return reasons;
//   if (Array.isArray(reason)) return reason;
//   if (typeof reason === "string" && reason.trim()) return [reason];
//   return [];
// }

// function InlinePhishingSummaryBox({ preview }) {
//   if (!preview) return null;
//   const outcome = mapOutcomeToKorean(preview.outcome);
//   const reasons = toArrayReasons(preview.reason, preview.reasons);
//   const guidanceTitle = preview?.guidance?.title || "-";

//   return (
//     <div className="max-w-3xl mx-auto my-4">
//       <div className="rounded-2xl border border-gray-200 bg-white/60 shadow-sm backdrop-blur p-4 md:p-5">
//         <h3 className="text-base md:text-lg font-semibold mb-3">
//           요약(대화 1 분석)
//         </h3>
//         <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
//           <div>
//             <div className="text-xs text-gray-500 mb-1">피싱여부</div>
//             <div className="text-sm md:text-base text-gray-900">{outcome}</div>
//           </div>
//           <div>
//             <div className="text-xs text-gray-500 mb-1">적용 지침</div>
//             <div className="text-sm md:text-base text-gray-900 line-clamp-2">
//               {guidanceTitle}
//             </div>
//           </div>
//           <div>
//             <div className="text-xs text-gray-500 mb-1">피싱여부 근거</div>
//             {reasons.length === 0 ? (
//               <div className="text-sm text-gray-500">-</div>
//             ) : (
//               <ul className="list-disc pl-5 space-y-1">
//                 {reasons.map((r, i) => (
//                   <li key={i} className="text-sm leading-6">
//                     {r}
//                   </li>
//                 ))}
//               </ul>
//             )}
//           </div>
//         </div>
//       </div>
//     </div>
//   );
// }

// /* ================== App 컴포넌트 ================== */
// const App = () => {
//   const [currentPage, setCurrentPage] = useState("landing");

//   // data
//   const [scenarios, setScenarios] = useState([]);
//   const [characters, setCharacters] = useState([]);
//   const [defaultCaseData, setDefaultCaseData] = useState(null);

//   // selection / simulation
//   const [selectedScenario, setSelectedScenario] = useState(null);
//   const [selectedCharacter, setSelectedCharacter] = useState(null);
//   const [simulationState, setSimulationState] = useState("IDLE"); // IDLE, PREPARE, RUNNING, FINISH
//   const [messages, setMessages] = useState([]);
//   const [sessionResult, setSessionResult] = useState(null);
//   const [progress, setProgress] = useState(0);

//   // modal / decision flags
//   const [pendingAgentDecision, setPendingAgentDecision] = useState(false);
//   const [showReportPrompt, setShowReportPrompt] = useState(false);

//   // run control flags (요청하신 동작)
//   const [hasInitialRun, setHasInitialRun] = useState(false); // 초기(Agent OFF) 실행했는지
//   const [hasAgentRun, setHasAgentRun] = useState(false); // 에이전트 실행했는지
//   const [agentRunning, setAgentRunning] = useState(false); // 에이전트 요청 중인지(로더)

//   // refs for intervals / scrolling
//   const scrollContainerRef = useRef(null);
//   const jobPollRef = useRef(null);
//   const simIntervalRef = useRef(null);
//   const lastTurnRef = useRef(-1);

//   // UI loading/error
//   const [dataLoading, setDataLoading] = useState(true);
//   const [dataError, setDataError] = useState(null);
//   const [currentCaseId, setCurrentCaseId] = useState(null);

//   const [agentPreviewShown, setAgentPreviewShown] = useState(false);

//   // NEW: verbose 토글
//   const [agentVerbose, setAgentVerbose] = useState(false);

//   // victim image helper
//   const getVictimImage = (photoPath) => {
//     if (!photoPath) return null;
//     try {
//       const fileName = photoPath.split("/").pop();
//       if (fileName)
//         return new URL(`./assets/victims/${fileName}`, import.meta.url).href;
//     } catch (e) {
//       console.warn("이미지 로드 실패:", e);
//     }
//     return null;
//   };

//   /* 메시지 추가 유틸 */
//   const addSystem = (content) =>
//     setMessages((prev) => [
//       ...prev,
//       { type: "system", content, timestamp: new Date().toLocaleTimeString() },
//     ]);
//   const addAnalysis = (content) =>
//     setMessages((prev) => [
//       ...prev,
//       { type: "analysis", content, timestamp: new Date().toLocaleTimeString() },
//     ]);
//   const addChat = (
//     sender,
//     content,
//     timestamp = null,
//     senderLabel = null,
//     side = null,
//   ) =>
//     setMessages((prev) => [
//       ...prev,
//       {
//         type: "chat",
//         sender,
//         senderLabel: senderLabel ?? sender,
//         senderName: senderLabel ?? sender,
//         side: side ?? (sender === "offender" ? "left" : "right"),
//         content,
//         timestamp: timestamp ?? new Date().toLocaleTimeString(),
//       },
//     ]);

//   /* 스크롤 자동 하단 고정 */
//   const stickToBottom = () => {
//     const el = scrollContainerRef.current;
//     if (el) el.scrollTop = el.scrollHeight;
//   };
//   useLayoutEffect(() => {
//     stickToBottom();
//   }, [
//     messages,
//     simulationState,
//     selectedScenario,
//     selectedCharacter,
//     sessionResult,
//   ]);

//   useEffect(() => {
//     const el = scrollContainerRef.current;
//     if (!el) return;
//     const ro = new ResizeObserver(() => stickToBottom());
//     ro.observe(el);
//     return () => ro.disconnect();
//   }, []);

//   /* 초기 데이터 로드 */
//   useEffect(() => {
//     let mounted = true;
//     (async () => {
//       try {
//         setDataLoading(true);
//         setDataError(null);
//         const [offList, vicList] = await Promise.all([
//           getOffenders(),
//           getVictims(),
//         ]);
//         if (!mounted) return;
//         setScenarios(Array.isArray(offList) ? offList : []);
//         setCharacters(Array.isArray(vicList) ? vicList : []);
//       } catch (err) {
//         console.error("초기 데이터 로드 실패:", err);
//         if (!mounted) return;
//         setDataError(err.message || String(err));
//       } finally {
//         if (mounted) setDataLoading(false);
//       }
//     })();
//     return () => {
//       mounted = false;
//     };
//   }, []);

//   const playLogs = useCallback(
//   (logs = [], { append = false, speed = 1500 } = {}, onComplete = null) => {
//     if (!Array.isArray(logs) || logs.length === 0) {
//       onComplete && onComplete();
//       return;
//     }

//     if (!append) setMessages([]);
//     setProgress((p) => (append ? p : 0));
//     setSimulationState("RUNNING");

//     // 기존 타이머 정리
//     if (simIntervalRef.current) {
//       clearTimeout(simIntervalRef.current);
//       simIntervalRef.current = null;
//     }

//     const total = logs.length;
//     let idx = 0;
//     let prevRun = logs[0]?.run ?? 1;

//     const step = () => {
//       if (idx >= total) {
//         simIntervalRef.current = null;
//         setSimulationState("IDLE");
//         onComplete && onComplete();
//         return;
//       }

//       const log = logs[idx];
//       const role = (log.role || "").toLowerCase();
//       const currRun = log.run ?? prevRun;

//       // 기본 속도
//       let delay = speed;

//       // 🔸 run 1 → 2로 넘어갈 때 5초 텀 추가
//       if (prevRun === 1 && currRun === 2) {
//         delay += 5000; // 5초
//       }

//       simIntervalRef.current = setTimeout(() => {
//         const offenderLabel =
//           log.offender_name ||
//           (selectedScenario ? `피싱범${selectedScenario.id}` : "피싱범");
//         const victimLabel =
//           log.victim_name ||
//           (selectedCharacter ? `피해자${selectedCharacter.id}` : "피해자");
//         const displayLabel = role === "offender" ? offenderLabel : victimLabel;
//         const side = role === "offender" ? "left" : "right";

//         // 🧠 victim thoughts를 같은 말풍선 안에 합치기
//         const content = String(log.content ?? "");

//         const ts =
//           log.created_kst && typeof log.created_kst === "string"
//             ? new Date(log.created_kst).toLocaleTimeString()
//             : log.created_kst ?? new Date().toLocaleTimeString();

//         if (role === "analysis" || role === "system" || log.label === "analysis") {
//           addAnalysis(content);
//         } else {
//           addChat(role || "offender", content, ts, displayLabel, side);
//         }

//         if (!append) {
//           setProgress(((idx + 1) / total) * 100);
//         } else {
//           setProgress((p) => Math.min(100, p + 100 / Math.max(1, total)));
//         }

//         prevRun = currRun;
//         idx += 1;
//         step(); // 다음 로그 예약
//       }, delay);
//     };

//     step();
//   },
//   [
//     addAnalysis,
//     addChat,
//     setMessages,
//     setProgress,
//     setSimulationState,
//     selectedScenario,
//     selectedCharacter,
//   ],
// );
//   /* playLogs: append 옵션 + onComplete 콜백 지원 */
//   // const playLogs = useCallback((logs = [],{ append = false, speed = 1500 } = {},onComplete = null,) => {
//   //   if (!Array.isArray(logs) || logs.length === 0) {
//   //     onComplete && onComplete();
//   //     return;
//   //   }

//   //   if (!append) setMessages([]);
//   //   setProgress((p) => (append ? p : 0));
//   //   setSimulationState("RUNNING");

//   //   if (simIntervalRef.current) {
//   //     clearInterval(simIntervalRef.current);
//   //     simIntervalRef.current = null;
//   //   }

//   //   let i = 0;
//   //   const total = logs.length;
//   //   const interval = setInterval(() => {
//   //     if (i >= total) {
//   //       clearInterval(interval);
//   //       simIntervalRef.current = null;
//   //       // 재생이 끝난 시점에 IDLE로 복귀
//   //       setSimulationState("IDLE");
//   //       onComplete && onComplete();
//   //       return;
//   //     }

//   //     const log = logs[i];
//   //     const role = (log.role || "").toLowerCase();
//   //     const offenderLabel =
//   //       log.offender_name ||
//   //       (selectedScenario ? `피싱범${selectedScenario.id}` : "피싱범");
//   //     const victimLabel =
//   //       log.victim_name ||
//   //       (selectedCharacter ? `피해자${selectedCharacter.id}` : "피해자");
//   //     const displayLabel = role === "offender" ? offenderLabel : victimLabel;
//   //     const side = role === "offender" ? "left" : "right";

//   //     const ts =
//   //       log.created_kst && typeof log.created_kst === "string"
//   //         ? new Date(log.created_kst).toLocaleTimeString()
//   //         : (log.created_kst ?? new Date().toLocaleTimeString());

//   //     if (
//   //       role === "analysis" ||
//   //       role === "system" ||
//   //       log.label === "analysis"
//   //     ) {
//   //       addAnalysis(log.content ?? "");
//   //     } else {
//   //       addChat(role || "offender", log.content ?? "", ts, displayLabel, side);
//   //     }

//   //     if (!append) {
//   //       setProgress(((i + 1) / total) * 100);
//   //     } else {
//   //       setProgress((p) => Math.min(100, p + 100 / Math.max(1, total)));
//   //     }

//   //     i += 1;
//   //   }, speed);

//   //   simIntervalRef.current = interval;
//   // },[addAnalysis, addChat, setMessages, setProgress, setSimulationState, selectedScenario, selectedCharacter]);

//   const showConversationBundle = useCallback((bundle) => {
//     // 리포트/요약용 상태 저장
//     setDefaultCaseData(bundle);
//     setSessionResult((prev) => ({
//       ...(prev || {}),
//       phishing: bundle.phishing ?? prev?.phishing ?? null,
//       isPhishing: bundle.phishing ?? prev?.isPhishing ?? null,
//       evidence: bundle.evidence ?? prev?.evidence ?? null,
//       totalTurns: bundle.total_turns ?? prev?.totalTurns ?? null,
//     }));

//     // 안전 정렬
//     const logs = (bundle.logs || []).slice().sort((a, b) => {
//       const ra = (a.run ?? 0) - (b.run ?? 0);
//       if (ra !== 0) return ra;
//       const ta = (a.turn_index ?? 0) - (b.turn_index ?? 0);
//       if (ta !== 0) return ta;
//       const da = new Date(a.created_at || a.created_kst || 0) - new Date(b.created_at || b.created_kst || 0);
//       return da;
//     });

//     if (!logs.length) {
//       addSystem("표시할 대화 로그가 없습니다.");
//       setShowReportPrompt(true);
//       setSimulationState("IDLE");
//       return;
//     }

//     // 전체 로그 재생 (필요하면 use_agent로 필터링)
//     playLogs(logs, { append: false, speed: 700 }, () => {
//       setShowReportPrompt(true);
//       addSystem("대화 재생이 완료되었습니다. 리포트를 확인할 수 있습니다.");
//     });
//   }, [addSystem, playLogs, setShowReportPrompt, setSimulationState]);

//   const showExistingCase = useCallback(async (caseId) => {
//     try {
//       const bundle = await getConversationBundle(caseId);
//       setCurrentCaseId(caseId);
//       showConversationBundle(bundle);
//     } catch (e) {
//       addSystem(`대화 불러오기 실패: ${e.message}`);
//     }
//   }, [addSystem, showConversationBundle]);

//   /* job 폴링: job이 done 되면 bundle을 onDone으로 전달 (play는 호출하지 않음) */
//   const startJobPollingForKick = (
//     jobId,
//     {
//       intervalMs = 1200,
//       timeoutMs = 120000,
//       onProgress = null,
//       onDone = null,
//       onError = null,
//     } = {},
//   ) => {
//     if (!jobId) {
//       onError && onError(new Error("jobId 없음"));
//       return;
//     }
//     if (jobPollRef.current) {
//       clearInterval(jobPollRef.current);
//       jobPollRef.current = null;
//     }

//     const start = Date.now();
//     jobPollRef.current = setInterval(async () => {
//       try {
//         if (Date.now() - start > timeoutMs) {
//           clearInterval(jobPollRef.current);
//           jobPollRef.current = null;
//           onError && onError(new Error("폴링 타임아웃"));
//           return;
//         }

//         const st = await getJobStatus(jobId).catch((e) => {
//           throw e;
//         });
//         onProgress && onProgress(st);

//         if (!st) return;

//         if (st.status === "error") {
//           clearInterval(jobPollRef.current);
//           jobPollRef.current = null;
//           onError && onError(new Error(st.error || "job error"));
//         } else if (st.status === "not_found") {
//           clearInterval(jobPollRef.current);
//           jobPollRef.current = null;
//           onError && onError(new Error("job not_found"));
//         } else if (st.status === "done" && st.case_id) {
//           clearInterval(jobPollRef.current);
//           jobPollRef.current = null;
//           setCurrentCaseId(st.case_id);
//           try {
//             const bundle = await getConversationBundle(st.case_id);
//             onDone && onDone(bundle, st.case_id);
//           } catch (err) {
//             onError && onError(err);
//           }
//         }
//         // running이면 그냥 대기
//       } catch (err) {
//         console.warn("job 폴링 실패:", err);
//       }
//     }, intervalMs);
//   };

//   /* --------- startSimulation: 초기 실행 (agent_mode: "off") --------- */
//   const startSimulation = async () => {
//     if (!selectedScenario || !selectedCharacter) {
//       addSystem("시나리오와 캐릭터를 먼저 선택해주세요.");
//       return;
//     }
//     setAgentPreviewShown(false);
//     setHasInitialRun(true);
//     setAgentRunning(false);
//     // setAgentPreviewShown(false);

//     // if (hasAgentRun || agentRunning) return;
//     // // 최초 실행 표시 (한 번만 실행되게 함)
//     // setHasInitialRun(true);
//     // setAgentRunning(false);

//     // 기존 정리
//     if (simIntervalRef.current) {
//       clearInterval(simIntervalRef.current);
//       simIntervalRef.current = null;
//     }
//     if (jobPollRef.current) {
//       clearInterval(jobPollRef.current);
//       jobPollRef.current = null;
//     }

//     setSimulationState("PREPARE");
//     setMessages([]);
//     setProgress(0);
//     setSessionResult(null);
//     setCurrentCaseId(null);
//     lastTurnRef.current = -1;
//     setPendingAgentDecision(false);
//     setShowReportPrompt(false);

//     addSystem(
//       `오케스트레이터 시뮬레이션 시작: ${selectedScenario.name} / ${selectedCharacter.name}`,
//     );

//     try {
//         // 📌 React 오케스트레이터로 바로 실행
//       const res = await runReactSimulation({
//         victim_id: selectedCharacter.id,
//         offender_id: selectedScenario.id,
//         use_tavily: false,      // 필요시 토글
//         max_turns: 15,          // 서버 기본과 맞추기
//         round_limit: 3,         // 2~5로 서버에서 클램프
//         round_no: 1
//       });
//       if (!res || !res.case_id) {
//         addSystem("시뮬레이션 실패: case_id를 받지 못했습니다.");
//         setSimulationState("IDLE");
//         return;
//       }
//       // case_id로 번들 로드
//       setCurrentCaseId(res.case_id);
//       const bundle = await getConversationBundle(res.case_id);
//       showConversationBundle(bundle);
      
//     } catch (err) {
//       console.error("시뮬레이션 실행 실패:", err);
//       addSystem("시뮬레이션 실행 실패 (콘솔 로그 확인).");
//       setSimulationState("IDLE");
//     }
//   };

//   /* --------- declineAgentRun: '아니요' 처리 (추가 실행 없음) --------- */
//   const declineAgentRun = () => {
//     setPendingAgentDecision(false);
//     setShowReportPrompt(true);
//     addSystem("에이전트 사용을 건너뜁니다. 리포트를 확인할 수 있습니다.");
//     // hasInitialRun remains true; no further runs allowed unless resetToSelection()
//   };

//   /* --------- startAgentRun: '예' 처리 (append 재생, 에이전트 한번만) --------- */
//   // 기존 startAgentRun 함수 전체를 아래로 교체하세요
//   const startAgentRun = async () => {
//     if (!currentCaseId) {
//       addSystem(
//         "case_id가 없습니다. 초기 시뮬레이션이 정상적으로 완료되었는지 확인하세요.",
//       );
//       return;
//     }
//     if (hasAgentRun || agentRunning) return;

//     setPendingAgentDecision(false);
//     setSimulationState("PREPARE");
//     setAgentRunning(true);
//     addSystem(
//       `에이전트 시뮬레이션을 시작합니다... (verbose=${agentVerbose ? "on" : "off"})`,
//     );

//     try {
//       // 1) 비동기 실행 kick
//       const kick = await runAgentForCaseAsync(currentCaseId, {
//         verbose: agentVerbose,
//         timeout: 120000,
//       });
//       if (!kick || !kick.job_id) {
//         addSystem("에이전트 실행 실패: job_id를 받지 못했습니다.");
//         setAgentRunning(false);
//         setSimulationState("IDLE");
//         return;
//       }

//       // 2) /agent/job/{id} 폴링
//       const jobId = kick.job_id;
//       const start = Date.now();
//       const POLL_INTERVAL = 1200;
//       const POLL_TIMEOUT = 180000; // 3분

//       const poll = async () => {
//         // 타임아웃
//         if (Date.now() - start > POLL_TIMEOUT)
//           throw new Error("에이전트 폴링 타임아웃");

//         const st = await getAgentJobStatus(jobId);
//         if (!st) return null;

//         // ✅ result.preview 우선, 없으면 st.preview (서버 래핑 차이 흡수)
//         const preview = st?.result?.preview ?? st?.preview ?? null;
//         if (preview && !agentPreviewShown) {
//           addSystem(
//             [
//               "🔎 에이전트 사전 판정(미리보기)",
//               `- 피싱 여부: ${preview.phishing ? "성공(공격자 우세)" : "실패(피해자 우세)"}`,
//               Array.isArray(preview.reasons) && preview.reasons.length
//                 ? `- 이유: ${preview.reasons.slice(0, 3).join(" / ")}`
//                 : "",
//               preview.guidance?.title
//                 ? `- 지침: ${preview.guidance.title}`
//                 : "",
//             ]
//               .filter(Boolean)
//               .join("\n"),
//           );
//           setSessionResult((prev) => ({ ...(prev || {}), preview }));
//           setAgentPreviewShown(true);
//         }

//         if (st.status === "error")
//           throw new Error(st.error || "agent job error");
//         if (st.status === "not_found") throw new Error("agent job not_found");
//         if (st.status === "running") return null;

//         // done
//         return st.result || st; // 라우터 구현에 따라 result 랩핑/직접일 수 있음
//       };

//       let result = null;
//       while (true) {
//         const r = await poll();
//         if (r) {
//           result = r;
//           break;
//         }
//         await new Promise((res) => setTimeout(res, POLL_INTERVAL));
//       }

//       // 3) 결과 처리: case_id로 번들 가져오기
//       const cid = result.case_id || currentCaseId;
//       setCurrentCaseId(cid);
//       const bundle = await getConversationBundle(cid);

//       setDefaultCaseData(bundle);

//       // personalized가 번들에 없으면(백엔드 구현에 따라),
//       // 필요 시 별도 조회 시도 (엔드포인트가 있을 때만)
//       let personalized =
//         bundle.personalized || bundle.personalized_preventions || null;
//       if (!personalized) {
//         try {
//           const pj = await getPersonalizedForCase(cid);
//           if (pj) personalized = pj;
//         } catch (_) {}
//       }

//       // 세션 상태 업데이트
//       const agentOnlyLogs = filterLogsByAgentFlag(bundle.logs || [], {
//         forAgent: true,
//       });
//       setSessionResult((prev) => ({
//         ...(prev || {}),
//         phishing: bundle.phishing ?? prev?.phishing ?? null,
//         isPhishing: bundle.phishing ?? prev?.isPhishing ?? null,
//         evidence: bundle.evidence ?? prev?.evidence ?? null,
//         totalTurns: bundle.total_turns ?? prev?.totalTurns ?? null,
//         agentUsed: true,
//         agentLogs: agentOnlyLogs,
//         personalized, // 리포트에서 쓰세요
//       }));

//       // 4) 에이전트 로그만 append 재생
//       if (!agentOnlyLogs.length) {
//         addSystem("에이전트 전용 로그(use_agent=true)가 없습니다.");
//         setHasAgentRun(true);
//         setAgentRunning(false);
//         setShowReportPrompt(true);
//         return;
//       }

//       playLogs(agentOnlyLogs, { append: true, speed: 1500 }, () => {
//         setHasAgentRun(true);
//         setAgentRunning(false);
//         setShowReportPrompt(true);
//         addSystem(
//           "에이전트 대화 재생이 완료되었습니다. 리포트를 확인할 수 있습니다.",
//         );
//       });
//     } catch (err) {
//       console.error("에이전트 실행 실패:", err);
//       addSystem(`에이전트 실행 실패: ${err.message || String(err)}`);
//       setAgentRunning(false);
//       setSimulationState("IDLE");
//     }
//   };

//   /* --------- resetToSelection: 모든 플래그 초기화 --------- */
//   const resetToSelection = () => {
//     setSelectedScenario(null);
//     setSelectedCharacter(null);
//     setMessages([]);
//     setSessionResult(null);
//     setProgress(0);
//     setSimulationState("IDLE");
//     // setPendingAgentDecision(false);
//     // setShowReportPrompt(false);

//     // setHasInitialRun(false);
//     // setHasAgentRun(false);
//     // setAgentRunning(false);

//     // setCurrentCaseId(null);
//     setCurrentPage("simulator");

//     // if (simIntervalRef.current) {
//     //   clearInterval(simIntervalRef.current);
//     //   simIntervalRef.current = null;
//     // }
//     // if (jobPollRef.current) {
//     //   clearInterval(jobPollRef.current);
//     //   jobPollRef.current = null;
//     // }
//     // lastTurnRef.current = -1;
//   };

//    /* --------- onBack 핸들러 추가 --------- */
//   const handleBack = () => {
//     setCurrentPage("landing");
//   };

//   // cleanup on unmount
//   useEffect(() => {
//     return () => {
//       if (simIntervalRef.current) {
//         clearInterval(simIntervalRef.current);
//         simIntervalRef.current = null;
//       }
//       if (jobPollRef.current) {
//         clearInterval(jobPollRef.current);
//         jobPollRef.current = null;
//       }
//     };
//   }, []);

//   /* --------- pageProps 전달 --------- */
//   const pageProps = {
//     COLORS,
//     apiRoot: API_ROOT,     // ✅ 추가
//     onBack: handleBack,    // ✅ 추가
//     setCurrentPage,
//     selectedScenario,
//     setSelectedScenario,
//     selectedCharacter,
//     setSelectedCharacter,
//     simulationState,
//     setSimulationState,
//     messages,
//     addSystem,
//     addAnalysis,
//     addChat,
//     sessionResult,
//     resetToSelection,
//     startSimulation,
//     startAgentRun,
//     declineAgentRun,
//     scenarios,
//     characters,
//     scrollContainerRef,
//     defaultCaseData,
//     dataLoading,
//     dataError,
//     currentCaseId,
//     pendingAgentDecision,
//     showReportPrompt,
//     hasInitialRun,
//     hasAgentRun,
//     agentRunning,
//     progress,
//     setProgress,
//     setShowReportPrompt,
//     agentVerbose, // NEW
//     setAgentVerbose, // NEW
//     victimImageUrl: selectedCharacter
//       ? getVictimImage(selectedCharacter.photo_path)
//       : null,
//   };

//   return (
//     <div className="font-sans">
//       {currentPage === "landing" && (
//         <LandingPage setCurrentPage={setCurrentPage} />
//       )}
//       {currentPage === "simulator" && <SimulatorPage {...pageProps} />}
//       {currentPage === "report" && (
//         <ReportPage {...pageProps} defaultCaseData={defaultCaseData} />
//       )}
//     </div>
//   );
// };

// src/App.jsx
import { useEffect, useLayoutEffect, useRef, useState, useCallback} from "react";
import LandingPage from "./LandingPage";
import SimulatorPage from "./SimulatorPage";
import ReportPage from "./ReportPage";


/* ================== 색상 토큰 ================== */
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

/* ================== MOCK MODE (더미 JSONL 주입) ================== */
const MOCK_MODE = true;

/* 유틸: is_convinced(1~10) → 10~100% 로 정규화 */
function normalizeConvincedToPct(v) {
  const n = Math.max(1, Math.min(10, Number(v) || 0));
  return n * 10; // 1->10%, 10->100%
}

// public의 JSONL을 줄단위로 읽기
async function loadJsonlFromPublic(path) {
  const res = await fetch(path, { cache: "no-store" });
  if (!res.ok) throw new Error(`JSONL 로드 실패: ${res.status} ${res.statusText}`);
  const text = await res.text();
  return text
    .split(/\r?\n/)
    .filter(Boolean)
    .map((line) => JSON.parse(line));
}

// JSONL → 프론트가 기대하는 번들 스키마로 변환
function jsonlToConversationBundle(rows) {
  const case_id = "dummy-case-1";
  if (!Array.isArray(rows) || rows.length === 0) {
    return { case_id, logs: [], total_turns: 0 };
  }
  const t0 = Date.now();
  const logs = rows.map((r, i) => {
    const role = (r.role || "").toLowerCase(); // "offender" | "victim" | "spinner_message" 등
    const textFromRow = typeof r.text === "string" ? r.text : "";
    const jr = r.json_reply || {};
    const vThoughts = typeof jr.thoughts === "string" ? jr.thoughts.trim() : "";
    const vDialogue = typeof jr.dialogue === "string" ? jr.dialogue.trim() : "";

    const content =
      role === "victim"
        ? [vThoughts, vDialogue].filter(Boolean).join("\n")
        : textFromRow;

    const isConvRaw = r.is_convinced; // 1~10
    const isConvPct = isConvRaw == null ? null : normalizeConvincedToPct(isConvRaw);

    return {
      run: r.run_no ?? 1,
      turn_index: r.turn ?? i,
      role,
      content,
      created_kst: new Date(t0 + i * 700).toISOString(),
      offender_name: "사칭 콜센터",
      victim_name: "피해자",
      use_agent: (r.run_no ?? 1) !== 1,
      guidance_type: null,
      guideline: null,
      thoughts: vThoughts || null,
      is_convinced: isConvRaw ?? null,      // 원본(1~10)
      convinced_pct: isConvPct,             // 정규화(10~100)
    };
  });

  // 정렬
  logs.sort((a, b) => {
    const ra = (a.run ?? 0) - (b.run ?? 0);
    if (ra !== 0) return ra;
    const ta = (a.turn_index ?? 0) - (b.turn_index ?? 0);
    if (ta !== 0) return ta;
    return new Date(a.created_kst) - new Date(b.created_kst);
  });

  const total_turns = Math.max(...logs.map((x) => x.turn_index ?? 0), 0) + 1;

  return {
    case_id,
    scenario: {
      methods_used: [],
      last_analysis: {
        outcome: "inconclusive",
        reasons: [],
        guidance: { type: null, title: null, category: null },
        phishing: null,
      },
    },
    offender: { id: 1, name: "사칭 콜센터", type: "더미", is_active: true },
    victim: {
      id: 1,
      name: "피해자",
      is_active: true,
      photo_path: "/static/images/victims/1.png",
    },
    logs,
    total_turns,
    phishing: null,
    evidence: null,
  };
}

// JSONL 캐시
let __dummyBundleCache = null;
async function getDummyBundle() {
  if (__dummyBundleCache) return __dummyBundleCache;
  const rows = await loadJsonlFromPublic("/dummy/sim_convo_rounds1_2_full.jsonl");
  __dummyBundleCache = jsonlToConversationBundle(rows);
  return __dummyBundleCache;
}

/* ================== 공통 fetch 유틸 ================== */
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
    if (err.name === "AbortError") throw new Error("요청 타임아웃 또는 취소됨");
    throw err;
  } finally {
    clearTimeout(id);
  }
}

/* ================== API 헬퍼 ================== */
async function runReactSimulation(body) {
  if (MOCK_MODE) {
    return { case_id: (await getDummyBundle()).case_id };
  }
  return fetchWithTimeout(`${API_ROOT}/react-agent/simulation`, {
    method: "POST",
    body,
    timeout: 600000,
  });
}
async function getOffenders() { return fetchWithTimeout(`${API_ROOT}/offenders/`); }
async function getVictims() { return fetchWithTimeout(`${API_ROOT}/victims/`); }
async function getConversationBundle(caseId) {
  if (MOCK_MODE) return await getDummyBundle();
  return fetchWithTimeout(`${API_ROOT}/conversations/${encodeURIComponent(caseId)}`);
}
async function runConversationAsync(offenderId, victimId, payload = {}) {
  return fetchWithTimeout(
    `${API_ROOT}/conversations/run_async/${encodeURIComponent(offenderId)}/${encodeURIComponent(victimId)}`,
    { method: "POST", body: payload, timeout: 300000 },
  );
}
async function getJobStatus(jobId) {
  return fetchWithTimeout(`${API_ROOT}/conversations/job/${encodeURIComponent(jobId)}`, { timeout: 15000 });
}
async function runAgentForCase(caseId, payload = {}, { verbose = false } = {}) {
  return fetchWithTimeout(
    `${API_ROOT}/agent/run/${encodeURIComponent(caseId)}?verbose=${verbose ? "true" : "false"}`,
    { method: "POST", body: payload, timeout: 120000 },
  );
}
async function runAgentForCaseAsync(caseId, { verbose = false, timeout = 1200000 } = {}) {
  const url = `${API_ROOT}/agent/run_async/${encodeURIComponent(caseId)}?verbose=${verbose ? "true" : "false"}`;
  return fetchWithTimeout(url, { method: "POST", timeout });
}
async function getAgentJobStatus(jobId) {
  return fetchWithTimeout(`${API_ROOT}/agent/job/${encodeURIComponent(jobId)}`, { timeout: 300000 });
}
async function getPersonalizedForCase(caseId) {
  return fetchWithTimeout(`${API_ROOT}/personalized/by-case/${encodeURIComponent(caseId)}`, { timeout: 200000 });
}

// ==== use_agent 판별 및 로그 필터 유틸 ====
function isUseAgentTrue(log) {
  if (!log) return false;
  const v = log?.use_agent ?? log?.useAgent ?? log?.use_agent_flag ?? log?.use_agent_value;
  if (v === true || v === "true") return true;
  if (v === 1 || v === "1") return true;
  return false;
}
function filterLogsByAgentFlag(logs = [], { forAgent = false } = {}) {
  if (!Array.isArray(logs)) return [];
  return forAgent ? logs.filter((l) => isUseAgentTrue(l)) : logs.filter((l) => !isUseAgentTrue(l));
}

// === 요약 박스 컴포넌트 (미리보기 preview를 그대로 표시) ======================
function mapOutcomeToKorean(outcome) {
  switch (outcome) {
    case "attacker_fail": return "공격자 실패";
    case "attacker_success": return "공격자 성공";
    case "inconclusive": return "판단 불가";
    default: return outcome || "-";
  }
}
function toArrayReasons(reason, reasons) {
  if (Array.isArray(reasons) && reasons.length) return reasons;
  if (Array.isArray(reason)) return reason;
  if (typeof reason === "string" && reason.trim()) return [reason];
  return [];
}
function InlinePhishingSummaryBox({ preview }) {
  if (!preview) return null;
  const outcome = mapOutcomeToKorean(preview.outcome);
  const reasons = toArrayReasons(preview.reason, preview.reasons);
  const guidanceTitle = preview?.guidance?.title || "-";

  return (
    <div className="max-w-3xl mx-auto my-4">
      <div className="rounded-2xl border border-gray-200 bg-white/60 shadow-sm backdrop-blur p-4 md:p-5">
        <h3 className="text-base md:text-lg font-semibold mb-3">
          요약(대화 1 분석)
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <div className="text-xs text-gray-500 mb-1">피싱여부</div>
            <div className="text-sm md:text-base text-gray-900">{outcome}</div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">적용 지침</div>
            <div className="text-sm md:text-base text-gray-900 line-clamp-2">
              {guidanceTitle}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">피싱여부 근거</div>
            {reasons.length === 0 ? (
              <div className="text-sm text-gray-500">-</div>
            ) : (
              <ul className="list-disc pl-5 space-y-1">
                {reasons.map((r, i) => (
                  <li key={i} className="text-sm leading-6">
                    {r}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    </div>
  );
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
  const [simulationState, setSimulationState] = useState("IDLE"); // IDLE, PREPARE, RUNNING, INTERMISSION
  const [messages, setMessages] = useState([]);
  const [sessionResult, setSessionResult] = useState(null);
  const [progress, setProgress] = useState(0);

  // modal / decision flags
  const [pendingAgentDecision, setPendingAgentDecision] = useState(false);
  const [showReportPrompt, setShowReportPrompt] = useState(false);

  // run control flags
  const [hasInitialRun, setHasInitialRun] = useState(false);
  const [hasAgentRun, setHasAgentRun] = useState(false);
  const [agentRunning, setAgentRunning] = useState(false);

  // NEW: spinner(전략회의) 노출 시간 (기본 5초) + 표시 텍스트
  const [spinnerDelayMs, setSpinnerDelayMs] = useState(5000);
  const [intermissionText, setIntermissionText] = useState(""); // 중앙 모달용 텍스트

  // refs
  const scrollContainerRef = useRef(null);
  const jobPollRef = useRef(null);
  const simIntervalRef = useRef(null);
  const lastTurnRef = useRef(-1);

  // UI loading/error
  const [dataLoading, setDataLoading] = useState(true);
  const [dataError, setDataError] = useState(null);
  const [currentCaseId, setCurrentCaseId] = useState(null);

  const [agentPreviewShown, setAgentPreviewShown] = useState(false);

  // NEW: verbose 토글
  const [agentVerbose, setAgentVerbose] = useState(false);

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

  /* 메시지 추가 유틸 */
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
  // 변형: addChat에 meta(예: convincedPct) 파라미터 추가
  const addChat = (
    sender,
    content,
    timestamp = null,
    senderLabel = null,
    side = null,
    meta = null,
  ) =>
    setMessages((prev) => [
      ...prev,
      {
        type: "chat",
        sender,
        senderLabel: senderLabel ?? sender,
        senderName: senderLabel ?? sender,
        side: side ?? (sender === "offender" ? "left" : "right"),
        content,
        timestamp: timestamp ?? new Date().toLocaleTimeString(),
        // NEW: 이름 옆 바 표현을 위해 퍼센트 보관
        convincedPct: meta?.convincedPct ?? null,
      },
    ]);

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

  /**
   * 대화 로그 재생
   * - run 1 → 2 전환 구간에서 중앙 모달(전략회의중) 표시 후 spinnerDelayMs 만큼 대기
   * - JSONL의 spinner_message 텍스트가 있으면 사용, 없으면 기본 "피싱범이 전략회의 중…"
   * - 각 로그의 is_convinced(1~10)을 convincedPct(10~100)로 변환하여 메시지 메타로 전달
   */
  const playLogs = useCallback(
    (
      logs = [],
      {
        append = false,
        speed = 1500,
        spinnerText: spinnerTextArg = null,
        spinnerDelayOverride = null, // 개별 호출 시 오버라이드
      } = {},
      onComplete = null,
    ) => {
      if (!Array.isArray(logs) || logs.length === 0) {
        onComplete && onComplete();
        return;
      }

      // spinner_message 추출(텍스트만 참조), 표시 자체는 중앙 모달로
      const spinnerLog = logs.find((l) => (l.role || "").toLowerCase() === "spinner_message");
      const spinnerTextRaw =
        spinnerTextArg ||
        (spinnerLog?.content && String(spinnerLog.content).trim()) ||
        null;
      const spinnerTextDefault = "피싱범이 전략회의 중…";
      const spinnerText = spinnerTextRaw || spinnerTextDefault;

      // 실제 출력용 로그에서는 spinner_message 제거
      const purifiedLogs = logs.filter((l) => (l.role || "").toLowerCase() !== "spinner_message");

      if (!append) setMessages([]);
      setProgress((p) => (append ? p : 0));

      setSimulationState("PREPARE");

      if (simIntervalRef.current) {
        clearTimeout(simIntervalRef.current);
        simIntervalRef.current = null;
      }

      const total = purifiedLogs.length;
      let idx = 0;
      let prevRun = purifiedLogs[0]?.run ?? 1;

      const INITIAL_DELAY = 1500; // 첫 메시지 직전 약간의 로딩
      const INTERMISSION_DELAY = spinnerDelayOverride ?? spinnerDelayMs; // 중앙 모달 대기시간

      const pushOne = (log) => {
        const role = (log.role || "").toLowerCase();
        const offenderLabel =
          log.offender_name ||
          (selectedScenario ? `피싱범${selectedScenario.id}` : "피싱범");
        const victimLabel =
          log.victim_name ||
          (selectedCharacter ? `피해자${selectedCharacter.id}` : "피해자");
        const displayLabel = role === "offender" ? offenderLabel : victimLabel;
        const side = role === "offender" ? "left" : "right";

        const content = String(log.content ?? "");

        const ts =
          log.created_kst && typeof log.created_kst === "string"
            ? new Date(log.created_kst).toLocaleTimeString()
            : log.created_kst ?? new Date().toLocaleTimeString();

        // NEW: 메시지에 설득도 퍼센트 주입
        const meta = {
          convincedPct:
            log?.convinced_pct ??
            (log?.is_convinced != null ? normalizeConvincedToPct(log.is_convinced) : null),
        };

        if (role === "analysis" || role === "system" || log.label === "analysis") {
          addAnalysis(content);
        } else {
          addChat(role || "offender", content, ts, displayLabel, side, meta);
        }
      };

      const step = () => {
        if (idx >= total) {
          simIntervalRef.current = null;
          setSimulationState("IDLE");
          onComplete && onComplete();
          return;
        }

        const log = purifiedLogs[idx];
        const currRun = log.run ?? prevRun;

        // run 1 -> 2 전환: 중앙 모달(전략회의) 표시 후 지연
        if (prevRun === 1 && currRun === 2) {
          setSimulationState("INTERMISSION");
          setIntermissionText(spinnerText);
          simIntervalRef.current = setTimeout(() => {
            setIntermissionText("");
            setSimulationState("RUNNING");
            pushOne(log);

            if (!append) {
              setProgress(((idx + 1) / total) * 100);
            } else {
              setProgress((p) => Math.min(100, p + 100 / Math.max(1, total)));
            }

            prevRun = currRun;
            idx += 1;
            step();
          }, INTERMISSION_DELAY);
          return;
        }

        const delay = idx === 0 ? INITIAL_DELAY : speed;

        simIntervalRef.current = setTimeout(() => {
          setSimulationState("RUNNING");
          pushOne(log);

          if (!append) {
            setProgress(((idx + 1) / total) * 100);
          } else {
            setProgress((p) => Math.min(100, p + 100 / Math.max(1, total)));
          }

          prevRun = currRun;
          idx += 1;
          step();
        }, delay);
      };

      step();
    },
    [
      addAnalysis,
      addChat,
      setMessages,
      setProgress,
      setSimulationState,
      selectedScenario,
      selectedCharacter,
      spinnerDelayMs,
    ],
  );

  const showConversationBundle = useCallback((bundle) => {
    setDefaultCaseData(bundle);
    setSessionResult((prev) => ({
      ...(prev || {}),
      phishing: bundle.phishing ?? prev?.phishing ?? null,
      isPhishing: bundle.phishing ?? prev?.isPhishing ?? null,
      evidence: bundle.evidence ?? prev?.evidence ?? null,
      totalTurns: bundle.total_turns ?? prev?.totalTurns ?? null,
    }));

    const logs = (bundle.logs || []).slice().sort((a, b) => {
      const ra = (a.run ?? 0) - (b.run ?? 0);
      if (ra !== 0) return ra;
      const ta = (a.turn_index ?? 0) - (b.turn_index ?? 0);
      if (ta !== 0) return ta;
      const da = new Date(a.created_at || a.created_kst || 0) - new Date(b.created_at || b.created_kst || 0);
      return da;
    });

    if (!logs.length) {
      addSystem("표시할 대화 로그가 없습니다.");
      setShowReportPrompt(true);
      setSimulationState("IDLE");
      return;
    }

    // 전체 로그 재생 (중앙 모달은 playLogs 내부에서 처리)
    playLogs(
      logs,
      {
        append: false,
        speed: 700,
        // spinnerDelayOverride: 7000, // 필요시 호출부에서 덮어쓰기
      },
      () => {
        setShowReportPrompt(true);
        addSystem("대화 재생이 완료되었습니다. 리포트를 확인할 수 있습니다.");
      },
    );
  }, [addSystem, playLogs, setShowReportPrompt, setSimulationState]);

  const showExistingCase = useCallback(async (caseId) => {
    try {
      const bundle = await getConversationBundle(caseId);
      setCurrentCaseId(caseId);
      showConversationBundle(bundle);
    } catch (e) {
      addSystem(`대화 불러오기 실패: ${e.message}`);
    }
  }, [addSystem, showConversationBundle]);

  /* job 폴링 */
  const startJobPollingForKick = (
    jobId,
    {
      intervalMs = 1200,
      timeoutMs = 120000,
      onProgress = null,
      onDone = null,
      onError = null,
    } = {},
  ) => {
    if (!jobId) {
      onError && onError(new Error("jobId 없음"));
      return;
    }
    if (jobPollRef.current) {
      clearInterval(jobPollRef.current);
      jobPollRef.current = null;
    }

    const start = Date.now();
    jobPollRef.current = setInterval(async () => {
      try {
        if (Date.now() - start > timeoutMs) {
          clearInterval(jobPollRef.current);
          jobPollRef.current = null;
          onError && onError(new Error("폴링 타임아웃"));
          return;
        }

        const st = await getJobStatus(jobId).catch((e) => { throw e; });
        onProgress && onProgress(st);
        if (!st) return;

        if (st.status === "error") {
          clearInterval(jobPollRef.current);
          jobPollRef.current = null;
          onError && onError(new Error(st.error || "job error"));
        } else if (st.status === "not_found") {
          clearInterval(jobPollRef.current);
          jobPollRef.current = null;
          onError && onError(new Error("job not_found"));
        } else if (st.status === "done" && st.case_id) {
          clearInterval(jobPollRef.current);
          jobPollRef.current = null;
          setCurrentCaseId(st.case_id);
          try {
            const bundle = await getConversationBundle(st.case_id);
            onDone && onDone(bundle, st.case_id);
          } catch (err) {
            onError && onError(err);
          }
        }
      } catch (err) {
        console.warn("job 폴링 실패:", err);
      }
    }, intervalMs);
  };

  /* --------- startSimulation --------- */
  const startSimulation = async () => {
    if (!selectedScenario || !selectedCharacter) {
      addSystem("시나리오와 캐릭터를 먼저 선택해주세요.");
      return;
    }
    setAgentPreviewShown(false);
    setHasInitialRun(true);
    setAgentRunning(false);

    if (simIntervalRef.current) {
      clearInterval(simIntervalRef.current);
      simIntervalRef.current = null;
    }
    if (jobPollRef.current) {
      clearInterval(jobPollRef.current);
      jobPollRef.current = null;
    }

    setSimulationState("PREPARE");
    setIntermissionText(""); // 초기화
    setMessages([]);
    setProgress(0);
    setSessionResult(null);
    setCurrentCaseId(null);
    lastTurnRef.current = -1;
    setPendingAgentDecision(false);
    setShowReportPrompt(false);

    addSystem(
      `오케스트레이터 시뮬레이션 시작: ${selectedScenario.name} / ${selectedCharacter.name}`,
    );

    try {
      const res = await runReactSimulation({
        victim_id: selectedCharacter.id,
        offender_id: selectedScenario.id,
        use_tavily: false,
        max_turns: 15,
        round_limit: 3,
        round_no: 1
      });
      if (!res || !res.case_id) {
        addSystem("시뮬레이션 실패: case_id를 받지 못했습니다.");
        setSimulationState("IDLE");
        return;
      }
      setCurrentCaseId(res.case_id);
      const bundle = await getConversationBundle(res.case_id);
      showConversationBundle(bundle);
    } catch (err) {
      console.error("시뮬레이션 실행 실패:", err);
      addSystem("시뮬레이션 실행 실패 (콘솔 로그 확인).");
      setSimulationState("IDLE");
    }
  };

  /* --------- declineAgentRun --------- */
  const declineAgentRun = () => {
    setPendingAgentDecision(false);
    setShowReportPrompt(true);
    addSystem("에이전트 사용을 건너뜁니다. 리포트를 확인할 수 있습니다.");
  };

  /* --------- startAgentRun --------- */
  const startAgentRun = async () => {
    if (!currentCaseId) {
      addSystem("case_id가 없습니다. 초기 시뮬레이션이 정상적으로 완료되었는지 확인하세요.");
      return;
    }
    if (hasAgentRun || agentRunning) return;

    setPendingAgentDecision(false);
    setSimulationState("PREPARE");
    setAgentRunning(true);
    addSystem(`에이전트 시뮬레이션을 시작합니다... (verbose=${agentVerbose ? "on" : "off"})`);

    try {
      const kick = await runAgentForCaseAsync(currentCaseId, { verbose: agentVerbose, timeout: 120000 });
      if (!kick || !kick.job_id) {
        addSystem("에이전트 실행 실패: job_id를 받지 못했습니다.");
        setAgentRunning(false);
        setSimulationState("IDLE");
        return;
      }

      const jobId = kick.job_id;
      const start = Date.now();
      const POLL_INTERVAL = 1200;
      const POLL_TIMEOUT = 180000;

      const poll = async () => {
        if (Date.now() - start > POLL_TIMEOUT) throw new Error("에이전트 폴링 타임아웃");
        const st = await getAgentJobStatus(jobId);
        if (!st) return null;

        const preview = st?.result?.preview ?? st?.preview ?? null;
        if (preview && !agentPreviewShown) {
          addSystem(
            [
              "🔎 에이전트 사전 판정(미리보기)",
              `- 피싱 여부: ${preview.phishing ? "성공(공격자 우세)" : "실패(피해자 우세)"}`,
              Array.isArray(preview.reasons) && preview.reasons.length
                ? `- 이유: ${preview.reasons.slice(0, 3).join(" / ")}`
                : "",
              preview.guidance?.title ? `- 지침: ${preview.guidance.title}` : "",
            ].filter(Boolean).join("\n"),
          );
          setSessionResult((prev) => ({ ...(prev || {}), preview }));
          setAgentPreviewShown(true);
        }

        if (st.status === "error") throw new Error(st.error || "agent job error");
        if (st.status === "not_found") throw new Error("agent job not_found");
        if (st.status === "running") return null;

        return st.result || st;
      };

      let result = null;
      while (true) {
        const r = await poll();
        if (r) { result = r; break; }
        await new Promise((res) => setTimeout(res, POLL_INTERVAL));
      }

      const cid = result.case_id || currentCaseId;
      setCurrentCaseId(cid);
      const bundle = await getConversationBundle(cid);

      setDefaultCaseData(bundle);

      let personalized = bundle.personalized || bundle.personalized_preventions || null;
      if (!personalized) {
        try {
          const pj = await getPersonalizedForCase(cid);
          if (pj) personalized = pj;
        } catch (_) {}
      }

      const agentOnlyLogs = filterLogsByAgentFlag(bundle.logs || [], { forAgent: true });
      setSessionResult((prev) => ({
        ...(prev || {}),
        phishing: bundle.phishing ?? prev?.phishing ?? null,
        isPhishing: bundle.phishing ?? prev?.isPhishing ?? null,
        evidence: bundle.evidence ?? prev?.evidence ?? null,
        totalTurns: bundle.total_turns ?? prev?.totalTurns ?? null,
        agentUsed: true,
        agentLogs: agentOnlyLogs,
        personalized,
      }));

      if (!agentOnlyLogs.length) {
        addSystem("에이전트 전용 로그(use_agent=true)가 없습니다.");
        setHasAgentRun(true);
        setAgentRunning(false);
        setShowReportPrompt(true);
        return;
      }

      playLogs(agentOnlyLogs, { append: true, speed: 1500 }, () => {
        setHasAgentRun(true);
        setAgentRunning(false);
        setShowReportPrompt(true);
        addSystem("에이전트 대화 재생이 완료되었습니다. 리포트를 확인할 수 있습니다.");
      });
    } catch (err) {
      console.error("에이전트 실행 실패:", err);
      addSystem(`에이전트 실행 실패: ${err.message || String(err)}`);
      setAgentRunning(false);
      setSimulationState("IDLE");
    }
  };

  /* --------- resetToSelection --------- */
  const resetToSelection = () => {
    setSelectedScenario(null);
    setSelectedCharacter(null);
    setMessages([]);
    setSessionResult(null);
    setProgress(0);
    setSimulationState("IDLE");
    setIntermissionText("");
    setCurrentPage("simulator");
  };

  const handleBack = () => {
    setCurrentPage("landing");
  };

  // cleanup on unmount
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
    };
  }, []);

  /* --------- pageProps 전달 --------- */
  const pageProps = {
    COLORS,
    mockMode: MOCK_MODE,
    apiRoot: API_ROOT,
    onBack: handleBack,
    setCurrentPage,
    selectedScenario,
    setSelectedScenario,
    selectedCharacter,
    setSelectedCharacter,
    simulationState,   // PREPARE / RUNNING / INTERMISSION / IDLE
    intermissionText,  // ← 중앙 모달에 노출할 텍스트 ("피싱범이 전략회의 중…")
    setSimulationState,
    messages,          // 각 message에 convincedPct 포함
    addSystem,
    addAnalysis,
    addChat,
    sessionResult,
    resetToSelection,
    startSimulation,
    startAgentRun,
    declineAgentRun,
    scenarios,
    characters,
    scrollContainerRef,
    defaultCaseData,
    dataLoading,
    dataError,
    currentCaseId,
    pendingAgentDecision,
    showReportPrompt,
    hasInitialRun,
    hasAgentRun,
    agentRunning,
    progress,
    setProgress,
    setShowReportPrompt,
    agentVerbose,
    setAgentVerbose,
    // 중앙 모달 시간 조절용
    spinnerDelayMs,
    setSpinnerDelayMs,
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
