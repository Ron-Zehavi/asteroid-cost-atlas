import { describe, expect, test } from 'vitest';
import type { Asteroid } from '../types/asteroid';
import {
  EXPORT_COLUMNS,
  UTF8_BOM,
  csvCell,
  pickExportColumns,
  serializeAsteroidsCsv,
  serializeAsteroidsJson,
} from './export';

function makeAsteroid(overrides: Partial<Asteroid> = {}): Asteroid {
  return {
    spkid: 1,
    name: 'Test 1',
    a_au: 2.5,
    eccentricity: 0.1,
    inclination_deg: 5,
    long_asc_node_deg: null,
    arg_perihelion_deg: null,
    mean_anomaly_deg: null,
    epoch_mjd: null,
    abs_magnitude: 18,
    diameter_estimated_km: 1.0,
    diameter_source: 'measured',
    rotation_hours: 6,
    albedo: 0.1,
    neo: 'Y',
    pha: 'N',
    orbit_class: 'APO',
    moid_au: 0.03,
    spectral_type: 'C',
    delta_v_km_s: 3,
    tisserand_jupiter: 5,
    inclination_penalty: 0.01,
    orbital_precision_source: 'sbdb',
    surface_gravity_m_s2: 1e-4,
    rotation_feasibility: 0.5,
    regolith_likelihood: 0.5,
    composition_class: 'C',
    composition_source: 'taxonomy',
    composition_confidence: 0.7,
    resource_value_usd_per_kg: null,
    specimen_value_per_kg: null,
    estimated_mass_kg: null,
    mission_cost_usd_per_kg: null,
    margin_per_kg: null,
    break_even_kg: null,
    is_viable: true,
    missions_supported: null,
    mission_profit_usd: null,
    campaign_profit_usd: null,
    economic_score: null,
    economic_priority_rank: null,
    total_extractable_precious_kg: null,
    total_precious_value_usd: null,
    ...overrides,
  };
}

describe('csvCell', () => {
  test('empty for null/undefined', () => {
    expect(csvCell(null)).toBe('');
    expect(csvCell(undefined)).toBe('');
  });

  test('passes through plain strings/numbers', () => {
    expect(csvCell('Ceres')).toBe('Ceres');
    expect(csvCell(2.5)).toBe('2.5');
    expect(csvCell(0)).toBe('0');
  });

  test('serializes booleans as lowercase strings', () => {
    expect(csvCell(true)).toBe('true');
    expect(csvCell(false)).toBe('false');
  });

  test('quotes values containing commas', () => {
    expect(csvCell('a, b')).toBe('"a, b"');
  });

  test('doubles internal quotes per RFC 4180', () => {
    expect(csvCell('she said "hi"')).toBe('"she said ""hi"""');
  });

  test('quotes values containing newlines', () => {
    expect(csvCell('line1\nline2')).toBe('"line1\nline2"');
  });
});

describe('pickExportColumns', () => {
  test('includes every EXPORT_COLUMN key', () => {
    const a = makeAsteroid({ name: 'X', delta_v_km_s: 3 });
    const out = pickExportColumns(a);
    for (const k of EXPORT_COLUMNS) expect(k in out).toBe(true);
    expect(out.name).toBe('X');
    expect(out.delta_v_km_s).toBe(3);
  });

  test('does NOT include economic ($) columns', () => {
    const a = makeAsteroid({ campaign_profit_usd: 999 });
    const out = pickExportColumns(a);
    expect('campaign_profit_usd' in out).toBe(false);
    expect('mission_profit_usd' in out).toBe(false);
    expect('break_even_kg' in out).toBe(false);
    expect('specimen_value_per_kg' in out).toBe(false);
  });
});

describe('serializeAsteroidsCsv', () => {
  test('begins with UTF-8 BOM', () => {
    const csv = serializeAsteroidsCsv([makeAsteroid()]);
    expect(csv.startsWith(UTF8_BOM)).toBe(true);
    expect(csv.charCodeAt(0)).toBe(0xfeff);
  });

  test('header row matches EXPORT_COLUMNS order', () => {
    const csv = serializeAsteroidsCsv([]);
    const header = csv.slice(UTF8_BOM.length).split('\n')[0];
    expect(header).toBe(EXPORT_COLUMNS.join(','));
  });

  test('escapes asteroid names with commas (e.g. \"175706 (1996 FG3)\")', () => {
    const csv = serializeAsteroidsCsv([makeAsteroid({ name: '175706 (1996, FG3)' })]);
    const dataRow = csv.slice(UTF8_BOM.length).split('\n')[1];
    expect(dataRow).toContain('"175706 (1996, FG3)"');
  });

  test('non-ASCII names round-trip (no mangling, BOM ensures Excel reads UTF-8)', () => {
    const csv = serializeAsteroidsCsv([makeAsteroid({ name: 'Hokkaidō Ångström' })]);
    expect(csv).toContain('Hokkaidō Ångström');
  });

  test('renders null fields as empty cells', () => {
    const csv = serializeAsteroidsCsv([makeAsteroid({ albedo: null, rotation_hours: null })]);
    const dataRow = csv.slice(UTF8_BOM.length).split('\n')[1];
    // 30 columns × 1 row → at least one ",," pair from null fields
    expect(dataRow).toContain(',,');
  });
});

describe('serializeAsteroidsJson', () => {
  test('produces valid JSON array of objects', () => {
    const json = serializeAsteroidsJson([makeAsteroid(), makeAsteroid({ spkid: 2 })]);
    const parsed = JSON.parse(json);
    expect(Array.isArray(parsed)).toBe(true);
    expect(parsed).toHaveLength(2);
    expect(parsed[0].spkid).toBe(1);
    expect(parsed[1].spkid).toBe(2);
  });

  test('excludes economic columns', () => {
    const json = serializeAsteroidsJson([makeAsteroid({ campaign_profit_usd: 12345 })]);
    expect(json).not.toContain('campaign_profit_usd');
    expect(json).not.toContain('break_even_kg');
  });
});
