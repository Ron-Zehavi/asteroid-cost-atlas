import { useMemo, useState } from 'react';
import type { Filters } from '../types/asteroid';

interface Props {
  filters: Filters;
  onUpdate: (patch: Partial<Filters>) => void;
  onClear: () => void;
}

const ORBIT_CLASSES: { value: string; label: string }[] = [
  { value: 'AMO', label: 'Amor (NEA)' },
  { value: 'APO', label: 'Apollo (NEA)' },
  { value: 'ATE', label: 'Aten (NEA)' },
  { value: 'IEO', label: 'Atira (NEA)' },
  { value: 'MCA', label: 'Mars-crosser' },
  { value: 'IMB', label: 'Inner main belt' },
  { value: 'MBA', label: 'Main belt' },
  { value: 'OMB', label: 'Outer main belt' },
  { value: 'TJN', label: 'Jupiter trojan' },
  { value: 'CEN', label: 'Centaur' },
  { value: 'TNO', label: 'Trans-Neptunian' },
];

function numOrUndef(v: string): number | undefined {
  return v === '' ? undefined : Number(v);
}

function isRangeInverted(min: number | undefined, max: number | undefined): boolean {
  return min !== undefined && max !== undefined && min > max;
}

export function FilterBar({ filters, onUpdate, onClear }: Props) {
  const [advancedOpen, setAdvancedOpen] = useState(false);

  const activeCount = useMemo(() => {
    let n = 0;
    if (filters.neo) n++;
    if (filters.is_viable !== undefined) n++;
    if (filters.composition_class) n++;
    if (filters.orbit_class) n++;
    if (filters.dv_min !== undefined) n++;
    if (filters.dv_max !== undefined && filters.dv_max !== 3) n++; // 3 is the default
    if (filters.inclination_max !== undefined) n++;
    if (filters.tisserand_min !== undefined) n++;
    if (filters.tisserand_max !== undefined) n++;
    if (filters.diameter_min !== undefined) n++;
    if (filters.diameter_max !== undefined) n++;
    return n;
  }, [filters]);

  const tisserandInverted = isRangeInverted(filters.tisserand_min, filters.tisserand_max);
  const diameterInverted = isRangeInverted(filters.diameter_min, filters.diameter_max);
  const dvInverted = isRangeInverted(filters.dv_min, filters.dv_max);

  return (
    <div className="filter-bar">
      <select
        value={filters.composition_class ?? ''}
        onChange={(e) => onUpdate({ composition_class: e.target.value || undefined })}
      >
        <option value="">All Classes</option>
        <option value="C">C (Carbonaceous)</option>
        <option value="S">S (Silicaceous)</option>
        <option value="M">M (Metallic)</option>
        <option value="V">V (Basaltic)</option>
        <option value="U">U (Unknown)</option>
      </select>

      <select
        value={filters.neo ?? ''}
        onChange={(e) => onUpdate({ neo: e.target.value || undefined })}
      >
        <option value="">All NEO</option>
        <option value="Y">NEO Only</option>
        <option value="N">Non-NEO</option>
      </select>

      <select
        value={filters.is_viable === undefined ? '' : String(filters.is_viable)}
        onChange={(e) => {
          const v = e.target.value;
          onUpdate({ is_viable: v === '' ? undefined : v === 'true' });
        }}
      >
        <option value="">All Viability</option>
        <option value="true">Viable Only</option>
        <option value="false">Not Viable</option>
      </select>

      <label className="filter-range">
        Max Dv:
        <input
          type="number"
          min={0}
          step={0.5}
          placeholder="km/s"
          className={dvInverted ? 'filter-input-error' : ''}
          value={filters.dv_max ?? ''}
          onChange={(e) => onUpdate({ dv_max: numOrUndef(e.target.value) })}
        />
      </label>

      <button
        type="button"
        className="filter-toggle"
        onClick={() => setAdvancedOpen((v) => !v)}
        aria-expanded={advancedOpen}
      >
        Advanced{activeCount > 0 ? ` (${activeCount})` : ''} {advancedOpen ? '▴' : '▾'}
      </button>

      {activeCount > 0 && (
        <button
          type="button"
          className="filter-clear"
          onClick={onClear}
          title="Reset all filters to defaults"
        >Clear</button>
      )}

      {advancedOpen && (
        <>
          <select
            value={filters.orbit_class ?? ''}
            onChange={(e) => onUpdate({ orbit_class: e.target.value || undefined })}
            title="Dynamical orbit class (Amor/Apollo/Aten = near-Earth, MBA = main belt, etc.)"
          >
            <option value="">All Orbits</option>
            {ORBIT_CLASSES.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>

          <label className="filter-range" title="Inclination cap, degrees from ecliptic">
            Max i°:
            <input
              type="number"
              min={0}
              max={180}
              step={1}
              placeholder="deg"
              value={filters.inclination_max ?? ''}
              onChange={(e) => onUpdate({ inclination_max: numOrUndef(e.target.value) })}
            />
          </label>

          <label className="filter-range" title="Tisserand parameter w.r.t. Jupiter. NEAs: T_J > 3. Comets: T_J < 3.">
            T_J:
            <input
              type="number"
              min={0}
              step={0.1}
              placeholder="min"
              className={tisserandInverted ? 'filter-input-error' : ''}
              value={filters.tisserand_min ?? ''}
              onChange={(e) => onUpdate({ tisserand_min: numOrUndef(e.target.value) })}
            />
            <input
              type="number"
              min={0}
              step={0.1}
              placeholder="max"
              className={tisserandInverted ? 'filter-input-error' : ''}
              value={filters.tisserand_max ?? ''}
              onChange={(e) => onUpdate({ tisserand_max: numOrUndef(e.target.value) })}
            />
          </label>

          <label className="filter-range" title="Estimated diameter (km)">
            D (km):
            <input
              type="number"
              min={0}
              step={0.1}
              placeholder="min"
              className={diameterInverted ? 'filter-input-error' : ''}
              value={filters.diameter_min ?? ''}
              onChange={(e) => onUpdate({ diameter_min: numOrUndef(e.target.value) })}
            />
            <input
              type="number"
              min={0}
              step={0.1}
              placeholder="max"
              className={diameterInverted ? 'filter-input-error' : ''}
              value={filters.diameter_max ?? ''}
              onChange={(e) => onUpdate({ diameter_max: numOrUndef(e.target.value) })}
            />
          </label>

          {(tisserandInverted || diameterInverted || dvInverted) && (
            <span className="filter-warning">⚠ min &gt; max — no results</span>
          )}
        </>
      )}
    </div>
  );
}
