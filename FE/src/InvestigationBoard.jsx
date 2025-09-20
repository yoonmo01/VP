// src/InvestigationBoard.jsx
import React from "react";

/*== 색상 토큰 ==*/
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

/*== 유틸 ==*/
const getRiskColor = (score) => {
  if (score >= 75) return "#FF4D4F"; // 빨강
  if (score >= 50) return "#FAAD14"; // 주황
  return "#52C41A"; // 초록
};
const toKoreanLevel = (level) => {
  const lv = String(level || "").toLowerCase();
  if (lv === "high") return "높음";
  if (lv === "medium") return "보통";
  if (lv === "low") return "낮음";
  return level || "알수없음";
};

/*== 첫 번째 대화: 요청하신 더미데이터 ==*/
const DIALOG1 = {
  banner: "첫번째 대화",
  judgement: {
    title: "피싱판정결과",
    isPhishing: false, // 실패
    reasonTitle: "피싱 실패 근거",
    reason:
      "송금·인출·대출 실행 등 실제 금전 이동 발화가 전혀 없습니다. 피해자가 “주민등록번호 앞자리·생년월을 알려주겠다”고 의사 표현은 했지만, 실제 숫자(값)를 말한 기록은 없음 → [B기준] 불충족. 링크/QR 접속, 악성앱·원격제어 앱 설치/승인 등 [C기준]에 해당하는 행위가 없습니다. 지점 대표번호를 통한 직접 확인 의사 표명, 최종적으로 “나중에 연락”으로 대화 종료 의사를 밝힘 → [phishing=false 조건 1~3] 충족.",
  },
  risk: {
    score: 56,
    level: "medium",
    label: "위험도",
    reasonTitle: "위험도 근거",
    reasons: [
      "“주민등록번호 앞자리·생년월 제공 의사”를 밝힘(민감정보 제공 직전 단계), “조회는 진행”에 동의하는 등 관여가 지속됨.",
      "송금·인출·대출 실행 등 실제 금전 이동 발화가 전혀 없습니다. 피해자가 “주민등록번호 앞자리·생년월을 알려주겠다”고 의사 표현은 했지만, 실제 숫자(값)를 말한 기록은 없음 → [B기준] 불충족. 링크/QR 접속, 악성앱·원격제어 앱 설치/승인 등 [C기준]에 해당하는 행위가 없습니다. 지점 대표번호를 통한 직접 확인 의사 표명, 최종적으로 “나중에 연락”으로 대화 종료 의사를 밝힘 → [phishing=false 조건 1~3] 충족.",
    ],
  },
  guidance: {
    title: "지침",
    categories: ["R", "D", "F"],
    reasoning:
      "'격리형 장기통제(R)' 전략을 통해 피해자를 심리적으로 고립시키고, '전문성 연출(D)'과 '의심 무마(F)'를 통해 의심을 최소화하고 신뢰를 구축하려 합니다.",
    expected_effect:
      "피해자는 범죄 연루 공포로 인해 협조적이 될 가능성이 높아지며, 격리된 상태에서 공격자의 지시에 더욱 쉽게 따를 수 있습니다. 또한, 전문성을 강조하여 피해자의 의심을 누그러뜨리고, 보안이 강화된 환경이라는 명분으로 외부와의 접촉을 차단할 수 있습니다.",
  },
};

/*== 두 번째 대화: 요청하신 텍스트 반영 ==*/
const DIALOG2 = {
  banner: "두번째 대화",
  judgement: {
    title: "피싱판정결과",
    isPhishing: true, // 성공
    reasonTitle: "피싱 성공 근거",
    reason:
      "금전 이동 실행 의사 표명: “얼마를, 어디로 이체해야 하나요?” (turn 15)\n수취인·계좌 확인: “수취인명이 ‘OO안전보호센터(가명)’ 맞나요?” (turn 17)\n경고 무시 진행 문의: “고위험 거래 경고가 뜹니다. 계속 진행해야 하나요?” (turn 19)\n이체 승인 발화: “네… 이체 진행하겠습니다.” (turn 21) → A) 금전 이동 실행 확정\n\n(참고) 공격자가 직후 “입금 접수 완료”라고 응답(turn 22) — 판정은 피해자 발화만으로 충분하나, 흐름상 실제 완료 정황 일치\n\n기관 사칭·권위 압박: 금융감독원·계좌 보호관찰 등으로 긴급성/권위 호소(turn 0~4)\n\n링크 유도: “문자로 링크 보내주면 확인하고 진행”(turn 11·13) → C) 링크 접속 유도\n\n원격제어/보안앱 설치 요구 반복(turn 0, 6, 8) → C) 디지털 접근 허용 요구",
  },
  risk: {
    score: 78,
    level: "high",
    label: "위험도",
    reasonTitle: "위험도 근거",
    reasons: [
      "A 기준(금전 이동) 충족: 피해자 스스로 이체 진행을 발화(turn 21).",
      "D 기준(기관 사칭 유도) 및 C 기준(링크·앱·원격제어) 요구가 누적.",
      "금융앱의 ‘고위험 거래’ 경고를 인지했음에도 진행 의사 확인(turn 19→21): 경고 무시 행동 패턴.",
    ],
  },
  // guidance는 제공 안 하셔도 되므로 생략 가능
};

