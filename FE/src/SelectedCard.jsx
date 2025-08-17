import Badge from "./Badge";

const SelectedCard = ({ title, subtitle, children, COLORS }) => (
    <div
        className="w-full max-w-6xl mx-auto rounded-xl p-6"
        style={{
            backgroundColor: COLORS.panel,
            border: `1px solid ${COLORS.border}`,
            color: COLORS.text,
        }}
    >
        <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-xl">{title}</h3>
            <Badge tone="primary" COLORS={COLORS}>
                SELECT
            </Badge>
        </div>
        {subtitle && (
            <p className="text-base mb-4" style={{ color: COLORS.sub }}>
                {subtitle}
            </p>
        )}
        {children}
    </div>
);

export default SelectedCard;
