const AU_KM = 149_597_870.7;

/** Approximate orbit circumference via Ramanujan's formula for ellipse. */
export function orbitCircumferenceKm(a: number, e: number): number {
  const b = a * Math.sqrt(1 - e * e);
  const h = ((a - b) / (a + b)) ** 2;
  const circumAU = Math.PI * (a + b) * (1 + (3 * h) / (10 + Math.sqrt(4 - 3 * h)));
  return circumAU * AU_KM;
}

export function formatKm(km: number): string {
  if (km >= 1e9) return `${(km / 1e9).toFixed(1)}B km`;
  if (km >= 1e6) return `${(km / 1e6).toFixed(0)}M km`;
  return `${(km / 1e3).toFixed(0)}K km`;
}

/** Orbital period from Kepler's third law. */
export function orbitalPeriod(a: number): { years: number; days: number; label: string } {
  const years = Math.pow(a, 1.5);
  const days = years * 365.25;
  if (years >= 1) return { years, days, label: `${years.toFixed(1)} yr` };
  return { years, days, label: `${days.toFixed(0)} d` };
}
