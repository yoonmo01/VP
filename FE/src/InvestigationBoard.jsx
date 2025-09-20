// src/InvestigationBoard.jsx
import React from "react";

/*== 색상 토큰== */
const COLORS = {
  bg: "#1E1F22",
  panel: "#2B2D31",
  panelDark: "#1a1b1e",
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

// 샘플 데이터 (기존 코드 기능 테스트용)
const sampleInsights = {
  isPhishing: true,
  reason:
    "피해자가 문자로 받은 링크를 통해 앱을 설치하여 디지털 전근을 허용하였습니다. 이는 악성앱 설치에 해당하는 고위험 행위입니다.",
  weakness:
    "음성 스트리밍 앱을 받기 서비스 전화 및 설치는 큰 위험을 초래합니다. 한국 클럽 수 앱을 설치하지 전에는 반드시 공식 채널을 통해 검증 여부를 재검토하십시오.",
  riskScore: 85,
  riskLevel: "high",
};

const InvestigationBoard = ({ insights = sampleInsights }) => {
  if (!insights) return null;

  // 위험도 색상 구하기 (기존 코드 기능 유지)
  const getRiskColor = (score) => {
    if (score >= 75) return "#FF4D4F"; // 빨강
    if (score >= 50) return "#FAAD14"; // 주황
    return "#52C41A"; // 초록
  };

  const getRiskLevelText = (level) => {
    return `위험도: ${level}`;
  };

  return (
    <div
      className="h-full overflow-y-auto"
      style={{ backgroundColor: COLORS.panelDark, maxHeight: "100vh" }}
    >
      {/* 🔹 스크롤 영역: 루트 컨테이너에 overflow-y-auto + maxHeight: 100vh */}
      {/* 상단 헤더 - 피싱 판정 결과 */}
      <div className="p-4 border-b" style={{ borderColor: COLORS.border }}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div
              className="w-2 h-2 rounded-full"
              style={{ backgroundColor: "#FAAD14" }}
            />
            <h2 className="text-lg font-semibold" style={{ color: COLORS.text }}>
              피싱 판정 결과
            </h2>
          </div>
          <div className="ml-auto">
            {insights.isPhishing ? (
              <span
                className="px-3 py-1 rounded text-xs text-white"
                style={{ backgroundColor: "#FF4D4F" }}
              >
                피싱 성공
              </span>
            ) : (
              <span
                className="px-3 py-1 rounded text-xs text-white"
                style={{ backgroundColor: "#52C41A" }}
              >
                피싱 실패
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="p-6 space-y-6 overflow-y-auto">
        {/* 피싱 성공 근거 */}
        <div>
          <h3 className="text-lg font-semibold mb-3" style={{ color: COLORS.text }}>
            피싱 성공 근거
          </h3>
          <div className="p-4 rounded-lg" style={{ backgroundColor: COLORS.panel }}>
            <p className="text-sm leading-relaxed" style={{ color: COLORS.sub }}>
              {insights.reason}
            </p>
          </div>
        </div>

        {/* 개인화 예방법 */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <div
                className="w-2 h-2 rounded-full"
                style={{ backgroundColor: COLORS.blurple }}
              />
              <h3 className="text-lg font-semibold" style={{ color: COLORS.text }}>
                개인화 예방법
              </h3>
            </div>
            <span
              className="px-3 py-1 rounded text-xs text-white"
              style={{ backgroundColor: getRiskColor(insights.riskScore) }}
            >
              {getRiskLevelText(insights.riskLevel)}
            </span>
          </div>

          <div className="space-y-4">
            {/* 요약 */}
            <div>
              <h4 className="font-medium mb-2" style={{ color: COLORS.text }}>
                요약
              </h4>
              <p className="text-sm leading-relaxed" style={{ color: COLORS.sub }}>
                {insights.weakness}
              </p>
            </div>

            {/* 대화 위험도 - 프로그레스 바 */}
            <div>
              <h4 className="font-medium mb-3" style={{ color: COLORS.text }}>
                대화 위험도
              </h4>
              <div
                className="w-full h-4 rounded-full overflow-hidden mb-2"
                style={{ backgroundColor: COLORS.panel }}
              >
                <div
                  className="h-4 transition-all"
                  style={{
                    width: `${insights.riskScore}%`,
                    backgroundColor: getRiskColor(insights.riskScore),
                  }}
                />
              </div>
              <p
                className="text-sm font-medium"
                style={{ color: getRiskColor(insights.riskScore) }}
              >
                {insights.riskScore}% ({insights.riskLevel})
              </p>
            </div>

            {/* 상세 단계 (steps) */}
            <div>
              <h4 className="font-medium mb-2" style={{ color: COLORS.text }}>
                상세 단계 (steps)
              </h4>
              <ul className="space-y-2 text-sm" style={{ color: COLORS.sub }}>
                <li>• 정상 은행 공식 홈페이지나 앱스토어에서 제공받는 앱만 설치하세요.</li>
                <li>• 전화 문의 시에도 뜻 모를 대화 과정에서 웹사이트로 안내받은 링크로 접근하세요.</li>
                <li>• 추신한 링크는 클릭 전에 URL을 꼼꼼히 확인하고, 의심스럽다면 바로 사용하세요.</li>
                <li>• 뱅킹 서비스나 비밀번호 앱 설치 보안을 실용하지 마세요.</li>
                <li>• 앱을 이미 설치했으면 즉시 삭제하고, 모바일 보안 앱으로 정밀 검사하세요.</li>
              </ul>
            </div>

            {/* 핵심 팁 (tips) */}
            <div>
              <h4 className="font-medium mb-2" style={{ color: COLORS.text }}>
                핵심 팁 (tips)
              </h4>
              <ul className="space-y-2 text-sm" style={{ color: COLORS.sub }}>
                <li>• 공식 스토어에 있는 앱만 충정가 못했습니다.</li>
                <li>• 은행 서류부터만 안내는 링크나 공식 채널을 확인하세요.</li>
                <li>• 한국 클럽 및 업신원빈을 URL을 바로 감춘하세요.</li>
                <li>• 앱 설치 전 먼 검토 요청 내용을 꼭 확인하세요.</li>
                <li>• 의심되는 업무 즉시 삭제하고 바이럽스를 탐지하세요.</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default InvestigationBoard;



// import React from "react";

// const InvestigationBoard = ({ COLORS, insights }) => {
//   if (!insights) return null;

//   // 위험도 색상 구하기
//   const getRiskColor = (score) => {
//     if (score >= 75) return "#FF4D4F"; // 빨강
//     if (score >= 50) return "#FAAD14"; // 주황
//     return "#52C41A"; // 초록
//   };

//   return (
//     <div
//       className="h-full flex flex-col p-4 space-y-6 overflow-y-auto"
//       style={{
//         backgroundColor: COLORS.panelDark,
//         borderLeft: `1px solid ${COLORS.border}`,
//       }}
//     >
//       {/* 피싱 여부 */}
//       <div className="flex justify-center">
//         {insights.isPhishing ? (
//           <span className="px-6 py-2 rounded-full text-white font-semibold"
//             style={{ backgroundColor: "#FF4D4F" }}>
//             성공
//           </span>
//         ) : (
//           <span className="px-6 py-2 rounded-full text-white font-semibold"
//             style={{ backgroundColor: "#52C41A" }}>
//             실패
//           </span>
//         )}
//       </div>

//       {/* 판단 근거 */}
//       <div>
//         <h3 className="text-lg font-bold mb-2" style={{ color: COLORS.text }}>
//           판단 근거
//         </h3>
//         <p className="text-sm leading-relaxed" style={{ color: COLORS.sub }}>
//           {insights.reason}
//         </p>
//       </div>

//       {/* 피해자 취약점 */}
//       <div>
//         <h3 className="text-lg font-bold mb-2" style={{ color: COLORS.text }}>
//           피해자 취약점
//         </h3>
//         <p className="text-sm leading-relaxed" style={{ color: COLORS.sub }}>
//           {insights.weakness}
//         </p>
//       </div>

//       {/* 대화 위험도 */}
//       <div>
//         <h3 className="text-lg font-bold mb-3" style={{ color: COLORS.text }}>
//           대화 위험도
//         </h3>
//         <div className="w-full h-4 rounded-full overflow-hidden"
//           style={{ backgroundColor: COLORS.panel }}>
//           <div
//             className="h-4 transition-all"
//             style={{
//               width: `${insights.riskScore}%`,
//               backgroundColor: getRiskColor(insights.riskScore),
//             }}
//           />
//         </div>
//         <p className="mt-2 text-sm font-medium"
//           style={{ color: getRiskColor(insights.riskScore) }}>
//           {insights.riskScore}% ({insights.riskLevel})
//         </p>
//       </div>
//     </div>
//   );
// };

// export default InvestigationBoard;


// import { useMemo } from "react";
// import { Shield, AlertTriangle, StickyNote, Info } from "lucide-react";

// /** 0~100 위험도 → 초록→노랑→빨강 색상 보간 */
// function riskColor(value) {
//   const v = Math.max(0, Math.min(100, Number(value) || 0));
//   const lerp = (a, b, t) => Math.round(a + (b - a) * t);
//   let r, g, b;
//   if (v <= 50) {
//     const t = v / 50;
//     r = lerp(46, 241, t); g = lerp(204, 196, t); b = lerp(113, 15, t);
//   } else {
//     const t = (v - 50) / 50;
//     r = lerp(241, 231, t); g = lerp(196, 76, t); b = lerp(15, 60, t);
//   }
//   return `rgb(${r}, ${g}, ${b})`;
// }
// function riskBucketText(v) {
//   const n = Number(v) || 0;
//   if (n >= 70) return "높음";
//   if (n >= 40) return "보통";
//   return "낮음";
// }

// /** 성공=빨강, 실패=초록 타원형 라벨 */
// function Pill({ ok, THEME, label }) {
//   const bg = ok ? (THEME.success || "#57F287") : (THEME.danger || "#ED4245"); // ok=true=실패(초록), ok=false=성공(빨강)
//   const color = THEME.black || "#000";
//   return (
//     <span
//       className="inline-block px-6 py-2 rounded-full text-sm font-semibold tracking-wide"
//       style={{ backgroundColor: bg, color, minWidth: 96, textAlign: "center" }}
//     >
//       {label}
//     </span>
//   );
// }

// function Card({ THEME, title, icon, children }) {
//   const Icon = icon || Info;
//   return (
//     <section
//       className="rounded-2xl p-5 md:p-6"
//       style={{ backgroundColor: THEME.panel, border: `1px solid ${THEME.border}` }}
//     >
//       <h3
//         className="text-lg md:text-xl font-semibold mb-4 flex items-center gap-2"
//         style={{ color: THEME.text }}
//       >
//         <Icon size={22} className="opacity-90" /> {title}
//       </h3>
//       {children}
//     </section>
//   );
// }

// function InsightPanel({ THEME, data }) {
//   const {
//     phishing = { success: false, reason: "근거 정보가 없습니다." },
//     weakness = "취약점 정보가 없습니다.",
//     weaknessTags = [],
//     risk = { score: 25, notes: [] },
//   } = data || {};

//   const score = Math.max(0, Math.min(100, Number(risk.score) || 0));
//   const barColor = riskColor(score);
//   const bucket = riskBucketText(score);

//   return (
//     <div className="flex flex-col gap-5 md:gap-6">
//       <Card THEME={THEME} title="피싱 여부" icon={Shield}>
//         <div className="flex items-center justify-between gap-4">
//           <Pill
//             ok={!phishing.success}
//             THEME={THEME}
//             label={phishing.success ? "성공" : "실패"}
//           />
//         </div>
//         <div
//           className="mt-4 p-4 rounded-lg text-sm leading-relaxed"
//           style={{
//             backgroundColor: THEME.bg,
//             border: `1px solid ${THEME.border}`,
//             color: THEME.sub,
//           }}
//         >
//           <div
//             className="text-xs font-semibold uppercase tracking-wider mb-2"
//             style={{ color: THEME.text, opacity: 0.85 }}
//           >
//             판단 근거
//           </div>
//           <div className="pl-3 border-l-4" style={{ borderColor: THEME.blurple || THEME.border }}>
//             <p className="whitespace-pre-wrap">{phishing.reason}</p>
//           </div>
//         </div>
//       </Card>

//       <Card THEME={THEME} title="피해자의 취약점" icon={StickyNote}>
//         <div
//           className="p-4 rounded-lg text-sm leading-relaxed"
//           style={{
//             backgroundColor: THEME.bg,
//             border: `1px solid ${THEME.border}`,
//             color: THEME.sub,
//           }}
//         >
//           <div className="pl-3 border-l-4 mb-2" style={{ borderColor: THEME.border }}>
//             <p className="whitespace-pre-wrap">{weakness}</p>
//           </div>
//           {Array.isArray(weaknessTags) && weaknessTags.length > 0 && (
//             <div className="flex flex-wrap gap-2 mt-2">
//               {weaknessTags.map((t, i) => (
//                 <span
//                   key={i}
//                   className="px-3 py-1 rounded-full text-xs font-medium"
//                   style={{ backgroundColor: THEME.border, color: THEME.black }}
//                 >
//                   #{t}
//                 </span>
//               ))}
//             </div>
//           )}
//         </div>
//       </Card>

//       <Card THEME={THEME} title="대화 위험도" icon={AlertTriangle}>
//         <div className="space-y-3">
//           <div className="flex items-baseline justify-between">
//             <span className="text-sm" style={{ color: THEME.sub }}>
//               위험군: <span style={{ color: THEME.text }}>{bucket}</span>
//             </span>
//             <span className="text-sm font-semibold" style={{ color: THEME.text }}>
//               {score} / 100
//             </span>
//           </div>
//           <div
//             className="w-full h-3 rounded-full overflow-hidden"
//             style={{ backgroundColor: THEME.panelDark }}
//             aria-label="위험도 프로그레스바"
//             aria-valuemin={0}
//             aria-valuemax={100}
//             aria-valuenow={score}
//           >
//             <div
//               className="h-full"
//               style={{ width: `${score}%`, background: `linear-gradient(90deg, ${barColor}, ${barColor})` }}
//             />
//           </div>
//           {Array.isArray(risk.notes) && risk.notes.length > 0 && (
//             <ul className="list-disc pl-5 text-sm" style={{ color: THEME.sub }}>
//               {risk.notes.map((n, i) => (<li key={i}>{n}</li>))}
//             </ul>
//           )}
//         </div>
//       </Card>
//     </div>
//   );
// }

// /** 수사보드형 레이아웃: 좌(7) : 우(3), 각자 스크롤 */
// export default function InvestigationBoard({ COLORS, children, insights }) {
//   const THEME = useMemo(
//     () => ({
//       ...COLORS,
//       bg: "#030617",
//       panel: "#061329",
//       panelDark: "#04101f",
//       panelDarker: "#020812",
//       border: "#A8862A",
//       text: "#FFFFFF",
//       sub: "#BFB38A",
//       blurple: "#A8862A",
//       success: COLORS?.success ?? "#57F287",
//       warn: COLORS?.warn ?? "#FF4757",
//       white: "#FFFFFF",
//       black: "#000000",
//       danger: COLORS?.danger ?? "#ED4245",
//     }),
//     [COLORS]
//   );

//   return (
//     <div className="min-h-screen" style={{ backgroundColor: THEME.bg, color: THEME.text }}>
//       <div className="mx-auto p-4 md:p-6 lg:p-8">
//         <div className="grid gap-6" style={{ gridTemplateColumns: "minmax(0,7fr) minmax(0,3fr)" }}>
//           <div
//             className="rounded-2xl min-h-[70vh] max-h-[calc(100vh-8rem)] overflow-y-auto"
//             style={{ backgroundColor: THEME.panel, border: `1px solid ${THEME.border}` }}
//           >
//             {children}
//           </div>
//           <aside
//             className="rounded-2xl min-h-[70vh] max-h-[calc(100vh-8rem)] overflow-y-auto p-4 md:p-5"
//             style={{ backgroundColor: THEME.panelDarker, border: `1px solid ${THEME.border}` }}
//           >
//             <InsightPanel THEME={THEME} data={insights} />
//           </aside>
//         </div>
//       </div>
//     </div>
//   );
// }