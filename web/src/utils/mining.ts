/**
 * Mission economics computation helpers.
 *
 * Mirrors the Python economic model constants for client-side calculations,
 * but applies three corrections to the pipeline's atlas columns:
 *
 *  1. Greedy fill by $/kg per mission — payload picks highest-value metal
 *     first (Rh → Ir → Au → Pt → Ru → Pd → Os), not the meaningless mass-
 *     averaged "specimen_value_per_kg" the atlas uses.
 *  2. Extraction limit — cap mineable inventory at min(f_rotation, 40%, 30%)
 *     of the per-metal yield, since processing 100% of an asteroid would
 *     spin-shed / structurally disrupt the rubble pile.
 *  3. Optimal stopping — campaign runs until either inventory exhausts or
 *     the next mission would be unprofitable.
 *
 * Everything here is still an upper-bound estimate. See `MODEL_CAVEATS`.
 */

import type { Asteroid } from '../types/asteroid';

// Mission cost constants (from scoring/economic.py)
const MISSION_MIN_COST = 300_000_000;
const SYSTEM_MASS_KG = 1_000;
const EXTRACTION_OVERHEAD = 5_000; // $/kg

// Resource weight percentages by class (from scoring/composition.py).
// Used by `extractionInventory` for the table's bulk water/metals columns.
const WATER_WT_PCT: Record<string, number> = { C: 15.0, S: 0, M: 0, V: 0, U: 1.5 };
const METAL_WT_PCT: Record<string, number> = { C: 19.7, S: 28.9, M: 98.6, V: 15.0, U: 25.0 };
const WATER_YIELD = 0.60;
const METAL_YIELD = 0.50;
const WATER_PRICE = 500; // $/kg in cislunar space
const METAL_PRICE = 50;  // $/kg in orbit

// Precious metal spot prices ($/kg)
export const METAL_PRICES: Record<string, number> = {
  platinum: 63_300, palladium: 47_870, rhodium: 299_000,
  iridium: 254_000, osmium: 12_860, ruthenium: 56_260, gold: 150_740,
};

export const METALS = ['platinum', 'palladium', 'rhodium', 'iridium', 'osmium', 'ruthenium', 'gold'] as const;

/** Per-mission payload size used as default for the campaign projection. */
export const DEFAULT_MISSION_KG = 100_000;

/** Surface-floor extraction caps that bound `extractionLimitFraction`. */
export const STRUCTURAL_LIMIT = 0.40;     // rubble-pile literature
export const OPERATIONAL_LIMIT = 0.30;    // engineering judgment

export const MODEL_CAVEATS = [
  'Upper-bound estimate. Real mining is far more constrained than this.',
  'Assumes selective greedy extraction at spot prices.',
  'Ignores market saturation (returning 100s of t of Rh would crash its price).',
  'Ignores R&D, capex amortization, regulation, and engineering uncertainty.',
  'Extraction limit caps inventory at ~30% of asteroid mass before structural failure.',
] as const;

// ───────────────────────── Existing surface (table) ─────────────────────────

export interface ExtractionInventory {
  waterKg: number;
  waterUsd: number;
  metalKg: number;
  metalUsd: number;
  preciousKg: number;
  preciousUsd: number;
  perMetal: { name: string; kg: number; usd: number }[];
}

/** TOTAL extractable resources from the asteroid (does NOT apply the
 *  extraction-limit cap). Used by the main asteroid table to display
 *  upper-bound water/bulk/precious inventories. */
export function extractionInventory(a: Asteroid): ExtractionInventory {
  const mass = a.estimated_mass_kg ?? 0;
  const cls = a.composition_class ?? 'U';

  const waterKg = mass * (WATER_WT_PCT[cls] ?? 0) / 100 * WATER_YIELD;
  const waterUsd = waterKg * WATER_PRICE;

  const metalKg = mass * (METAL_WT_PCT[cls] ?? 0) / 100 * METAL_YIELD;
  const metalUsd = metalKg * METAL_PRICE;

  const perMetal = METALS.map((m) => {
    const ppmKey = `${m}_ppm` as keyof Asteroid;
    const ppm = (a[ppmKey] as number | null) ?? 0;
    const extractKey = `extractable_${m}_kg` as keyof Asteroid;
    const kg = (a[extractKey] as number | null) ?? (mass * ppm / 1e6 * 0.30);
    const usd = kg * METAL_PRICES[m];
    return { name: m, kg, usd };
  });

  const preciousKg = perMetal.reduce((s, m) => s + m.kg, 0);
  const preciousUsd = perMetal.reduce((s, m) => s + m.usd, 0);

  return { waterKg, waterUsd, metalKg, metalUsd, preciousKg, preciousUsd, perMetal };
}

// ───────────────────────── New mission/campaign math ─────────────────────────

/** Per-metal mineable inventory in kg (after extraction-limit cap). */
interface MetalAvailability {
  name: string;
  kg: number;
  pricePerKg: number;
}

export interface ExtractedMetal {
  name: string;
  kg: number;
  usd: number;
}

export interface MissionScenario {
  payloadKg: number;
  mix: ExtractedMetal[];
  revenue: number;
  fixedCost: number;
  variableCost: number;
  totalCost: number;
  profit: number;
  feasible: boolean;
}

export interface CampaignProjection {
  missions: MissionScenario[];
  totalRevenue: number;
  totalCost: number;
  totalProfit: number;
  missionsRun: number;
  stoppedReason: 'inventory_exhausted' | 'profit_negative' | 'no_inventory';
  extractionFraction: number;   // f_max applied
  totalAvailableKg: number;     // after f_max, summed across all PGM
}

