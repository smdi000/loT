interface Props {
  label: string;
  code: string;
  value: number;
  tone?: 'cyan' | 'violet';
}

export default function JointAngleVisual({ label, code, value, tone = 'cyan' }: Props) {
  const arcLength = 201;
  const progress = Math.max(0, Math.min(value, 180)) / 180;

  return (
    <div className={`joint-range joint-range-${tone}`} role="img" aria-label={`${label}本次最大角度 ${value.toFixed(1)} 度`}>
      <svg viewBox="0 0 164 104" aria-hidden="true">
        <path className="joint-range-base" d="M18 84 A64 64 0 0 1 146 84" />
        <path
          className="joint-range-value"
          d="M18 84 A64 64 0 0 1 146 84"
          pathLength={arcLength}
          strokeDasharray={`${progress * arcLength} ${arcLength}`}
        />
        <circle cx="18" cy="84" r="3" />
        <circle cx="146" cy="84" r="3" />
      </svg>
      <div className="joint-range-copy">
        <small>{code}</small>
        <strong>{value.toFixed(1)}°</strong>
        <span>{label} · 本次最大记录</span>
      </div>
    </div>
  );
}
