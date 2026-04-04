/**
 * Hohmann transfer trajectory with time-aware mission simulation.
 *
 * Mission lifecycle:
 *   WAITING      → before launch window (show countdown)
 *   WINDOW_OPEN  → launch window is open (trajectory updates daily)
 *   IN_TRANSIT   → spacecraft launched, advancing along arc
 *   ARRIVED      → spacecraft reached asteroid
 *   PAST         → mission complete, arc fades
 *
 * Launch windows are anchored to fixed synodic-period multiples from
 * a reference epoch (J2000), not relative to current time. This ensures
 * windows stay in place as time advances.
 */

import type { Vec3 } from './kepler';

const V_EARTH = 29.78; // km/s
const WINDOW_DURATION_DAYS = 30;
const MIN_SYNODIC_DAYS = 60; // minimum for near-Earth orbits

export type MissionPhase = 'waiting' | 'window_open' | 'in_transit' | 'arrived' | 'past';

export interface TransferParams {
  a_transfer: number;
  e_transfer: number;
  dv_departure: number;
  dv_arrival: number;
  dv_inclination: number;
  dv_total: number;
  transfer_days: number;
  synodic_days: number;
}

export interface LaunchWindow {
  date: string;
  dayOffset: number;
  windowEnd: number;
  arrivalDay: number;
}

/**
 * Compute Hohmann transfer parameters.
 */
export function computeHohmannTransfer(
  a_target: number,
  i_deg: number = 0,
): TransferParams {
  const a_earth = 1.0;
  const a_transfer = (a_earth + a_target) / 2;
  const e_transfer = Math.abs(a_target - a_earth) / (a_target + a_earth);

  const dv1 = V_EARTH * Math.abs(Math.sqrt(2 * a_target / (a_earth + a_target)) - 1);
  const dv2 = (V_EARTH / Math.sqrt(a_target)) * Math.abs(1 - Math.sqrt(2 / (a_earth + a_target)));
  const v_mid = V_EARTH * Math.sqrt(2 / (a_earth + a_target));
  const i_rad = (i_deg * Math.PI) / 180;
  const dv_inc = 2 * v_mid * Math.sin(i_rad / 2);
  const dv_total = Math.sqrt(dv1 ** 2 + dv2 ** 2 + dv_inc ** 2);

  const transfer_years = Math.sqrt(a_transfer ** 3) * 0.5;
  const transfer_days = transfer_years * 365.25;

  // Synodic period — shorter for NEAs (frequent close approaches)
  const T_target = Math.pow(a_target, 1.5);
  const denom = Math.abs(1 - 1 / T_target);
  let synodic_days: number;
  if (denom < 0.001) {
    synodic_days = MIN_SYNODIC_DAYS; // Co-orbital
  } else {
    synodic_days = Math.min(365.25 / denom, 36525);
    // For accessible NEAs, cap synodic to ~1 year for more frequent windows
    if (a_target < 1.5) synodic_days = Math.min(synodic_days, 365);
    if (a_target < 2.0) synodic_days = Math.min(synodic_days, 730);
  }

  return {
    a_transfer, e_transfer,
    dv_departure: dv1, dv_arrival: dv2, dv_inclination: dv_inc, dv_total,
    transfer_days, synodic_days,
  };
}

/**
 * Compute fixed launch windows anchored to epoch multiples.
 *
 * Windows are at fixed positions in time (synodic multiples from J2000),
 * NOT relative to current dayOffset. This ensures they don't move as
 * the timeline advances.
 *
 * Returns windows surrounding `currentDayOffset` (some past, some future).
 */
