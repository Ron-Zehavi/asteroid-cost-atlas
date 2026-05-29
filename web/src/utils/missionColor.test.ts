import { describe, expect, test } from 'vitest';
import type { Asteroid } from '../types/asteroid';
import { campaignTint, viabilityTint } from './missionColor';

function fg3Like(overrides: Partial<Asteroid> = {}): Asteroid {
  return {
    spkid: 20175706,
    name: '175706 (1996 FG3)',
    a_au: 1.055,
    eccentricity: 0.3501,
    inclination_deg: 1.97,
    long_asc_node_deg: 299.47,
    arg_perihelion_deg: 24.06,
    mean_anomaly_deg: 36.65,
    epoch_mjd: 2461000.5,
    abs_magnitude: 18.31,
    diameter_estimated_km: 1.196,
    diameter_source: 'measured',
    rotation_hours: 3.5942,
    albedo: 0.072,
    neo: 'Y',
    pha: 'Y',
    orbit_class: 'APO',
    moid_au: 0.0281,
    spectral_type: 'C',
    delta_v_km_s: 1.153,
    tisserand_jupiter: 5.77,
    inclination_penalty: 0.0003,
    orbital_precision_source: 'sbdb',
    surface_gravity_m_s2: 0.0003343,
    rotation_feasibility: 0.7971,
    regolith_likelihood: 0.7971,
    composition_class: 'C',
    composition_source: 'taxonomy',
    composition_confidence: 0.5607,
    resource_value_usd_per_kg: 38.11,
    specimen_value_per_kg: 90936.61,
    estimated_mass_kg: 1164489330121.877,
    mission_cost_usd_per_kg: 5628.7,
    margin_per_kg: 80307.9,
    break_even_kg: 3805.7,
    is_viable: true,
    missions_supported: 346,
    mission_profit_usd: 693131,
    campaign_profit_usd: 239823335,
    economic_score: 90209847743,
    economic_priority_rank: 107988,
    total_extractable_precious_kg: 1319762.34,
    total_precious_value_usd: 119940423234,
    extractable_platinum_kg: 356228.93,
    extractable_palladium_kg: 220787.18,
    extractable_rhodium_kg: 50969.70,
    extractable_iridium_kg: 179319.71,
    extractable_osmium_kg: 190743.35,
    extractable_ruthenium_kg: 263686.96,
    extractable_gold_kg: 58026.50,
    ...overrides,
  };
}

const noPgm = {
  extractable_platinum_kg: 0, extractable_palladium_kg: 0,
  extractable_rhodium_kg: 0, extractable_iridium_kg: 0,
  extractable_osmium_kg: 0, extractable_ruthenium_kg: 0,
  extractable_gold_kg: 0,
};

describe('viabilityTint', () => {
  test('FG3-like asteroid is colored green (campaign yields profit)', () => {
    expect(viabilityTint(fg3Like())).toBe('#44dd66');
  });

  test('asteroid with no PGM is grey', () => {
    expect(viabilityTint(fg3Like(noPgm))).toBe('#888899');
  });

  test('asteroid with no transport-cost data is grey (no campaign possible)', () => {
    expect(viabilityTint(fg3Like({ mission_cost_usd_per_kg: null }))).toBe('#888899');
  });
});

describe('campaignTint', () => {
  test('FG3-like asteroid returns a non-grey tinted color', () => {
    const tint = campaignTint(fg3Like());
    expect(tint).not.toBe('#555566');
    expect(tint).toMatch(/^rgb\(\d+,\d+,\d+\)$/);
  });

  test('asteroid with no profit returns the dim grey baseline', () => {
    expect(campaignTint(fg3Like(noPgm))).toBe('#555566');
  });

  test('larger profit produces a warmer color (higher R)', () => {
    const big = fg3Like();
    const small = fg3Like({
      // Scale all extractable down 100× so campaign profit is much smaller.
      extractable_platinum_kg: 3562, extractable_palladium_kg: 2208,
      extractable_rhodium_kg: 510, extractable_iridium_kg: 1793,
      extractable_osmium_kg: 1907, extractable_ruthenium_kg: 2637,
      extractable_gold_kg: 580,
    });
    const bigR = parseInt(campaignTint(big).match(/rgb\((\d+)/)![1], 10);
    const smallR = parseInt(campaignTint(small).match(/rgb\((\d+)/)![1], 10);
    expect(bigR).toBeGreaterThan(smallR);
  });
});
