import { describe, expect, test } from 'vitest';
import type { Asteroid } from '../types/asteroid';
import {
  campaignProjection,
  DEFAULT_MISSION_KG,
  extractionLimitFraction,
  METAL_PRICES,
  missionScenario,
  OPERATIONAL_LIMIT,
} from './mining';

/** 175706 (1996 FG3) — values pulled from the live atlas API. */
function fg3(overrides: Partial<Asteroid> = {}): Asteroid {
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
    delta_v_km_s: 1.1530703732014953,
    tisserand_jupiter: 5.774506236253515,
    inclination_penalty: 0.00029551832116422915,
    orbital_precision_source: 'sbdb',
    surface_gravity_m_s2: 0.0003343535904878626,
    rotation_feasibility: 0.7971,
    regolith_likelihood: 0.7971,
    composition_class: 'C',
    composition_source: 'taxonomy',
    composition_confidence: 0.5607,
    resource_value_usd_per_kg: 38.11,
    specimen_value_per_kg: 90936.61,
    estimated_mass_kg: 1164489330121.877,
    mission_cost_usd_per_kg: 5628.700887221246,
    margin_per_kg: 80307.90911277875,
    break_even_kg: 3805.711096998153,
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

describe('extractionLimitFraction', () => {
  test('for 1996 FG3 returns 30% (operational ceiling binding)', () => {
    // rotation 3.6h is slow enough that f_rotation > 0.30; operational cap wins.
    expect(extractionLimitFraction(fg3())).toBeCloseTo(OPERATIONAL_LIMIT, 5);
  });

  test('falls back to operational limit when rotation data is missing', () => {
    expect(extractionLimitFraction(fg3({ rotation_hours: null }))).toBe(OPERATIONAL_LIMIT);
  });

  test('falls back to operational limit when surface gravity is missing', () => {
    expect(extractionLimitFraction(fg3({ surface_gravity_m_s2: null }))).toBe(OPERATIONAL_LIMIT);
  });

  test('falls back to operational limit when surface gravity is zero or negative', () => {
    expect(extractionLimitFraction(fg3({ surface_gravity_m_s2: 0 }))).toBe(OPERATIONAL_LIMIT);
    expect(extractionLimitFraction(fg3({ surface_gravity_m_s2: -1 }))).toBe(OPERATIONAL_LIMIT);
  });

  test('a fast rotator with low gravity is rotation-limited below 30%', () => {
    // Very fast spin + low gravity → centrifugal ≈ gravity → f_rotation small.
    const fast = fg3({ rotation_hours: 0.5, surface_gravity_m_s2: 1e-4 });
    expect(extractionLimitFraction(fast)).toBeLessThan(OPERATIONAL_LIMIT);
  });

  test('is always between 0 and 0.30', () => {
    expect(extractionLimitFraction(fg3())).toBeGreaterThanOrEqual(0);
    expect(extractionLimitFraction(fg3())).toBeLessThanOrEqual(OPERATIONAL_LIMIT);
  });
});

describe('missionScenario — greedy fill by $/kg', () => {
  test('1-ton mission picks ALL Rhodium first (highest $/kg)', () => {
    const s = missionScenario(fg3(), 1_000);
    expect(s.payloadKg).toBe(1_000);
    expect(s.mix[0].name).toBe('rhodium');
    expect(s.mix[0].kg).toBe(1_000);
    expect(s.revenue).toBe(1_000 * METAL_PRICES.rhodium);
  });

  test('10-ton mission still all Rhodium (FG3 has ~15 t mineable Rh)', () => {
    const s = missionScenario(fg3(), 10_000);
    expect(s.payloadKg).toBe(10_000);
    expect(s.mix).toHaveLength(1);
    expect(s.mix[0].name).toBe('rhodium');
    expect(s.mix[0].kg).toBe(10_000);
  });

  test('100-ton mission switches to Iridium once Rhodium exhausted', () => {
    const s = missionScenario(fg3(), 100_000);
    expect(s.payloadKg).toBe(100_000);
    expect(s.mix[0].name).toBe('rhodium');
    expect(s.mix[1].name).toBe('iridium');
    // FG3 mineable Rh after 30% cap: 50,970 × 0.30 ≈ 15,291 kg
    expect(s.mix[0].kg).toBeCloseTo(50_970 * OPERATIONAL_LIMIT, 0);
  });

  test('mission with no PGM yields empty payload + negative profit', () => {
    const sterile = fg3({
      ...Object.fromEntries(
        ['platinum', 'palladium', 'rhodium', 'iridium', 'osmium', 'ruthenium', 'gold']
          .map((m) => [`extractable_${m}_kg`, 0]),
      ),
    } as Partial<Asteroid>);
    const s = missionScenario(sterile, 100_000);
    expect(s.payloadKg).toBe(0);
    expect(s.revenue).toBe(0);
    expect(s.feasible).toBe(false);
    // Still pays the $300M fixed cost.
    expect(s.totalCost).toBeGreaterThanOrEqual(300_000_000);
    expect(s.profit).toBeLessThan(0);
  });

  test('greedy mix sums to payload mass', () => {
    const s = missionScenario(fg3(), 100_000);
    const totalKg = s.mix.reduce((sum, m) => sum + m.kg, 0);
    expect(totalKg).toBeCloseTo(s.payloadKg, 5);
  });
});

describe('campaignProjection — optimal stopping bounded by extraction limit', () => {
  test('FG3 runs ~4-5 missions before extraction limit binds', () => {
    const c = campaignProjection(fg3(), DEFAULT_MISSION_KG);
    expect(c.missionsRun).toBeGreaterThanOrEqual(3);
    expect(c.missionsRun).toBeLessThanOrEqual(6);
  });

  test('per-mission profit is monotonically non-increasing (greedy depletes high-$/kg first)', () => {
    const c = campaignProjection(fg3(), DEFAULT_MISSION_KG);
    for (let i = 1; i < c.missions.length; i++) {
      expect(c.missions[i].profit).toBeLessThanOrEqual(c.missions[i - 1].profit);
    }
  });

  test('total mineable PGM equals 30% of the atlas total_extractable_precious_kg', () => {
    const c = campaignProjection(fg3());
    // sum of all extractable_<metal>_kg in the FG3 fixture × 0.30
    const expected = (
      356_228.93 + 220_787.18 + 50_969.70 + 179_319.71 + 190_743.35 + 263_686.96 + 58_026.50
    ) * OPERATIONAL_LIMIT;
    expect(c.totalAvailableKg).toBeCloseTo(expected, 0);
  });

  test('campaign stops when next mission would be unprofitable OR inventory exhausted', () => {
    const c = campaignProjection(fg3());
    expect(['inventory_exhausted', 'profit_negative']).toContain(c.stoppedReason);
  });

  test('asteroid with no PGM → no_inventory reason', () => {
    const dry = fg3({
      ...Object.fromEntries(
        ['platinum', 'palladium', 'rhodium', 'iridium', 'osmium', 'ruthenium', 'gold']
          .map((m) => [`extractable_${m}_kg`, 0]),
      ),
    } as Partial<Asteroid>);
    const c = campaignProjection(dry);
    expect(c.stoppedReason).toBe('no_inventory');
    expect(c.missionsRun).toBe(0);
  });

  test('reports the binding extraction-limit fraction', () => {
    const c = campaignProjection(fg3());
    expect(c.extractionFraction).toBeCloseTo(OPERATIONAL_LIMIT, 5);
  });

  test('total profit < unconstrained greedy projection (extraction-limit cap is binding)', () => {
    // Old broken model: missions_supported=346, campaign_profit_usd=$240M
    // Unconstrained greedy: ~12 missions, ~$102B
    // Constrained (this model): ~4-5 missions, much less than $102B
    const c = campaignProjection(fg3());
    expect(c.totalProfit).toBeLessThan(102e9);
    // But still positive (FG3 has plenty of high-$/kg metal for a few missions).
    expect(c.totalProfit).toBeGreaterThan(0);
  });
});