export function estimateLaunchWindows(
  synodic_days: number,
  transfer_days: number,
  currentDayOffset: number,
  count: number = 10,
): LaunchWindow[] {
  const J2000 = new Date('2000-01-01T12:00:00Z');
  const windows: LaunchWindow[] = [];

  // Anchor windows so one always falls near the current time.
  // Use a small fixed phase offset to avoid windows landing exactly at epoch.
  const phase0 = 42; // fixed anchor offset from J2000

  // Find the window cycle nearest to current time
  const cycleNum = Math.floor((currentDayOffset - phase0) / synodic_days);

  // Start 1 cycle before current to catch in-transit from recent window
  const startCycle = Math.max(0, cycleNum - 1);
  for (let i = 0; i < count; i++) {
    const start = Math.round(phase0 + (startCycle + i) * synodic_days);
    const end = start + WINDOW_DURATION_DAYS;
    const arrival = end + Math.round(transfer_days);
    const date = new Date(J2000.getTime() + start * 86400000);
    windows.push({
      date: date.toISOString().slice(0, 10),
      dayOffset: start,
      windowEnd: end,
      arrivalDay: arrival,
    });
  }

  return windows;
}

/**
 * Determine current mission phase.
 */
export function getMissionPhase(
  windows: LaunchWindow[],
  currentDay: number,
): { phase: MissionPhase; window: LaunchWindow; daysUntil?: number; progress?: number } {
  // Check if we're in transit or arrived from any window
  for (const w of windows) {
    if (currentDay >= w.windowEnd && currentDay < w.arrivalDay) {
      const elapsed = currentDay - w.windowEnd;
      const total = w.arrivalDay - w.windowEnd;
      return { phase: 'in_transit', window: w, progress: Math.min(elapsed / total, 1) };
    }
    if (currentDay >= w.arrivalDay && currentDay < w.arrivalDay + 10) {
      return { phase: 'arrived', window: w };
    }
  }

  // Check if we're in an open window
  for (const w of windows) {
    if (currentDay >= w.dayOffset && currentDay < w.windowEnd) {
      const remaining = Math.round(w.windowEnd - currentDay);
      return { phase: 'window_open', window: w, daysUntil: remaining };
    }
  }

  // Find next future window
  const futureWindows = windows.filter((w) => w.dayOffset > currentDay);
  if (futureWindows.length > 0) {
    const next = futureWindows[0];
    return { phase: 'waiting', window: next, daysUntil: Math.round(next.dayOffset - currentDay) };
  }

  return { phase: 'past', window: windows[windows.length - 1] };
}

/**
 * Generate transfer arc points.
 */
export function transferArcPoints(
  departurePos: Vec3,
  arrivalPos: Vec3,
  segments: number = 64,
): Vec3[] {
  const points: Vec3[] = [];

  for (let i = 0; i <= segments; i++) {
    const t = i / segments;
    const bulge = Math.sin(t * Math.PI) * 0.3;
    const x = departurePos.x * (1 - t) + arrivalPos.x * t;
    const y = departurePos.y * (1 - t) + arrivalPos.y * t;
    const z = departurePos.z * (1 - t) + arrivalPos.z * t;

    const dx = arrivalPos.x - departurePos.x;
    const dz = arrivalPos.z - departurePos.z;
    const len = Math.sqrt(dx * dx + dz * dz) || 1;
    const perpX = -dz / len * bulge * len * 0.5;
    const perpZ = dx / len * bulge * len * 0.5;

    points.push({
      x: x + perpX,
      y: y + bulge * 0.15,
      z: z + perpZ,
    });
  }

  return points;
}

/**
 * Get spacecraft position along arc at given progress [0,1].
 */
export function getSpacecraftPosition(arcPoints: Vec3[], progress: number): Vec3 {
  const clamped = Math.max(0, Math.min(1, progress));
  const idx = Math.min(Math.floor(clamped * (arcPoints.length - 1)), arcPoints.length - 1);
  return arcPoints[idx];
}

/**
 * Convert day offset to calendar date string.
 */
export function dayOffsetToDate(dayOffset: number): string {
  const J2000 = new Date('2000-01-01T12:00:00Z');
  return new Date(J2000.getTime() + dayOffset * 86400000).toISOString().slice(0, 10);
}
