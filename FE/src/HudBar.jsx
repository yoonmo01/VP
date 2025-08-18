import { Shield } from "lucide-react";
import AIDisclaimerScroll from "./AIDisclaimerScroll";

const HudBar = ({ COLORS }) => (
    <div
        className="flex items-center justify-between px-6 py-4 rounded-tl-3xl rounded-tr-3xl"
        style={{
            backgroundColor: COLORS.panel,
            borderBottom: `1px solid ${COLORS.border}`,
        }}
    >
        <div className="flex items-center gap-3">
            <span
                className="text-xs tracking-widest px-3 py-2 rounded"
                style={{
                    color: COLORS.blurple,
                    backgroundColor: "rgba(88,101,242,.12)",
                    border: `1px solid rgba(88,101,242,.3)`,
                }}
            >
                CASE LOG
            </span>
            <span
                className="text-base font-medium"
                style={{ color: COLORS.sub }}
            >
                사건번호: SIM-
                {new Date().toISOString().slice(2, 10).replace(/-/g, "")}
            </span>
        </div>
        <div className="flex items-center gap-2">
            <AIDisclaimerScroll COLORS={COLORS} />
            <Shield size={20} color={COLORS.sub} />
        </div>
    </div>
);

export default HudBar;