/* 재사용 섹션 렌더러 */
function ConversationBlock({ conv }) {
  const { judgement, risk, guidance } = conv || {};
  if (!judgement || !risk) return null;

  return (
    <>
      {/* 헤더 - 피싱판정결과 */}
      <div className="p-4 border-b" style={{ borderColor: COLORS.border }}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full" style={{ backgroundColor: "#FAAD14" }} />
            <h2 className="text-lg font-semibold" style={{ color: COLORS.text }}>
              {judgement.title}
            </h2>
          </div>
          <div className="ml-auto">
            {judgement.isPhishing ? (
              <span className="px-3 py-1 rounded text-xs text-white" style={{ backgroundColor: "#FF4D4F" }}>
                피싱 방어 실패
              </span>
            ) : (
              <span className="px-3 py-1 rounded text-xs text-white" style={{ backgroundColor: "#52C41A" }}>
                피싱 방어 성공
              </span>
            )}
          </div>
        </div>
      </div>

      {/* 본문 */}
      <div className="p-6 space-y-6">
        {/* 판단 근거 */}
        <section>
          <h3 className="text-lg font-semibold mb-3" style={{ color: COLORS.text }}>
            {judgement.reasonTitle}
          </h3>
          <div className="p-4 rounded-lg" style={{ backgroundColor: COLORS.panel }}>
            <p className="text-sm leading-relaxed whitespace-pre-wrap" style={{ color: COLORS.sub }}>
              {judgement.reason}
            </p>
          </div>
        </section>

        {/* 위험도 */}
        <section>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full" style={{ backgroundColor: COLORS.blurple }} />
              <h3 className="text-lg font-semibold" style={{ color: COLORS.text }}>
                {risk.label}
              </h3>
            </div>
            <span className="px-3 py-1 rounded text-xs text-white" style={{ backgroundColor: getRiskColor(risk.score) }}>
              {toKoreanLevel(risk.level)} (점수 {risk.score}점)
            </span>
          </div>

          {/* 게이지 */}
          <div className="w-full h-4 rounded-full overflow-hidden mb-2" style={{ backgroundColor: COLORS.panel }}>
            <div
              className="h-4 transition-all"
              style={{ width: `${risk.score}%`, backgroundColor: getRiskColor(risk.score) }}
            />
          </div>
        </section>

        {/* 위험도 근거 리스트 */}
        <section>
          <h4 className="font-medium mb-2" style={{ color: COLORS.text }}>
            {risk.reasonTitle}
          </h4>
          <ul className="space-y-2 text-sm" style={{ color: COLORS.sub }}>
            {Array.isArray(risk.reasons) &&
              risk.reasons.map((r, i) => (
                <li key={i} className="leading-relaxed whitespace-pre-wrap">
                  • {r}
                </li>
              ))}
          </ul>
        </section>

        {/* 지침(있을 때만) */}
        {guidance && (
          <section>
            <h3 className="text-lg font-semibold mb-3" style={{ color: COLORS.text }}>
              {guidance.title || "지침"}
            </h3>

            {Array.isArray(guidance.categories) && guidance.categories.length > 0 && (
              <div className="flex flex-wrap gap-2 mb-3">
                {guidance.categories.map((c, idx) => (
                  <span
                    key={idx}
                    className="px-3 py-1 rounded-full text-xs font-medium"
                    style={{ backgroundColor: COLORS.border, color: COLORS.white }}
                  >
                    {c}
                  </span>
                ))}
              </div>
            )}

            {guidance.reasoning && (
              <div className="p-4 rounded-lg mb-3" style={{ backgroundColor: COLORS.panel }}>
                <h4 className="font-medium mb-2" style={{ color: COLORS.text }}>
                  의도/전략 설명
                </h4>
                <p className="text-sm leading-relaxed" style={{ color: COLORS.sub }}>
                  {guidance.reasoning}
                </p>
              </div>
            )}

            {guidance.expected_effect && (
              <div className="p-4 rounded-lg" style={{ backgroundColor: COLORS.panel }}>
                <h4 className="font-medium mb-2" style={{ color: COLORS.text }}>
                  예상 효과
                </h4>
                <p className="text-sm leading-relaxed" style={{ color: COLORS.sub }}>
                  {guidance.expected_effect}
                </p>
              </div>
            )}
          </section>
        )}
      </div>
    </>
  );
}

/*== 메인 컴포넌트: 두 개의 대화를 아래로 이어서 렌더 ==*/
export default function InvestigationBoard({ dataList }) {
  // 기본값: 첫번째 + 두번째 더미
  const list = Array.isArray(dataList) && dataList.length > 0 ? dataList : [DIALOG1, DIALOG2];

  return (
    <div className="h-full overflow-y-auto" style={{ backgroundColor: COLORS.panelDark, maxHeight: "100vh" }}>
      {list.map((conv, idx) => (
        <div key={idx}>
          {/* 가운데 구분 배지 (두번째 대화 표시) */}
          {idx > 0 && (
            <div className="sticky top-0 z-10">
              <div
                className="flex items-center gap-3 px-4 py-2"
                style={{
                  backgroundColor: COLORS.panelDark,
                  borderTop: `1px solid ${COLORS.border}`,
                  borderBottom: `1px solid ${COLORS.border}`,
                }}
              >
                <div className="flex-1 h-px" style={{ backgroundColor: COLORS.border }} />
                <span
                  className="px-3 py-1 rounded-full text-xs font-semibold"
                  style={{ backgroundColor: COLORS.panel, color: COLORS.text, border: `1px solid ${COLORS.border}` }}
                >
                  {conv.banner || "두번째 대화"}
                </span>
                <div className="flex-1 h-px" style={{ backgroundColor: COLORS.border }} />
              </div>
            </div>
          )}

          <ConversationBlock conv={conv} />
        </div>
      ))}
    </div>
  );
}
