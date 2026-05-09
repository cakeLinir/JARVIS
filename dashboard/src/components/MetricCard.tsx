import type { ReactNode } from "react";

type Props = {
  label: string;
  value: ReactNode;
  hint?: string;
};

export function MetricCard({ label, value, hint }: Props) {
  return (
    <section className="metric-card">
      <span className="metric-label">{label}</span>
      <div className="metric-value">{value}</div>
      {hint ? <span className="metric-hint">{hint}</span> : null}
    </section>
  );
}
