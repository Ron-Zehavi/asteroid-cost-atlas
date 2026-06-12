/**
 * Spotlight Mode: shared flight state and the storytelling logic for a
 * featured asteroid — which number leads, how the composition reads,
 * what the diameter compares to. All numbers come straight from the
 * atlas fields; nothing here invents data.
 */
import type { Asteroid } from '../types/asteroid';
import { DEFAULT_MISSION_KG, campaignProjection } from './mining';
import {
  SPOTLIGHT_ARRIVAL_FACTOR,
  SPOTLIGHT_MIN_ARRIVAL_DIST,
  SPOTLIGHT_ROCK_FRACTION,
} from './sceneConstants';

export const KM_PER_AU = 149_597_870.7;

/** Shared between CameraFlight (writer) and OrbitLine / SpotlightAsteroid (readers).
 *  Module-level so it survives React StrictMode's double-mount, same as
 *  focusOverrideShared in SolarSystem. progress runs 0→1 (eased) per flight. */
export const spotlightFlight = { active: false, progress: 1 };

export function easeInOutCubic(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

/** Camera's final distance from the asteroid at the end of the flight. */
export function spotlightArrivalDistance(targetDistFromSun: number): number {
  return Math.max(SPOTLIGHT_MIN_ARRIVAL_DIST, targetDistFromSun * SPOTLIGHT_ARRIVAL_FACTOR);
}

/** Rendered rock radius: a fixed fraction of the arrival framing, never
 *  smaller than the (already OBJECT_SCALE-exaggerated) cloud radius. */
export function spotlightRockRadius(arrivalDist: number, cloudRadius: number): number {
  return Math.max(arrivalDist * SPOTLIGHT_ROCK_FRACTION, cloudRadius);
}

export function fmtUsdShort(n: number): string {
  const abs = Math.abs(n);
  const sign = n < 0 ? '-' : '';
  if (abs >= 1e12) return `${sign}$${(abs / 1e12).toFixed(2)}T`;
  if (abs >= 1e9) return `${sign}$${(abs / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${sign}$${(abs / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `${sign}$${(abs / 1e3).toFixed(0)}K`;
  return `${sign}$${abs.toFixed(0)}`;
}

/** Honest size anchor for a diameter in km. */
export function sizeComparison(diamKm: number | null | undefined): string | null {
  if (diamKm == null || !isFinite(diamKm) || diamKm <= 0) return null;
  if (diamKm < 0.05) return 'about the size of a large building';
  if (diamKm < 0.15) return 'about the size of a football stadium';
  if (diamKm < 0.5) return 'a few city blocks across';
  if (diamKm < 2) return 'the size of a small town';
  if (diamKm < 5) return 'about the width of Manhattan';
  if (diamKm < 15) return 'roughly Mount Everest, floating free';
  if (diamKm < 60) return 'wider than the city of London';
  if (diamKm < 300) return 'the size of a small country';
  return 'a small world of its own';
}

const COMPOSITION_STORY: Record<string, { title: string; blurb: string }> = {
  C: {
    title: 'C-type — carbon-rich',
    blurb: 'Dark, primitive rock. The class most likely to carry water — the rocket fuel of deep space.',
  },
  S: {
    title: 'S-type — stony',
    blurb: 'Silicate rock with metal veined through it. The most common bright asteroid.',
  },
  M: {
    title: 'M-type — metal-rich',
    blurb: 'Possibly the exposed core fragment of a shattered protoplanet. Where the platinum is.',
  },
  V: {
    title: 'V-type — basaltic',
    blurb: 'Volcanic crust, almost certainly a chip knocked off Vesta in an ancient impact.',
  },
  U: {
    title: 'Unclassified',
    blurb: 'No spectral match yet — its composition is still an open question.',
  },
};

export function compositionStory(a: Asteroid): { title: string; blurb: string } {
  const c = a.composition_class;
  return COMPOSITION_STORY[c === 'C' || c === 'S' || c === 'M' || c === 'V' ? c : 'U'];
}

export interface Headline {
  value: number;
  format: (n: number) => string;
  caption: string;
  footnote: string | null;
}

/** The one unforgettable number, in order of preference: campaign profit,
 *  in-ground precious-metal value, then delta-v. Computed with the same
 *  greedy + extraction-limit model as the detail drawer and the mission row,
 *  so the spotlight never contradicts itself. */
export function pickHeadline(a: Asteroid): Headline | null {
  const campaign = campaignProjection(a, DEFAULT_MISSION_KG);
  if (campaign.missionsRun > 0 && campaign.totalProfit > 0) {
    return {
      value: campaign.totalProfit,
      format: fmtUsdShort,
      caption: campaign.missionsRun === 1
        ? 'projected profit, single mission'
        : `projected profit over ${campaign.missionsRun} missions`,
      footnote: 'upper-bound model estimate — greedy missions, extraction-limited',
    };
  }
  if (a.total_precious_value_usd != null && a.total_precious_value_usd > 0) {
    return {
      value: a.total_precious_value_usd,
      format: fmtUsdShort,
      caption: 'of precious metals on board, at spot prices',
      footnote: 'in-ground value — before any mission costs',
    };
  }
  if (a.delta_v_km_s != null && a.delta_v_km_s > 0) {
    return {
      value: a.delta_v_km_s,
      format: (n) => `${n.toFixed(2)} km/s`,
      caption: 'Δv to reach it from Earth',
      footnote: 'two-impulse transfer estimate',
    };
  }
  if (a.diameter_estimated_km != null && a.diameter_estimated_km > 0) {
    return {
      value: a.diameter_estimated_km,
      format: (n) => `${n.toFixed(2)} km`,
      caption: 'across',
      footnote: null,
    };
  }
  return null;
}
