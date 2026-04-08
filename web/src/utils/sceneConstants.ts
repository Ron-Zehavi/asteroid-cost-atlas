/**
 * DISTANCE_SCALE: visual compression of orbital distances.
 *   1.0 = real AU distances
 *   0.125 = 1/8 real distances (current)
 * Only affects rendering — orbital periods stay correct (use real `a` for Kepler math).
 */
export const DISTANCE_SCALE = 1.0;

/**
 * OBJECT_SCALE: visual exaggeration of every body's *radius* — Sun, planets, asteroids.
 *   1.0 = true physical radii (most bodies are sub-pixel at typical zoom)
 *   Bumping this up makes Sun/planets/asteroids visibly bigger without
 *   touching their orbital distances. Keep DISTANCE_SCALE separate so the
 *   ratio of orbit-to-body sizes can be tuned independently.
 */
export const OBJECT_SCALE = 10.0;

/** Cargo spaceship GLB scale for the sandbox preview. */
export const SPACECRAFT_SCALE_PREVIEW = 0.0000015;

/** Cargo spaceship GLB scale for the in-transit visualization. */
export const SPACECRAFT_SCALE_TRANSIT = 0.000000011;
