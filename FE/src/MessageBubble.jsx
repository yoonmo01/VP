import { useState, useEffect } from "react";

const MessageBubble = ({ message, selectedCharacter, victimImageUrl, COLORS }) => {
    const isVictim = message.sender === "victim";
    const isScammer = message.sender === "offender";
    const isSystem = message.type === "system";
    const isAnalysis = message.type === "analysis";
    const isSpinner = isSystem && message.content.includes("🔄");

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
                    color: isVictim
                        ? COLORS.black
                        : isAnalysis
                          ? COLORS.warn
                          : COLORS.text,
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
                        <div className="w-1 h-8 bg-[#5865F2] animate-pulse" style={{animationDelay: '0s'}}></div>
                        <div className="w-1 h-8 bg-[#5865F2] animate-pulse" style={{animationDelay: '0.1s'}}></div>
                        <div className="w-1 h-8 bg-[#5865F2] animate-pulse" style={{animationDelay: '0.2s'}}></div>
                        <div className="w-1 h-8 bg-[#5865F2] animate-pulse" style={{animationDelay: '0.3s'}}></div>
                        <div className="w-1 h-8 bg-[#5865F2] animate-pulse" style={{animationDelay: '0.4s'}}></div>
                    </div>
                )}

                {isScammer && (
                    <div
                        className="flex items-center mb-2"
                        style={{ color: COLORS.warn }}
                    >
                        <span className="mr-2 text-lg">🎭</span>
                        <span
                            className="text-sm font-medium"
                            style={{ color: COLORS.sub }}
                        >
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
                                `👤${selectedCharacter.avatar || ''}`
                            )}
                        </span>
                        <span
                            className="text-sm font-medium"
                            style={{ color: "#687078" }}
                        >
                            {selectedCharacter.name}
                        </span>
                    </div>
                )}
                <p className="whitespace-pre-line text-base leading-relaxed">
                    {isSpinner ? message.content.replace("🔄 ", "") : message.content}
                </p>
                <div
                    className="text-xs mt-2 opacity-70"
                    style={{ color: COLORS.sub }}
                >
                    {message.timestamp}
                </div>
            </div>
        </div>
    );
};

export default MessageBubble;
