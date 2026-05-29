/** Pure URL <-> Filters helpers. The hook handles the window side effects. */

import type { Filters } from '../types/asteroid';

export const DEFAULT_FILTERS: Filters = {
  sort: 'economic_priority_rank',
  order: 'asc',
  limit: 200,
  offset: 0,
  dv_max: 3,
};

const URL_FILTER_KEYS = [
  'neo', 'composition_class', 'orbit_class', 'viable',
  'dv_min', 'dv_max', 'inclination_max',
  'tisserand_min', 'tisserand_max',
  'diameter_min', 'diameter_max',
  'sort', 'order',
] as const;

const NUMERIC_KEYS = [
  'dv_min', 'dv_max', 'inclination_max',
  'tisserand_min', 'tisserand_max',
  'diameter_min', 'diameter_max',
] as const;

export function parseFiltersFromSearch(search: string): Filters {
  const params = new URLSearchParams(search);
  const hasAnyFilter = URL_FILTER_KEYS.some((k) => params.has(k));
  if (!hasAnyFilter) return { ...DEFAULT_FILTERS };

  const f: Filters = { sort: 'economic_priority_rank', order: 'asc', limit: 200, offset: 0 };

  for (const k of NUMERIC_KEYS) {
    const v = params.get(k);
    if (v != null && v !== '') {
      const n = Number(v);
      if (Number.isFinite(n)) (f as unknown as Record<string, unknown>)[k] = n;
    }
  }

  for (const k of ['neo', 'composition_class', 'orbit_class'] as const) {
    const v = params.get(k);
    if (v) f[k] = v;
  }

  const viable = params.get('viable');
  if (viable === 'true') f.is_viable = true;
  else if (viable === 'false') f.is_viable = false;

  const sort = params.get('sort');
  if (sort) f.sort = sort;
  const order = params.get('order');
  if (order === 'asc' || order === 'desc') f.order = order;

  return f;
}

/** Strip filter params from `existing` and write current values, leaving non-filter
 * params (e.g. `?asteroid=`) untouched. Returns a new URLSearchParams.
 */
export function applyFiltersToSearch(
  existing: URLSearchParams,
  filters: Filters,
): URLSearchParams {
  const out = new URLSearchParams(existing);
  for (const k of URL_FILTER_KEYS) out.delete(k);

  if (filters.neo) out.set('neo', filters.neo);
  if (filters.composition_class) out.set('composition_class', filters.composition_class);
  if (filters.orbit_class) out.set('orbit_class', filters.orbit_class);
  if (filters.is_viable !== undefined) out.set('viable', String(filters.is_viable));
  if (filters.sort !== DEFAULT_FILTERS.sort) out.set('sort', filters.sort);
  if (filters.order !== DEFAULT_FILTERS.order) out.set('order', filters.order);
  for (const k of NUMERIC_KEYS) {
    const v = (filters as unknown as Record<string, unknown>)[k];
    if (typeof v === 'number') out.set(k, String(v));
  }
  return out;
}