/**
 * Fraction of the asteroid mass that can be mined without destabilizing the
 * rubble pile, taking the minimum of:
 *   f_rotation    — physics: 1 − (centrifugal acceleration / surface gravity)
 *   f_structural  — Sanchez & Scheeres (2014), rubble-pile disruption ≈ 40%
 *   f_operational — engineering judgment, infrastructure cap ≈ 30%
 *
 * When rotation data is missing, falls back to the operational limit so the
 * scenario isn't silently uncapped.
 */
export function extractionLimitFraction(a: Asteroid): number {
  if (
    !a.rotation_hours
    || !a.diameter_estimated_km
    || a.surface_gravity_m_s2 == null
    || a.surface_gravity_m_s2 <= 0
  ) {
    return OPERATIONAL_LIMIT;
  }
  const omega = (2 * Math.PI) / (a.rotation_hours * 3600);
  const radius = (a.diameter_estimated_km * 1000) / 2;
  const centrifugal = omega * omega * radius;
  const fRotation = Math.max(0, 1 - centrifugal / a.surface_gravity_m_s2);
  return Math.min(fRotation, STRUCTURAL_LIMIT, OPERATIONAL_LIMIT);
}

/** Mineable PGM inventory, sorted by $/kg descending. */
function availableInventory(a: Asteroid): MetalAvailability[] {
  const fMax = extractionLimitFraction(a);
  const items: MetalAvailability[] = [];
  for (const name of METALS) {
    const extractKey = `extractable_${name}_kg` as keyof Asteroid;
    const rawKg = (a[extractKey] as number | null) ?? 0;
    if (rawKg <= 0) continue;
    items.push({ name, kg: rawKg * fMax, pricePerKg: METAL_PRICES[name] });
  }
  return items.sort((a, b) => b.pricePerKg - a.pricePerKg);
}

/** MUTATES `inv`. Picks up to `targetKg` from the available inventory,
 *  highest-priced metals first. Returns the resulting mission economics. */
function takeGreedy(
  inv: MetalAvailability[],
  targetKg: number,
  transportPerKg: number,
): MissionScenario {
  let remaining = targetKg;
  const mix: ExtractedMetal[] = [];
  let revenue = 0;

  for (const m of inv) {
    if (remaining <= 0) break;
    if (m.kg <= 0) continue;
    const take = Math.min(remaining, m.kg);
    if (take > 0) {
      const usd = take * m.pricePerKg;
      mix.push({ name: m.name, kg: take, usd });
      revenue += usd;
      remaining -= take;
      m.kg -= take;
    }
  }

  const payloadKg = targetKg - remaining;
  const fixedCost = MISSION_MIN_COST + SYSTEM_MASS_KG * transportPerKg;
  const variableCost = payloadKg * (transportPerKg + EXTRACTION_OVERHEAD);
  const totalCost = fixedCost + variableCost;
  const profit = revenue - totalCost;

  return {
    payloadKg, mix, revenue,
    fixedCost, variableCost, totalCost,
    profit,
    feasible: payloadKg > 0 && profit > 0,
  };
}

/** Single mission economics (no campaign decay). Useful for the "1 t / 10 t /
 *  100 t scenario" table — each scenario starts from a fresh inventory. */
export function missionScenario(a: Asteroid, targetKg: number): MissionScenario {
  const transport = a.mission_cost_usd_per_kg ?? Infinity;
  return takeGreedy(availableInventory(a), targetKg, transport);
}

/** Run successive missions of `missionSize` until inventory is exhausted OR
 *  the next mission would not be profitable. The extraction-limit cap is
 *  applied to the initial inventory, so it naturally bounds the campaign
 *  size from above — if the cap allows fewer missions than the optimal-
 *  stopping cutoff, the cap wins. */
export function campaignProjection(
  a: Asteroid,
  missionSize: number = DEFAULT_MISSION_KG,
): CampaignProjection {
  const fMax = extractionLimitFraction(a);
  const inv = availableInventory(a);
  const totalAvailableKg = inv.reduce((s, m) => s + m.kg, 0);
  const empty = {
    missions: [], totalRevenue: 0, totalCost: 0, totalProfit: 0,
    missionsRun: 0, extractionFraction: fMax, totalAvailableKg,
  };

  if (inv.length === 0 || a.mission_cost_usd_per_kg == null) {
    return { ...empty, stoppedReason: 'no_inventory' };
  }

  const transport = a.mission_cost_usd_per_kg;
  const missions: MissionScenario[] = [];
  let stoppedReason: CampaignProjection['stoppedReason'] = 'inventory_exhausted';

  while (inv.some((m) => m.kg > 0.01)) {
    const m = takeGreedy(inv, missionSize, transport);
    if (m.payloadKg <= 0) { stoppedReason = 'inventory_exhausted'; break; }
    if (m.profit <= 0)    { stoppedReason = 'profit_negative';     break; }
    missions.push(m);
  }

  const totalRevenue = missions.reduce((s, m) => s + m.revenue, 0);
  const totalCost = missions.reduce((s, m) => s + m.totalCost, 0);
  const totalProfit = totalRevenue - totalCost;

  return {
    missions, totalRevenue, totalCost, totalProfit,
    missionsRun: missions.length, stoppedReason,
    extractionFraction: fMax, totalAvailableKg,
  };
}
