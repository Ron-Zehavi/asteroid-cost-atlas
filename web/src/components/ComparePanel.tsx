import type { Asteroid } from '../types/asteroid';

function fmt(n: number | null | undefined, d = 2): string {
  if (n == null || !isFinite(n)) return '—';
  return n.toLocaleString(undefined, { maximumFractionDigits: d });
}

function fmtUsd(n: number | null | undefined): string {
  if (n == null || !isFinite(n)) return '—';
  if (Math.abs(n) >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
  if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  return `$${(n ?? 0).toLocaleString()}`;
}

const FIELDS: [string, (a: Asteroid) => string][] = [
  ['Name', (a) => a.name],
  ['Class', (a) => a.composition_class ?? '—'],
  ['Diameter (km)', (a) => fmt(a.diameter_estimated_km, 3)],
  ['Delta-v (km/s)', (a) => fmt(a.delta_v_km_s, 2)],
  ['Tisserand', (a) => fmt(a.tisserand_jupiter, 3)],
  ['Margin/kg', (a) => fmtUsd(a.margin_per_kg)],
  ['Break-even (kg)', (a) => fmt(a.break_even_kg, 0)],
  ['Viable', (a) => a.is_viable ? 'Yes' : 'No'],
  ['Missions', (a) => fmt(a.missions_supported, 0)],
  ['Campaign Profit', (a) => fmtUsd(a.campaign_profit_usd)],
  ['Rank', (a) => fmt(a.economic_priority_rank, 0)],
];

interface Props {
  pinned: Asteroid[];
  onRemove: (spkid: number) => void;
  onClose: () => void;
}

export function ComparePanel({ pinned, onRemove, onClose }: Props) {
  if (pinned.length === 0) return null;

  return (
    <div className="compare-panel">
      <div className="compare-header">
        <h3>Compare ({pinned.length})</h3>
        <button onClick={onClose} className="close-btn">x</button>
      </div>
      <table className="compare-table">
        <tbody>
          {FIELDS.map(([label, render]) => (
            <tr key={label}>
              <td className="compare-label">{label}</td>
              {pinned.map((a) => (
                <td key={a.spkid}>{render(a)}</td>
              ))}
            </tr>
          ))}
          <tr>
            <td className="compare-label"></td>
            {pinned.map((a) => (
              <td key={a.spkid}>
                <button onClick={() => onRemove(a.spkid)} className="remove-btn">Remove</button>
              </td>
            ))}
          </tr>
        </tbody>
      </table>
    </div>
  );
}
