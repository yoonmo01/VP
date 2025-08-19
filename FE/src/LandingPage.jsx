import React from "react";
import { Play } from "lucide-react";
import bg from "./assets/첫화면.png";
import "./fonts.css";

const LandingPage = ({ setCurrentPage }) => (
    <div
        className="relative min-h-screen flex items-center justify-center"
        style={{
            backgroundImage: `url(${bg})`,
            backgroundSize: "cover",
            backgroundPosition: "center",
        }}
    >
        <div className="absolute inset-0 bg-black opacity-60" />
        <div className="relative z-10 text-center px-6">
            <h1 className="text-5xl md:text-7xl font-extrabold text-white mb-6 hakgyoansim-outline-font">
                보이스피싱 시뮬레이션
            </h1>
            <p className="text-xl md:text-2xl text-gray-200 hakgyoansim-font">
                지역사회 피싱 범죄 예방을 위한 AI 에이전트 활용 연구 및 대응 방안 개발
            </p>
            <button
                onClick={() => setCurrentPage("simulator")}
                className="
            mt-12 px-10 py-4 rounded-2xl font-semibold text-lg
            bg-[#5865F2] text-white shadow-lg
            hover:bg-[#4752C4] hover:scale-105
            transition-all duration-300
            "
            >
                <Play className="inline mr-3" size={22} />
                시작하기
            </button>
        </div>
    </div>
);

export default LandingPage;
