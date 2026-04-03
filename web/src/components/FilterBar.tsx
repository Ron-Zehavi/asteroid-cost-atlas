import type { Filters } from '../types/asteroid';

interface Props {
  filters: Filters;
  onUpdate: (patch: Partial<Filters>) => void;
}

export function FilterBar({ filters, onUpdate }: Props) {
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
          value={filters.dv_max ?? ''}
          onChange={(e) => {
            const v = e.target.value;
            onUpdate({ dv_max: v ? Number(v) : undefined });
          }}
        />
      </label>
    </div>
  );
}
