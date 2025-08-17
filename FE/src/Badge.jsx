const Badge = ({ children, tone = "neutral", COLORS }) => {
    const tones = {
        neutral: {
            bg: "rgba(63,65,71,.5)",
            bd: COLORS.border,
            fg: COLORS.text,
        },
        primary: {
            bg: "rgba(88,101,242,.12)",
            bd: "rgba(88,101,242,.3)",
            fg: COLORS.blurple,
        },
        warn: {
            bg: "rgba(254,231,92,.12)",
            bd: "rgba(254,231,92,.35)",
            fg: COLORS.warn,
        },
        danger: {
            bg: "rgba(237,66,69,.12)",
            bd: "rgba(237,66,69,.35)",
            fg: COLORS.danger,
        },
        success: {
            bg: "rgba(87,242,135,.12)",
            bd: "rgba(87,242,135,.35)",
            fg: COLORS.success,
        },
    };
    const t = tones[tone] || tones.neutral;
    return (
        <span
            className="text-sm px-3 py-2 rounded font-medium"
            style={{
                backgroundColor: t.bg,
                border: `1px solid ${t.bd}`,
                color: t.fg,
            }}
        >
            {children}
        </span>
    );
};

export default Badge;
