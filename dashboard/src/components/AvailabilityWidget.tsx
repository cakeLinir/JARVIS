import type { AvailabilityResult, StreamRecommendation } from "../types/shift";
import { REC_LABELS, SHIFT_TYPE_CLASS, SHIFT_TYPE_LABELS } from "../types/shift";

// ── Typen ────────────────────────────────────────────────────────────────────

type Props = {
  today: AvailabilityResult | null | undefined;
  tomorrow: AvailabilityResult | null | undefined;
};

// ── Hilfsfunktionen ──────────────────────────────────────────────────────────

// Entfernt Farb-Emojis aus Backend-Texten für kompakte Darstellung
function stripEmoji(text: string): string {
  return text.replace(/[🟢🟡🟠🔴🛌]/g, "").replace(/\s+/g, " ").trim();
}

// Ampel-Farbe als CSS-Variable-Referenz
const REC_COLOR: Record<StreamRecommendation, string> = {
  free:        "var(--ok)",
  conditional: "var(--warn)",
  discouraged: "#e07b39",
  blocked:     "var(--bad)",
};

// Ampel-Emoji für kompakten Überblick
const REC_EMOJI: Record<StreamRecommendation, string> = {
  free:        "🟢",
  conditional: "🟡",
  discouraged: "🟠",
  blocked:     "🔴",
};

// ── Tages-Kachel ─────────────────────────────────────────────────────────────

function DayAvail({ data, label }: { data: AvailabilityResult | null | undefined; label: string }) {
  if (!data) {
    return (
      <div className="avail-day">
        <div className="avail-day-label">{label}</div>
        <span className="muted" style={{ fontSize: 13 }}>Keine Daten</span>
      </div>
    );
  }

  const rec = data.streamRecommendation;
  const recColor = REC_COLOR[rec] ?? "var(--muted)";
  const shiftClass = data.shift
    ? (SHIFT_TYPE_CLASS[data.shift.type as keyof typeof SHIFT_TYPE_CLASS] ?? "")
    : "";
  const shiftLabel = data.shift
    ? (SHIFT_TYPE_LABELS[data.shift.type as keyof typeof SHIFT_TYPE_LABELS] ?? data.shift.label)
    : null;

  return (
    <div className="avail-day">
      {/* Tag-Kopfzeile */}
      <div className="avail-day-header">
        <span className="avail-day-label">{label}</span>
        <span className="avail-date-str">{data.date}</span>
      </div>

      {/* Schicht-Badge */}
      <div className="avail-shift-row">
        {shiftLabel ? (
          <>
            <span
              className={`badge shift-inline-badge ${shiftClass}`}
              style={{ fontSize: 12 }}
            >
              {shiftLabel}
            </span>
            {data.shift?.start && data.shift.start !== "00:00" && (
              <span className="avail-time muted">
                {data.shift.start}–{data.shift.end}
                {data.shift.crossesMidnight && " +1"}
              </span>
            )}
          </>
        ) : (
          <span className="muted" style={{ fontSize: 13 }}>Keine Schicht</span>
        )}
      </div>

      {/* Streaming-Ampel */}
      <div className="avail-rec-row">
        <span className="avail-rec-emoji">{REC_EMOJI[rec]}</span>
        <span className="avail-rec-label" style={{ color: recColor }}>
          {REC_LABELS[rec]}
        </span>
        {data.streamWindow && (
          <span className="avail-window">
            {data.streamWindow.from}–{data.streamWindow.to}
          </span>
        )}
      </div>

      {/* Begründungstext */}
      <div className="avail-reason">{stripEmoji(data.reason)}</div>
    </div>
  );
}

// ── Haupt-Widget ─────────────────────────────────────────────────────────────

export function AvailabilityWidget({ today, tomorrow }: Props) {
  return (
    <div className="avail-widget">
      <DayAvail data={today} label="Heute" />
      <DayAvail data={tomorrow} label="Morgen" />
    </div>
  );
}
