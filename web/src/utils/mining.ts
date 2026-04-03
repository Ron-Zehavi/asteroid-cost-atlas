/**
 * Mining economics computation helpers.
 * Mirrors the Python economic model constants for client-side calculations.
 */

import type { Asteroid } from '../types/asteroid';

// Mission cost constants (from economic.py)
const MISSION_MIN_COST = 300_000_000;
const SYSTEM_MASS_KG = 1_000;
const EXTRACTION_OVERHEAD = 5_000; // $/kg

// Resource weight percentages by class (from composition.py)
const WATER_WT_PCT: Record<string, number> = { C: 15.0, S: 0, M: 0, V: 0, U: 1.5 };
const METAL_WT_PCT: Record<string, number> = { C: 19.7, S: 28.9, M: 98.6, V: 15.0, U: 25.0 };
const WATER_YIELD = 0.60;
const METAL_YIELD = 0.50;
const WATER_PRICE = 500; // $/kg in cislunar space
const METAL_PRICE = 50;  // $/kg in orbit

// Precious metal spot prices (from composition.py)
export const METAL_PRICES: Record<string, number> = {
  platinum: 63_300, palladium: 47_870, rhodium: 299_000,
  iridium: 254_000, osmium: 12_860, ruthenium: 56_260, gold: 150_740,
};

export const METALS = ['platinum', 'palladium', 'rhodium', 'iridium', 'osmium', 'ruthenium', 'gold'] as const;

export interface ExtractionInventory {
  waterKg: number;
  waterUsd: number;
  metalKg: number;
  metalUsd: number;
  preciousKg: number;
  preciousUsd: number;
  perMetal: { name: string; kg: number; usd: number }[];
}

export interface MissionScenario {
  payloadKg: number;     // actual payload (capped at available)
  revenue: number;
  transportCost: number;
  fixedCost: number;
  totalCost: number;
  profit: number;
  feasible: boolean;     // payload > 0 and margin positive
}

/** Compute total extractable resources from an asteroid. */
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
    const extractKg = `extractable_${m}_kg` as keyof Asteroid;
    const kg = (a[extractKg] as number | null) ?? (mass * ppm / 1e6 * 0.30);
    const usd = kg * METAL_PRICES[m];
    return { name: m, kg, usd };
  });

  const preciousKg = perMetal.reduce((s, m) => s + m.kg, 0);
  const preciousUsd = perMetal.reduce((s, m) => s + m.usd, 0);

  return { waterKg, waterUsd, metalKg, metalUsd, preciousKg, preciousUsd, perMetal };
}

/** Compute profit for a mission returning `targetKg` of refined precious metals. */
export function missionScenario(a: Asteroid, targetKg: number): MissionScenario {
  const maxPrecious = a.total_extractable_precious_kg ?? 0;
  const payloadKg = Math.min(targetKg, maxPrecious);
  const transport = a.mission_cost_usd_per_kg ?? Infinity;
  const specimenValue = a.specimen_value_per_kg ?? 0;

  const revenue = payloadKg * specimenValue;
  const fixedCost = MISSION_MIN_COST + SYSTEM_MASS_KG * transport;
  const transportCost = payloadKg * transport;
  const extractionCost = payloadKg * EXTRACTION_OVERHEAD;
  const totalCost = fixedCost + transportCost + extractionCost;
  const profit = revenue - totalCost;

  return {
    payloadKg,
    revenue,
    transportCost: transportCost + extractionCost,
    fixedCost,
    totalCost,
    profit,
    feasible: payloadKg > 0 && profit > 0,
  };
}
