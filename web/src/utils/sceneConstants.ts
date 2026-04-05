/**
 * DISTANCE_SCALE: visual compression of orbital distances.
 *   1.0 = real AU distances
 *   0.125 = 1/8 real distances (current)
 * Only affects rendering — orbital periods stay correct (use real `a` for Kepler math).
 */
export const DISTANCE_SCALE = 0.125;

/** Cargo spaceship GLB scale for the sandbox preview. */
export const SPACECRAFT_SCALE_PREVIEW = 0.0000015;

/** Cargo spaceship GLB scale for the in-transit visualization. */
export const SPACECRAFT_SCALE_TRANSIT = 0.000000011;
