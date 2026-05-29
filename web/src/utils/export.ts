import type { Asteroid } from '../types/asteroid';

const EXPORT_COLUMNS: (keyof Asteroid)[] = [
  'spkid', 'name',
  'a_au', 'eccentricity', 'inclination_deg', 'moid_au',
  'long_asc_node_deg', 'arg_perihelion_deg', 'mean_anomaly_deg', 'epoch_mjd',
  'orbit_class', 'neo', 'pha',
  'abs_magnitude', 'diameter_estimated_km', 'diameter_source',
  'rotation_hours', 'albedo', 'spectral_type',
  'delta_v_km_s', 'tisserand_jupiter', 'inclination_penalty',
  'orbital_precision_source',
  'surface_gravity_m_s2', 'rotation_feasibility', 'regolith_likelihood',
  'composition_class', 'composition_source', 'composition_confidence',
  'is_viable',
];

function csvCell(v: unknown): string {
  if (v == null) return '';
  const s = typeof v === 'boolean' ? (v ? 'true' : 'false') : String(v);
  if (s.includes(',') || s.includes('"') || s.includes('\n')) {
    return `"${s.replace(/"/g, '""')}"`;
  }
  return s;
}

function pickColumns(a: Asteroid): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const col of EXPORT_COLUMNS) out[col] = a[col];
  return out;
}

function download(filename: string, content: string, mime: string): void {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function timestamp(): string {
  return new Date().toISOString().slice(0, 10);
}

export function exportAsteroidsCsv(rows: Asteroid[]): void {
  const header = EXPORT_COLUMNS.join(',');
  const lines = rows.map((r) =>
    EXPORT_COLUMNS.map((c) => csvCell(r[c])).join(','),
  );
  download(`asteroid-atlas_${timestamp()}.csv`, [header, ...lines].join('\n'), 'text/csv');
}

export function exportAsteroidsJson(rows: Asteroid[]): void {
  const payload = JSON.stringify(rows.map(pickColumns), null, 2);
  download(`asteroid-atlas_${timestamp()}.json`, payload, 'application/json');
}
