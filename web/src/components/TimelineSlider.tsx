import type { LaunchWindow } from '../utils/transfer';

export type PlaySpeed = 0 | 10 | 100;

interface Props {
  dayOffset: number;
  onChange: (days: number) => void;
  speed: PlaySpeed;
  onSetSpeed: (speed: PlaySpeed) => void;
  windows?: LaunchWindow[];
}

const J2000 = new Date('2000-01-01T12:00:00Z');
const TIMELINE_MIN = 0;
const TIMELINE_MAX = 18262;
const TIMELINE_RANGE = TIMELINE_MAX - TIMELINE_MIN;

function daysToDate(days: number): string {
  const date = new Date(J2000.getTime() + days * 86400000);
  return date.toISOString().slice(0, 10);
}

export function todayOffset(): number {
  return Math.round((Date.now() - J2000.getTime()) / 86400000);
}

function pct(dayOffset: number): number {
  return ((dayOffset - TIMELINE_MIN) / TIMELINE_RANGE) * 100;
}

export function TimelineSlider({ dayOffset, onChange, speed, onSetSpeed, windows }: Props) {
  // Filter windows to those within the timeline range
  const visibleWindows = (windows ?? []).filter(
    (w) => w.arrivalDay >= TIMELINE_MIN && w.dayOffset <= TIMELINE_MAX,
  );

  return (
    <div className="timeline-slider">
      <button
        className={`play-btn ${speed > 0 ? 'active' : ''}`}
        onClick={() => onSetSpeed(speed === 0 ? 10 : 0)}
        title={speed === 0 ? 'Play (10 d/s)' : 'Pause'}
      >
        {speed === 0 ? '▶' : '⏸'}
      </button>
      <button
        className={`play-btn fast ${speed === 100 ? 'active' : ''}`}
        onClick={() => onSetSpeed(speed === 100 ? 10 : 100)}
        title="Fast forward (100 d/s)"
      >
        ⏩
      </button>
      <span className="timeline-label">{daysToDate(Math.round(dayOffset))}</span>

      <div className="timeline-track-wrapper">
        {/* Launch window markers */}
        {visibleWindows.map((w, i) => {
          const startPct = Math.max(0, pct(w.dayOffset));
          const endPct = Math.min(100, pct(w.windowEnd));
          const arrivalPct = Math.min(100, pct(w.arrivalDay));
          const transitStartPct = Math.min(100, pct(w.windowEnd));

          return (
            <div key={i}>
              {/* Launch window band (gold) */}
              <div
                className="timeline-marker window-marker"
                style={{ left: `${startPct}%`, width: `${endPct - startPct}%` }}
                title={`Launch window: ${w.date} (${Math.round(w.windowEnd - w.dayOffset)}d)`}
                onClick={() => { onSetSpeed(0); onChange(w.dayOffset); }}
              />
              {/* Transit band (orange) */}
              <div
                className="timeline-marker transit-marker"
                style={{ left: `${transitStartPct}%`, width: `${arrivalPct - transitStartPct}%` }}
                title={`In transit → arrival ${daysToDate(w.arrivalDay)}`}
              />
              {/* Arrival dot (green) */}
              <div
                className="timeline-marker arrival-dot"
                style={{ left: `${arrivalPct}%` }}
                title={`Arrival: ${daysToDate(w.arrivalDay)}`}
                onClick={() => { onSetSpeed(0); onChange(w.arrivalDay); }}
              />
            </div>
          );
        })}

        <input
          type="range"
          min={TIMELINE_MIN}
          max={TIMELINE_MAX}
          step={1}
          value={Math.round(dayOffset)}
          onChange={(e) => { onSetSpeed(0); onChange(Number(e.target.value)); }}
        />
      </div>

      <button className="timeline-btn" onClick={() => onChange(todayOffset())}>Today</button>
      <span className="timeline-speed">
        {speed === 0 ? 'paused' : speed === 10 ? '10 d/s' : '100 d/s'}
      </span>
    </div>
  );
}
