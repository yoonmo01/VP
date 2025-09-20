// src/components/TTSModal.jsx
import React, { useEffect, useRef, useState } from "react";
import { X, Mic } from "lucide-react";
import AudioWaveform from "./AudioWaveform";
import SpeakerAvatar from "./SpeakerAvatar";
import DEFAULT_COLORS from "../constants/colors";
import victim from "../assets/avatars/01.png";
import criminal from "../assets/avatars/02.png";

const API_BASE = "http://127.0.0.1:8000";

const toUrl = (b64, mime) => {
  const clean = (b64 || "").replace(/\s/g, "");
  const pad = "=".repeat((4 - (clean.length % 4)) % 4);
  const norm = clean.replace(/-/g, "+").replace(/_/g, "/") + pad;
  const type = !mime || mime === "audio/wav" ? "audio/wav" : mime;
  return `data:${type};base64,${norm}`;
};

export default function TTSModal({ isOpen, onClose, COLORS }) {
  const theme = COLORS ?? DEFAULT_COLORS;

  const [loading, setLoading] = useState(false);
  const [dialogue, setDialogue] = useState([]);
  const [urls, setUrls] = useState([]);
  const [idx, setIdx] = useState(-1);
  const [currentText, setCurrentText] = useState("");
  const [isPlaying, setIsPlaying] = useState(false);

  const audioRef = useRef(null);

  useEffect(() => {
    // console.log("TTS theme:", theme);
  }, [theme]);

  const playAt = async (i, sources = null, itemsArr = null) => {
    const a = audioRef.current;
    if (!a) return;
    const srcArray = sources || urls;
    const itemsArray = itemsArr || dialogue;
    if (!srcArray[i] || !itemsArray[i]) return;

    const item = itemsArray[i];
    setIdx(i);
    setCurrentText(item.text || "");
    setIsPlaying(true);

    try {
      a.pause();
      a.src = srcArray[i];
      a.load();

      await new Promise((resolve, reject) => {
        a.addEventListener("loadedmetadata", resolve, { once: true });
        a.addEventListener("error", reject, { once: true });
        setTimeout(() => reject(new Error("timeout")), 6000);
      });

      await a.play();
    } catch (err) {
      console.warn("[playAt] error:", err);
      setIsPlaying(false);
    }
  };

  const handlePlayDialogue = async () => {
    setLoading(true);
    setDialogue([]);
    setUrls([]);
    setIdx(-1);
    setCurrentText("");
    setIsPlaying(false);

    try {
      const res = await fetch(`${API_BASE}/api/tts/synthesize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: "dialogue" }),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const data = await res.json();
      const items = (data.items || []).map((it) => ({
        ...it,
        totalDurationSec: Number(it.totalDurationSec) || 0,
        charTimeSec: Number(it.charTimeSec) || 0,
      }));

      setDialogue(items);
      const urlsLocal = items.map((it) => toUrl(it.audioContent, it.contentType));
      setUrls(urlsLocal);
      playAt(0, urlsLocal, items);
    } catch (e) {
      alert(`TTS 오류: ${e.message}`);
      console.error(e);
      setIsPlaying(false);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const a = audioRef.current;
    if (!a) return;

    const onEnded = () => {
      const next = idx + 1;
      if (next < dialogue.length) {
        playAt(next, urls, dialogue);
      } else {
        setIdx(-1);
        setCurrentText("");
        setIsPlaying(false);
      }
    };
    const onPlay = () => setIsPlaying(true);
    const onPause = () => setIsPlaying(false);
    const onError = () => setIsPlaying(false);

    a.addEventListener("ended", onEnded);
    a.addEventListener("play", onPlay);
    a.addEventListener("pause", onPause);
    a.addEventListener("error", onError);

    return () => {
      a.removeEventListener("ended", onEnded);
      a.removeEventListener("play", onPlay);
      a.removeEventListener("pause", onPause);
      a.removeEventListener("error", onError);
    };
  }, [idx, urls, dialogue]);

  if (!isOpen) return null;

  const current = idx >= 0 ? dialogue[idx] : null;
  const currentSpeaker = current?.speaker;

  const modalShadow = `0 8px 30px ${theme.black}80, 0 2px 8px ${theme.accent}20`;

  // 파형/아바타 사이즈 연동 상수 (고정 사이즈 내에서 조절)
  const WAVE_HEIGHT = 140;
  const WAVE_MAX_BAR = 120;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="absolute inset-0"
        style={{ backgroundColor: `${theme.black}CC` }}
        aria-hidden="true"
      />

      {/* ✅ 고정 크기 모달 (가로 900px, 세로 760px) */}
      <div
        className="relative w-[900px] mx-4 rounded-3xl border overflow-hidden flex flex-col"
        style={{
          height: "760px",
          background: `linear-gradient(180deg, ${theme.panel} 0%, ${theme.panelDark} 100%)`,
          borderColor: theme.border,
          boxShadow: modalShadow,
          backdropFilter: "saturate(1.05) blur(6px)",
        }}
        role="dialog"
        aria-modal="true"
      >
        <div
          className="flex items-center justify-between px-6 py-4 border-b rounded-t-3xl"
          style={{
            borderColor: theme.border,
            backgroundColor: theme.panel,
          }}
        >
          <h2 className="text-2xl font-bold" style={{ color: theme.text }}>
            TTS 대화 시뮬레이션
          </h2>
          <button
            onClick={onClose}
            aria-label="닫기"
            className="p-2 rounded-lg transition-colors duration-200 hover:opacity-85"
            style={{
              color: theme.sub,
              backgroundColor: theme.panelDark,
            }}
          >
            <X size={20} />
          </button>
        </div>

        {/* ✅ 본문: overflow 숨김으로 스크롤 제거 */}
        <div className="flex-1 px-8 py-6 flex flex-col overflow-hidden">
          {/* 상단 시나리오 전환 버튼바 + 주요 액션 */}
          <div className="flex items-center justify-between gap-3 mb-4">
            <div className="flex items-center gap-3">
              <button
                onClick={() =>
                  alert("다음 시나리오(다른 수법)로 이어집니다. (추후 구현)")
                }
                className="px-4 py-2 rounded-md text-sm font-semibold transition-colors"
                style={{
                  backgroundColor: theme.panel,
                  color: theme.text,
                  border: `1px solid ${theme.border}`,
                }}
              >
                다음 시나리오 이어가기
              </button>
              <button
                onClick={() => alert("다른 수법 #2 (추후 구현)")}
                className="px-4 py-2 rounded-md text-sm font-medium transition-colors"
                style={{
                  backgroundColor: theme.panelDark,
                  color: theme.sub,
                  border: `1px solid ${theme.border}`,
                }}
              >
                다른 수법 #2
              </button>
              <button
                onClick={() => alert("다른 수법 #3 (추후 구현)")}
                className="px-4 py-2 rounded-md text-sm font-medium transition-colors"
                style={{
                  backgroundColor: theme.panelDark,
                  color: theme.sub,
                  border: `1px solid ${theme.border}`,
                }}
              >
                다른 수법 #3
              </button>
            </div>

            {/* 주요 액션: 대화 재생 */}
            <button
              onClick={handlePlayDialogue}
              disabled={loading}
              className="px-5 py-2.5 rounded-lg font-semibold transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed hover:opacity-95"
              style={{
                backgroundColor: loading ? theme.border : theme.blurple,
                color: theme.white,
                boxShadow: `0 8px 24px ${theme.blurple}26, 0 2px 8px ${theme.black}33`,
                border: `1px solid ${theme.blurple}55`,
              }}
              aria-label="대화 재생"
              title="대화 재생"
            >
              {loading ? (
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  준비 중...
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <Mic size={16} />
                  대화 재생
                </div>
              )}
            </button>
          </div>

          {/* 버튼바 하단 분리선(선택) */}
          <div
            className="w-full h-px my-2"
            style={{
              backgroundColor: theme.border,
              boxShadow: `0 1px 0 ${theme.black}22`,
            }}
          />

          {/* 중앙 배치: 위/아래 가변 여백으로 시각적 중앙 정렬 */}
          <div className="flex-1" />

          {/* 프로필 + 파형 */}
          <div
            className="grid items-center my-6"
            style={{
              gridTemplateColumns: `${WAVE_MAX_BAR + 40}px 1fr ${WAVE_MAX_BAR + 40}px`,
              columnGap: "24px",
            }}
          >
            <SpeakerAvatar
              speaker="offender"
              isActive={currentSpeaker === "offender"}
              isPlaying={isPlaying}
              COLORS={theme}
              size={WAVE_MAX_BAR}
              photoSrc={criminal}
              alt="피싱범"
            />

            <div className="w-full">
              <AudioWaveform
                isActive={isPlaying}
                speaker={currentSpeaker}
                COLORS={theme}
                heightPx={WAVE_HEIGHT}
                maxBarHeight={WAVE_MAX_BAR}
                gap={4}
              />
            </div>

            <SpeakerAvatar
              speaker="victim"
              isActive={currentSpeaker === "victim"}
              isPlaying={isPlaying}
              COLORS={theme}
              size={WAVE_MAX_BAR}
              photoSrc={victim}
              alt="피해자"
            />
          </div>

          <div className="flex-1" />

          {/* 대화 로그(크게, 중앙 정렬) */}
          <div
            className="min-h-24 p-5 rounded-lg border text-center flex items-center justify-center"
            style={{
              background: theme.bg,
              borderColor: theme.border,
              color: theme.text,
              boxShadow: `inset 0 1px 0 ${theme.black}30`,
            }}
          >
            <p className="text-lg leading-relaxed" style={{ maxWidth: 980 }}>
              {currentText || "대화를 시작하려면 위의 ‘대화 재생’ 버튼을 눌러주세요."}
            </p>
          </div>
        </div>

        <audio ref={audioRef} className="hidden" />
      </div>
    </div>
  );
}


// // src/components/TTSModal.jsx
// import React, { useEffect, useRef, useState } from "react";
// import { X, Mic } from "lucide-react";
// import AudioWaveform from "./AudioWaveform";
// import SpeakerAvatar from "./SpeakerAvatar";
// import DEFAULT_COLORS from "../constants/colors";
// import victim from "../assets/avatars/01.png";
// import criminal from "../assets/avatars/02.png";

// const API_BASE = "http://127.0.0.1:8000";

// const toUrl = (b64, mime) => {
//   const clean = (b64 || "").replace(/\s/g, "");
//   const pad = "=".repeat((4 - (clean.length % 4)) % 4);
//   const norm = clean.replace(/-/g, "+").replace(/_/g, "/") + pad;
//   const type = !mime || mime === "audio/wav" ? "audio/wav" : mime;
//   return `data:${type};base64,${norm}`;
// };

// export default function TTSModal({ isOpen, onClose, COLORS }) {
//   const theme = COLORS ?? DEFAULT_COLORS;

//   const [loading, setLoading] = useState(false);
//   const [dialogue, setDialogue] = useState([]);
//   const [urls, setUrls] = useState([]);
//   const [idx, setIdx] = useState(-1);
//   const [currentText, setCurrentText] = useState("");
//   const [isPlaying, setIsPlaying] = useState(false);

//   const audioRef = useRef(null);

//   useEffect(() => {
//     // console.log("TTS theme:", theme);
//   }, [theme]);

//   const playAt = async (i, sources = null, itemsArr = null) => {
//     const a = audioRef.current;
//     if (!a) return;
//     const srcArray = sources || urls;
//     const itemsArray = itemsArr || dialogue;
//     if (!srcArray[i] || !itemsArray[i]) return;

//     const item = itemsArray[i];
//     setIdx(i);
//     setCurrentText(item.text || "");
//     setIsPlaying(true);

//     try {
//       a.pause();
//       a.src = srcArray[i];
//       a.load();

//       await new Promise((resolve, reject) => {
//         a.addEventListener("loadedmetadata", resolve, { once: true });
//         a.addEventListener("error", reject, { once: true });
//         setTimeout(() => reject(new Error("timeout")), 6000);
//       });

//       await a.play();
//     } catch (err) {
//       console.warn("[playAt] error:", err);
//       setIsPlaying(false);
//     }
//   };

//   const handlePlayDialogue = async () => {
//     setLoading(true);
//     setDialogue([]);
//     setUrls([]);
//     setIdx(-1);
//     setCurrentText("");
//     setIsPlaying(false);

//     try {
//       const res = await fetch(`${API_BASE}/api/tts/synthesize`, {
//         method: "POST",
//         headers: { "Content-Type": "application/json" },
//         body: JSON.stringify({ mode: "dialogue" }),
//       });

//       if (!res.ok) throw new Error(`HTTP ${res.status}`);

//       const data = await res.json();
//       const items = (data.items || []).map((it) => ({
//         ...it,
//         totalDurationSec: Number(it.totalDurationSec) || 0,
//         charTimeSec: Number(it.charTimeSec) || 0,
//       }));

//       setDialogue(items);
//       const urlsLocal = items.map((it) => toUrl(it.audioContent, it.contentType));
//       setUrls(urlsLocal);
//       playAt(0, urlsLocal, items);
//     } catch (e) {
//       alert(`TTS 오류: ${e.message}`);
//       console.error(e);
//       setIsPlaying(false);
//     } finally {
//       setLoading(false);
//     }
//   };

//   useEffect(() => {
//     const a = audioRef.current;
//     if (!a) return;

//     const onEnded = () => {
//       const next = idx + 1;
//       if (next < dialogue.length) {
//         playAt(next, urls, dialogue);
//       } else {
//         setIdx(-1);
//         setCurrentText("");
//         setIsPlaying(false);
//       }
//     };
//     const onPlay = () => setIsPlaying(true);
//     const onPause = () => setIsPlaying(false);
//     const onError = () => setIsPlaying(false);

//     a.addEventListener("ended", onEnded);
//     a.addEventListener("play", onPlay);
//     a.addEventListener("pause", onPause);
//     a.addEventListener("error", onError);

//     return () => {
//       a.removeEventListener("ended", onEnded);
//       a.removeEventListener("play", onPlay);
//       a.removeEventListener("pause", onPause);
//       a.removeEventListener("error", onError);
//     };
//   }, [idx, urls, dialogue]);

//   if (!isOpen) return null;

//   const current = idx >= 0 ? dialogue[idx] : null;
//   const currentSpeaker = current?.speaker;

//   const modalShadow = `0 8px 30px ${theme.black}80, 0 2px 8px ${theme.accent}20`;

//   // 파형/아바타 사이즈 연동 상수
//   const WAVE_HEIGHT = 140;
//   const WAVE_MAX_BAR = 120;

//   return (
//     <div className="fixed inset-0 z-50 flex items-center justify-center">
//       <div
//         className="absolute inset-0"
//         style={{ backgroundColor: `${theme.black}CC` }}
//         aria-hidden="true"
//       />

//       <div
//         className="relative w/full max-w-[900px] mx-4 rounded-3xl border overflow-hidden flex flex-col"
//         style={{
//           background: `linear-gradient(180deg, ${theme.panel} 0%, ${theme.panelDark} 100%)`,
//           borderColor: theme.border,
//           boxShadow: modalShadow,
//           backdropFilter: "saturate(1.05) blur(6px)",
//           minHeight: "80vh",
//           maxHeight: "95vh",
//           height: "85vh", //고정 높이
//         }}
//         role="dialog"
//         aria-modal="true"
//       >
//         <div
//           className="flex items-center justify-between px-6 py-4 border-b rounded-t-3xl"
//           style={{
//             borderColor: theme.border,
//             backgroundColor: theme.panel,
//           }}
//         >
//           <h2 className="text-2xl font-bold" style={{ color: theme.text }}>
//             TTS 대화 시뮬레이션
//           </h2>
//           <button
//             onClick={onClose}
//             aria-label="닫기"
//             className="p-2 rounded-lg transition-colors duration-200 hover:opacity-85"
//             style={{
//               color: theme.sub,
//               backgroundColor: theme.panelDark,
//             }}
//           >
//             <X size={20} />
//           </button>
//         </div>

//         <div className="flex-1 px-8 py-6 overflow-y-scroll flex flex-col">
//           {/* 상단 시나리오 전환 버튼바 + 주요 액션 */}
//           <div className="flex items-center justify-between gap-3 mb-4">
//             <div className="flex items-center gap-3">
//               <button
//                 onClick={() =>
//                   alert("다음 시나리오(다른 수법)로 이어집니다. (추후 구현)")
//                 }
//                 className="px-4 py-2 rounded-md text-sm font-semibold transition-colors"
//                 style={{
//                   backgroundColor: theme.panel,
//                   color: theme.text,
//                   border: `1px solid ${theme.border}`,
//                 }}
//               >
//                 다음 시나리오 이어가기
//               </button>
//               <button
//                 onClick={() => alert("다른 수법 #2 (추후 구현)")}
//                 className="px-4 py-2 rounded-md text-sm font-medium transition-colors"
//                 style={{
//                   backgroundColor: theme.panelDark,
//                   color: theme.sub,
//                   border: `1px solid ${theme.border}`,
//                 }}
//               >
//                 다른 수법 #2
//               </button>
//               <button
//                 onClick={() => alert("다른 수법 #3 (추후 구현)")}
//                 className="px-4 py-2 rounded-md text-sm font-medium transition-colors"
//                 style={{
//                   backgroundColor: theme.panelDark,
//                   color: theme.sub,
//                   border: `1px solid ${theme.border}`,
//                 }}
//               >
//                 다른 수법 #3
//               </button>
//             </div>

//             {/* 주요 액션: 대화 재생 */}
//             <button
//               onClick={handlePlayDialogue}
//               disabled={loading}
//               className="px-5 py-2.5 rounded-lg font-semibold transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed hover:opacity-95"
//               style={{
//                 backgroundColor: loading ? theme.border : theme.blurple,
//                 color: theme.white,
//                 boxShadow: `0 8px 24px ${theme.blurple}26, 0 2px 8px ${theme.black}33`,
//                 border: `1px solid ${theme.blurple}55`,
//               }}
//               aria-label="대화 재생"
//               title="대화 재생"
//             >
//               {loading ? (
//                 <div className="flex items-center gap-2">
//                   <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
//                   준비 중...
//                 </div>
//               ) : (
//                 <div className="flex items-center gap-2">
//                   <Mic size={16} />
//                   대화 재생
//                 </div>
//               )}
//             </button>
//           </div>

//           {/* 분리선 */}
//             <div
//             className="w-full h-px my-2"
//             style={{
//                 backgroundColor: theme.border,           // 테마 경계선 색상
//                 boxShadow: `0 1px 0 ${theme.black}22`,   // 살짝 입체감(선택)
//             }}
//             />

//           {/* 프로필 섹션 중앙 정렬: 위쪽 가변 여백 */}
//           <div className="flex-1" />

//           {/* 상단 영역: 좌(아바타) - 중앙(파형) - 우(아바타) */}
//           <div
//             className="grid items-center my-8"
//             style={{
//               gridTemplateColumns: `${WAVE_MAX_BAR + 40}px 1fr ${WAVE_MAX_BAR + 40}px`,
//               columnGap: "24px",
//             }}
//           >
//             <SpeakerAvatar
//               speaker="offender"
//               isActive={currentSpeaker === "offender"}
//               isPlaying={isPlaying}
//               COLORS={theme}
//               size={WAVE_MAX_BAR}
//               photoSrc={criminal}
//               alt="피싱범"
//             />

//             <div className="w-full">
//               <AudioWaveform
//                 isActive={isPlaying}
//                 speaker={currentSpeaker}
//                 COLORS={theme}
//                 heightPx={WAVE_HEIGHT}
//                 maxBarHeight={WAVE_MAX_BAR}
//                 gap={4}
//               />
//             </div>

//             <SpeakerAvatar
//               speaker="victim"
//               isActive={currentSpeaker === "victim"}
//               isPlaying={isPlaying}
//               COLORS={theme}
//               size={WAVE_MAX_BAR}
//               photoSrc={victim}
//               alt="피해자"
//             />
//           </div>

//           {/* 프로필 섹션 중앙 정렬: 아래쪽 가변 여백 */}
//           <div className="flex-1" />

//           {/* 대화 로그 영역 */}
//           <div
//             className="min-h-28 p-6 rounded-lg border text-center flex items-center justify-center mb-6"
//             style={{
//               background: theme.bg,
//               borderColor: theme.border,
//               color: theme.text,
//               boxShadow: `inset 0 1px 0 ${theme.black}30`,
//             }}
//           >
//             <p className="text-xl md:text-2xl leading-relaxed" style={{ maxWidth: 980 }}>
//               {currentText || "대화를 시작하려면 아래 버튼을 누르세요."}
//             </p>
//           </div>

//           {/* 진행률 UI가 필요하면 아래 주석을 해제하세요.
//           {dialogue.length > 0 && (
//             <div className="mt-6">
//               <div className="flex justify-between text-base mb-2" style={{ color: theme.sub }}>
//                 <span>진행률</span>
//                 <span>{idx + 1} / {dialogue.length}</span>
//               </div>
//               <div className="h-3 rounded-full overflow-hidden" style={{ backgroundColor: theme.border }}>
//                 <div
//                   className="h-3 transition-all duration-300 rounded-full"
//                   style={{
//                     backgroundColor: theme.blurple,
//                     width: `${dialogue.length > 0 ? ((idx + 1) / dialogue.length) * 100 : 0}%`,
//                     boxShadow: `0 4px 14px ${theme.blurple}40`,
//                   }}
//                 />
//               </div>
//             </div>
//           )} */}
//         </div>

//         <audio ref={audioRef} className="hidden" />
//       </div>
//     </div>
//   );
// }
