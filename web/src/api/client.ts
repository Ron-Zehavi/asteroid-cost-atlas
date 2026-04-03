import type {
  Asteroid,
  AsteroidListResponse,
  CompositionStat,
  Filters,
  HistogramBin,
  Stats,
} from '../types/asteroid';

const BASE = '/api';

async function fetchJson<T>(url: string): Promise<T> {
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return resp.json() as Promise<T>;
}

export async function getStats(): Promise<Stats> {
  return fetchJson<Stats>(`${BASE}/stats`);
}

export async function getAsteroids(filters: Filters): Promise<AsteroidListResponse> {
  const params = new URLSearchParams();
  params.set('limit', String(filters.limit));
  params.set('offset', String(filters.offset));
  params.set('sort', filters.sort);
  params.set('order', filters.order);
  if (filters.neo) params.set('neo', filters.neo);
  if (filters.is_viable !== undefined) params.set('is_viable', String(filters.is_viable));
  if (filters.composition_class) params.set('composition_class', filters.composition_class);
  if (filters.orbit_class) params.set('orbit_class', filters.orbit_class);
  if (filters.dv_min !== undefined) params.set('dv_min', String(filters.dv_min));
  if (filters.dv_max !== undefined) params.set('dv_max', String(filters.dv_max));
  return fetchJson<AsteroidListResponse>(`${BASE}/asteroids?${params}`);
}

export async function getAsteroid(spkid: number): Promise<Asteroid> {
  return fetchJson<Asteroid>(`${BASE}/asteroids/${spkid}`);
}

export async function searchAsteroids(query: string): Promise<Asteroid[]> {
  return fetchJson<Asteroid[]>(`${BASE}/search?q=${encodeURIComponent(query)}`);
}

export async function getDeltaVHistogram(binWidth = 1.0): Promise<HistogramBin[]> {
  return fetchJson<HistogramBin[]>(`${BASE}/charts/delta-v?bin_width=${binWidth}`);
}

export async function getCompositionStats(): Promise<CompositionStat[]> {
  return fetchJson<CompositionStat[]>(`${BASE}/charts/composition`);
}
