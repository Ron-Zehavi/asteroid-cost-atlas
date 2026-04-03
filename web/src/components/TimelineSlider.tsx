export type PlaySpeed = 0 | 10 | 100;

interface Props {
  dayOffset: number;
  onChange: (days: number) => void;
  speed: PlaySpeed;
  onSetSpeed: (speed: PlaySpeed) => void;
}

const J2000 = new Date('2000-01-01T12:00:00Z');

function daysToDate(days: number): string {
  const date = new Date(J2000.getTime() + days * 86400000);
  return date.toISOString().slice(0, 10);
}

export function todayOffset(): number {
  return Math.round((Date.now() - J2000.getTime()) / 86400000);
}

export function TimelineSlider({ dayOffset, onChange, speed, onSetSpeed }: Props) {
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
      <input
        type="range"
        min={0}
        max={18262}
        step={1}
        value={Math.round(dayOffset)}
        onChange={(e) => { onSetSpeed(0); onChange(Number(e.target.value)); }}
      />
      <button className="timeline-btn" onClick={() => onChange(todayOffset())}>Today</button>
      <span className="timeline-speed">
        {speed === 0 ? 'paused' : speed === 10 ? '10 d/s' : '100 d/s'}
      </span>
    </div>
  );
}
