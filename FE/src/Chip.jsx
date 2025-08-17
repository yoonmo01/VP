const Chip = ({ active, label, onClick, COLORS }) => (
    <button
        onClick={onClick}
        className="text-base px-4 py-2 rounded-full mr-3 mb-3 font-medium"
        style={{
            backgroundColor: active
                ? "rgba(88,101,242,.18)"
                : "rgba(63,65,71,.5)",
            color: active ? COLORS.blurple : COLORS.text,
            border: `1px solid ${active ? "rgba(88,101,242,.35)" : COLORS.border}`,
        }}
    >
        {label}
    </button>
);

export default Chip;
