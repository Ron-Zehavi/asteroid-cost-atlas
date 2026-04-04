import type { Asteroid } from '../types/asteroid';
import { extractionInventory, METALS, METAL_PRICES } from '../utils/mining';

function fmtN(n: number | null | undefined, d = 0): string {
  if (n == null || !isFinite(n)) return '—';
  return n.toLocaleString(undefined, { maximumFractionDigits: d });
}

function fmtKgUsd(kg: number, usd: number): string {
  if (!isFinite(kg) || kg < 0.01) return '—';
  const kgStr = kg >= 1e6 ? `${(kg / 1e6).toFixed(1)}Mt`
    : kg >= 1e3 ? `${(kg / 1e3).toFixed(1)}t`
    : `${kg.toFixed(0)}kg`;
  const usdStr = usd >= 1e12 ? `$${(usd / 1e12).toFixed(1)}T`
    : usd >= 1e9 ? `$${(usd / 1e9).toFixed(1)}B`
    : usd >= 1e6 ? `$${(usd / 1e6).toFixed(1)}M`
    : usd >= 1e3 ? `$${(usd / 1e3).toFixed(0)}K`
    : `$${usd.toFixed(0)}`;
  return `${kgStr} (${usdStr})`;
}

const METAL_LABELS: Record<string, string> = {
  platinum: 'Pt', palladium: 'Pd', rhodium: 'Rh',
  iridium: 'Ir', osmium: 'Os', ruthenium: 'Ru', gold: 'Au',
};

type ColDef = {
  key: string;
  label: string;
  tooltip: string;
  sortable: boolean;
  render: (a: Asteroid) => string;
  className?: string;
};

const BASE_COLUMNS: ColDef[] = [
  { key: 'name', label: 'Name', tooltip: 'Asteroid designation', sortable: true,
    render: (a) => a.name },
  { key: 'composition_class', label: 'Class', tooltip: 'C=carbonaceous, S=silicaceous, M=metallic, V=basaltic, U=unknown', sortable: false,
    render: (a) => a.composition_class ?? '—' },
  { key: 'composition_confidence', label: 'Conf', tooltip: 'Classification confidence: 0%=uncertain (prior only), 100%=certain (confirmed taxonomy). Higher = more reliable resource estimates', sortable: true, className: 'col-confidence',
    render: (a) => {
      if (a.composition_confidence == null) return '—';
      return `${(a.composition_confidence * 100).toFixed(0)}%`;
    } },
  { key: 'diameter_estimated_km', label: 'D (km)', tooltip: 'Estimated diameter in km (measured or from absolute magnitude)', sortable: true,
    render: (a) => fmtN(a.diameter_estimated_km, 3) },
  { key: 'delta_v_km_s', label: 'Dv', tooltip: 'Delta-v mission cost proxy (km/s) — lower = easier to reach', sortable: true,
    render: (a) => fmtN(a.delta_v_km_s, 2) },
  { key: 'water_kg', label: 'Water', tooltip: 'Extractable water: mass × wt% × 60% yield. $500/kg cislunar propellant', sortable: false,
    render: (a) => { const inv = extractionInventory(a); return fmtKgUsd(inv.waterKg, inv.waterUsd); } },
  { key: 'metal_kg', label: 'Bulk Metals', tooltip: 'Extractable Fe/Ni/Co: mass × wt% × 50% yield. $50/kg in-orbit', sortable: false,
    render: (a) => { const inv = extractionInventory(a); return fmtKgUsd(inv.metalKg, inv.metalUsd); } },
];

const METAL_COLUMNS: ColDef[] = METALS.map((m) => ({
  key: `metal_${m}`,
  label: METAL_LABELS[m],
  tooltip: `${m.charAt(0).toUpperCase() + m.slice(1)}: 30% extraction yield. Spot $${(METAL_PRICES[m] / 1000).toFixed(0)}K/kg`,
  sortable: false,
  className: 'col-metal',
  render: (a: Asteroid) => {
    const inv = extractionInventory(a);
    const metal = inv.perMetal.find((pm) => pm.name === m);
    if (!metal || metal.kg < 0.01) return '—';
    return fmtKgUsd(metal.kg, metal.usd);
  },
}));

const COLUMNS: ColDef[] = [...BASE_COLUMNS, ...METAL_COLUMNS];

interface Props {
  asteroids: Asteroid[];
  total: number;
  loading: boolean;
  sort: string;
  order: 'asc' | 'desc';
  offset: number;
  limit: number;
  onSort: (col: string) => void;
  onNext: () => void;
  onPrev: () => void;
  onSelect: (a: Asteroid) => void;
}

export function AsteroidTable({
  asteroids, total, loading, sort, order, offset, limit,
  onSort, onNext, onPrev, onSelect,
}: Props) {
  return (
    <div className="asteroid-table-container">
      <table className="asteroid-table">
        <thead>
          <tr>
            {COLUMNS.map((col) => (
              <th
                key={col.key}
                onClick={col.sortable ? () => onSort(col.key) : undefined}
                className={`${col.sortable ? 'sortable' : ''} ${col.className ?? ''} has-tooltip`}
                data-tooltip={col.tooltip}
              >
                {col.label}
                {sort === col.key && (order === 'asc' ? ' ↑' : ' ↓')}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <tr><td colSpan={COLUMNS.length} className="loading">Loading...</td></tr>
          ) : asteroids.length === 0 ? (
            <tr><td colSpan={COLUMNS.length} className="loading">No results</td></tr>
          ) : (
            asteroids.map((a) => (
              <tr key={a.spkid} onClick={() => onSelect(a)} className={a.is_viable ? 'viable' : ''}>
                {COLUMNS.map((col) => (
                  <td key={col.key} className={col.className}>{col.render(a)}</td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
      <div className="pagination">
        <button onClick={onPrev} disabled={offset === 0}>Prev</button>
        <span>{offset + 1}–{Math.min(offset + limit, total)} of {total.toLocaleString()}</span>
        <button onClick={onNext} disabled={offset + limit >= total}>Next</button>
      </div>
    </div>
  );
}
