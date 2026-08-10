interface Props {
  label: string;
  value: string | number;
  hint: string;
  tone?: 'cyan' | 'blue' | 'violet' | 'green';
}

export default function MetricCard({ label, value, hint, tone = 'cyan' }: Props) {
  return (
    <div className={`metric-card metric-${tone}`}>
      <div className="metric-glow" />
      <span className="metric-label">{label}</span>
      <strong>{value}</strong>
      <span className="metric-hint">{hint}</span>
    </div>
  );
}
