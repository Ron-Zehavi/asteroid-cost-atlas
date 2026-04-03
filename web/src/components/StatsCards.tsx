import type { Stats } from '../types/asteroid';

function fmt(n: number | null | undefined, decimals = 0): string {
  if (n == null || (typeof n === 'number' && !isFinite(n))) return '—';
  return n.toLocaleString(undefined, { maximumFractionDigits: decimals });
}

export function StatsCards({ stats }: { stats: Stats | null }) {
  if (!stats) return <div className="stats-cards"><span className="stat-label">Loading atlas...</span></div>;

  const cards: [string, string][] = [
    [fmt(stats.total_objects), 'Total Asteroids'],
    [fmt(stats.scored_objects), 'Scored'],
    [fmt(stats.nea_candidates), 'NEA Candidates'],
    [fmt(stats.min_delta_v, 2), 'Min Dv (km/s)'],
    [fmt(stats.median_delta_v, 2), 'Median Dv (km/s)'],
  ];

  return (
    <div className="stats-cards">
      {cards.map(([value, label]) => (
        <div className="stat-card" key={label}>
          <span className="stat-value">{value}</span>
          <span className="stat-label">{label}</span>
        </div>
      ))}
    </div>
  );
}
