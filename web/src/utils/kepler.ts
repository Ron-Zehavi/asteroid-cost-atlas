/**
 * Keplerian orbital elements to heliocentric ecliptic Cartesian coordinates.
 *
 * 1. Solve Kepler's equation: M = E - e*sin(E)  (Newton-Raphson)
 * 2. True anomaly from eccentric anomaly
 * 3. Position in orbital plane
 * 4. Rotate by omega, i, Omega into ecliptic frame
 */

const DEG2RAD = Math.PI / 180;
const TWO_PI = 2 * Math.PI;

/** Solve Kepler's equation M = E - e*sin(E) for E via Newton-Raphson. */
function solveKepler(M: number, e: number, tol = 1e-8, maxIter = 30): number {
  let E = M; // initial guess
  for (let i = 0; i < maxIter; i++) {
    const dE = (E - e * Math.sin(E) - M) / (1 - e * Math.cos(E));
    E -= dE;
    if (Math.abs(dE) < tol) break;
  }
  return E;
}

export interface KeplerElements {
  a: number;        // semi-major axis (AU)
  e: number;        // eccentricity
  i: number;        // inclination (degrees)
  om: number;       // longitude of ascending node (degrees)
  w: number;        // argument of perihelion (degrees)
  ma: number;       // mean anomaly (degrees)
}

export interface Vec3 {
  x: number;
  y: number;
  z: number;
}

/**
 * Convert Keplerian elements to heliocentric ecliptic Cartesian position (AU).
 */
export function keplerToCartesian(el: KeplerElements): Vec3 {
  const { a, e } = el;
  const iRad = el.i * DEG2RAD;
  const omRad = el.om * DEG2RAD;
  const wRad = el.w * DEG2RAD;
  let M = (el.ma * DEG2RAD) % TWO_PI;
  if (M < 0) M += TWO_PI;

  // Solve Kepler's equation
  const E = solveKepler(M, e);

  // True anomaly
  const sinE = Math.sin(E);
  const cosE = Math.cos(E);
  const sqrtTerm = Math.sqrt(1 - e * e);
  const nu = Math.atan2(sqrtTerm * sinE, cosE - e);

  // Distance from focus
  const r = a * (1 - e * cosE);

  // Position in orbital plane
  const xOrb = r * Math.cos(nu);
  const yOrb = r * Math.sin(nu);

  // Rotation into ecliptic frame
  const cosOm = Math.cos(omRad);
  const sinOm = Math.sin(omRad);
  const cosW = Math.cos(wRad);
  const sinW = Math.sin(wRad);
  const cosI = Math.cos(iRad);
  const sinI = Math.sin(iRad);

  const x = (cosOm * cosW - sinOm * sinW * cosI) * xOrb
          + (-cosOm * sinW - sinOm * cosW * cosI) * yOrb;
  const y = (sinOm * cosW + cosOm * sinW * cosI) * xOrb
          + (-sinOm * sinW + cosOm * cosW * cosI) * yOrb;
  const z = (sinW * sinI) * xOrb + (cosW * sinI) * yOrb;

  return { x, y, z };
}

/**
 * Generate points along an orbit ellipse for rendering.
 */
export function orbitPoints(el: KeplerElements, segments = 128): Vec3[] {
  const points: Vec3[] = [];
  for (let i = 0; i <= segments; i++) {
    const ma = (360 * i) / segments;
    points.push(keplerToCartesian({ ...el, ma }));
  }
  return points;
}

/**
 * Propagate mean anomaly forward by dt days from epoch.
 * n = mean motion = 360 / period, period = a^1.5 years * 365.25 days
 */
export function propagateMeanAnomaly(ma0: number, a: number, dtDays: number): number {
  const periodDays = Math.pow(a, 1.5) * 365.25;
  const n = 360 / periodDays; // degrees per day
  return (ma0 + n * dtDays) % 360;
}
