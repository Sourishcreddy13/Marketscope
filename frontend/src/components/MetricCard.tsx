export default function MetricCard({ label, value, tone = '' }: { label: string; value: string; tone?: string }) {
  return <div className="metric-card"><span className="eyebrow">{label}</span><strong className={tone}>{value}</strong></div>
}
