import { useState, useEffect } from "react";

const SpinnerMessage = ({ simulationState, COLORS }) => {
    const [messageIndex, setMessageIndex] = useState(0);
    
    const spinnerMessages = [
        "피싱범이 전략 회의 중...",
        "피해자가 전화를 받는 중...",
        "AI가 대화 시나리오를 구상 중...",
        "보이스피싱 시뮬레이션 준비 중...",
        "피싱범이 목표를 선정 중...",
        "피해자가 취약점을 노출 중...",
        "대화 로그를 수집 중...",
        "피싱 기법을 분석 중...",
        "시뮬레이션 환경을 구축 중...",
        "AI 모델이 학습 데이터를 분석 중..."
    ];

    // 3초마다 메시지 변경 (시스템 메시지 추가하지 않음)
    useEffect(() => {
        if (simulationState === "PREPARE" || simulationState === "RUNNING") {
            const interval = setInterval(() => {
                setMessageIndex(prev => (prev + 1) % spinnerMessages.length);
            }, 3000);
            
            return () => clearInterval(interval);
        }
    }, [simulationState]);

    // 시뮬레이션이 실행 중이 아니면 스피너를 표시하지 않음
    if (simulationState !== "PREPARE" && simulationState !== "RUNNING") {
        return null;
    }

    return (
        <div className="flex justify-center py-8">
            <div 
                className="bg-[#2B2D31] rounded-lg shadow-lg p-8 flex flex-col items-center justify-center border w-80 h-32" 
                style={{ borderColor: COLORS.border }}
            >
                {/* 바 애니메이션 */}
                <div className="flex space-x-1 mb-4">
                    <div className="w-1 h-8 bg-[#5865F2] animate-pulse" style={{animationDelay: '0s'}}></div>
                    <div className="w-1 h-8 bg-[#5865F2] animate-pulse" style={{animationDelay: '0.1s'}}></div>
                    <div className="w-1 h-8 bg-[#5865F2] animate-pulse" style={{animationDelay: '0.2s'}}></div>
                    <div className="w-1 h-8 bg-[#5865F2] animate-pulse" style={{animationDelay: '0.3s'}}></div>
                    <div className="w-1 h-8 bg-[#5865F2] animate-pulse" style={{animationDelay: '0.4s'}}></div>
                </div>
                
                {/* 메시지 */}
                <p className="text-sm text-center" style={{ color: COLORS.sub }}>
                    {spinnerMessages[messageIndex]}
                </p>
            </div>
        </div>
    );
};

export default SpinnerMessage;
