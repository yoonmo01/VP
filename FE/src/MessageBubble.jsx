// ✅ 변경: 피해자 헤더에 설득도 바 추가 (message.convincedPct 사용)

import { useState, useEffect } from "react";

const MessageBubble = ({ message, selectedCharacter, victimImageUrl, COLORS }) => {
  const isVictim = message.sender === "victim";
  const isScammer = message.sender === "offender";
  const isSystem = message.type === "system";
  const isAnalysis = message.type === "analysis";
  const isSpinner = isSystem && message.content.includes("🔄");

  // 설득도(%). App.jsx에서 meta로 내려줌
  const convincedPct =
    typeof message?.convincedPct === "number"
      ? Math.max(10, Math.min(100, message.convincedPct))
      : null;

  return (
    <div className={`flex ${isVictim ? "justify-end" : "justify-start"}`}>
      <div
        className={[
          "max-w-md lg:max-w-lg px-5 py-3 rounded-2xl border",
          isSystem ? "mx-auto text-center" : "",
          isSpinner ? "w-80 h-32 flex flex-col items-center justify-center" : "",
        ].join(" ")}
        style={{
          backgroundColor: isSystem
            ? "rgba(88,101,242,.12)"
            : isAnalysis
            ? "rgba(254,231,92,.12)"
            : isVictim
            ? COLORS.white
            : "#313338",
          color: isVictim ? COLORS.black : isAnalysis ? COLORS.warn : COLORS.text,
          border: `1px solid ${
            isSystem
              ? "rgba(88,101,242,.35)"
              : isAnalysis
              ? "rgba(254,231,92,.35)"
              : COLORS.border
          }`,
        }}
      >
        {/* 스피너 메시지일 때 바 애니메이션 표시 */}
        {isSpinner && (
          <div className="flex space-x-1 mb-4">
            <div className="w-1 h-8 bg-[#5865F2] animate-pulse" style={{ animationDelay: "0s" }}></div>
            <div className="w-1 h-8 bg-[#5865F2] animate-pulse" style={{ animationDelay: "0.1s" }}></div>
            <div className="w-1 h-8 bg-[#5865F2] animate-pulse" style={{ animationDelay: "0.2s" }}></div>
            <div className="w-1 h-8 bg-[#5865F2] animate-pulse" style={{ animationDelay: "0.3s" }}></div>
            <div className="w-1 h-8 bg-[#5865F2] animate-pulse" style={{ animationDelay: "0.4s" }}></div>
          </div>
        )}

        {isScammer && (
          <div className="flex items-center mb-2" style={{ color: COLORS.warn }}>
            <span className="mr-2">
              <img
                src={new URL("./assets/offender_profile.png", import.meta.url).href}
                alt="피싱범"
                className="w-8 h-8 rounded-full object-cover"
              />
            </span>
            <span className="text-sm font-medium" style={{ color: COLORS.sub }}>
              피싱범
            </span>
          </div>
        )}

        {isVictim && selectedCharacter && (
          <div className="flex items-center mb-2">
            <span className="mr-2 text-lg">
              {victimImageUrl ? (
                <img
                  src={victimImageUrl}
                  alt={selectedCharacter.name}
                  className="w-8 h-8 rounded-full object-cover"
                />
              ) : (
                `👤${selectedCharacter.avatar || ""}`
              )}
            </span>

            {/* 이름 + (설득도 바) */}
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium" style={{ color: "#687078" }}>
                {selectedCharacter.name}
              </span>
              {convincedPct != null && (
                <div className="flex items-center gap-1 min-w-[140px] max-w-[220px]">
                  <div className="flex-1 h-2 bg-[#e5e7eb] rounded overflow-hidden">
                    <div
                      className="h-full bg-red-500 transition-all"
                      style={{ width: `${convincedPct}%` }}
                      title={`설득도 ${convincedPct}%`}
                    />
                  </div>
                  <span className="text-[10px] text-gray-500 w-8 text-right">
                    {convincedPct}%
                  </span>
                </div>
              )}
            </div>
          </div>
        )}

        <p className="whitespace-pre-line text-base leading-relaxed">
          {isSpinner ? message.content.replace("🔄 ", "") : message.content}
        </p>
        <div className="text-xs mt-2 opacity-70" style={{ color: COLORS.sub }}>
          {message.timestamp}
        </div>
      </div>
    </div>
  );
};

export default MessageBubble;