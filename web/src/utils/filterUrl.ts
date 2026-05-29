/** Pure URL <-> Filters helpers. The hook handles the window side effects.
 *
 * Defaults are *applied on parse* and *omitted on serialize*, so the URL only
 * shows what differs from the bare-page state. A param present with an empty
 * value (e.g. `?dv_max=`) means "explicitly cleared" — overriding the default.
 */

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

type NumericKey = typeof NUMERIC_KEYS[number];

function defaultNumeric(k: NumericKey): number | undefined {
  return (DEFAULT_FILTERS as unknown as Record<string, number | undefined>)[k];
}

function setNumeric(f: Filters, k: NumericKey, v: number | undefined): void {
  (f as unknown as Record<string, unknown>)[k] = v;
}

export function parseFiltersFromSearch(search: string): Filters {
  const params = new URLSearchParams(search);
  const f: Filters = { ...DEFAULT_FILTERS };

  for (const k of NUMERIC_KEYS) {
    if (!params.has(k)) continue;             // not in URL → keep default
    const v = params.get(k);
    if (v === '' || v == null) {
      setNumeric(f, k, undefined);            // empty value → explicit clear
    } else {
      const n = Number(v);
      if (Number.isFinite(n)) setNumeric(f, k, n);
    }
  }

  for (const k of ['neo', 'composition_class', 'orbit_class'] as const) {
    if (!params.has(k)) continue;
    const v = params.get(k);
    if (v) f[k] = v;
    else delete f[k];
  }

  if (params.has('viable')) {
    const v = params.get('viable');
    if (v === 'true') f.is_viable = true;
    else if (v === 'false') f.is_viable = false;
    else f.is_viable = undefined;
  }

  const sort = params.get('sort');
  if (sort) f.sort = sort;
  const order = params.get('order');
  if (order === 'asc' || order === 'desc') f.order = order;

  return f;
}

/** Strip filter params from `existing` and write only values that differ from
 * the defaults; non-filter params (e.g. `?asteroid=`) are preserved.
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
    const dv = defaultNumeric(k);
    if (v === dv) continue;                   // matches default → omit
    if (typeof v === 'number') {
      out.set(k, String(v));
    } else if (dv !== undefined) {
      out.set(k, '');                         // explicit clear sentinel
    }
  }

  return out;
}
