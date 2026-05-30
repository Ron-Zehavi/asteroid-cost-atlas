/** Per-asteroid color helpers for the scene's `Color: Viability` and
 *  `Color: Campaign Profit` modes. Both honour the new greedy + extraction-
 *  limit + optimal-stopping model from `mining.ts`. */

import type { Asteroid } from '../types/asteroid';
import { campaignProjection } from './mining';

/** Greenish if the new model finds ≥1 profitable mission; dim grey otherwise. */
export function viabilityTint(a: Asteroid): string {
  const c = campaignProjection(a);
  return c.missionsRun > 0 && c.totalProfit > 0 ? '#44dd66' : '#888899';
}

/** Log-scaled gradient from dim grey ($0–1B) → amber ($1B–$10B) → bright
 *  orange ($10B+). Designed so the difference between a marginal target
 *  ($1B campaign) and a top-tier one ($30B+) is visually obvious. */
export function campaignTint(a: Asteroid): string {
  const c = campaignProjection(a);
  if (c.missionsRun === 0 || c.totalProfit <= 0) return '#555566';

  const t = Math.min(1, Math.log10(c.totalProfit) / 11); // log10(1e11) = 11 → cap
  // grey → amber → bright orange
  const r = Math.round(85 + t * 170);
  const g = Math.round(85 + t * 95);
  const b = Math.round(85 - t * 80);
  return `rgb(${r},${g},${b})`;
}
