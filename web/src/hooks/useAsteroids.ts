import { useCallback, useEffect, useState } from 'react';
import { getAsteroid, getAsteroids } from '../api/client';
import type { Asteroid, AsteroidListResponse, Filters } from '../types/asteroid';

const PERMALINK_PARAM = 'asteroid';

const DEFAULT_FILTERS: Filters = {
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

const NUMERIC_KEYS = new Set([
  'dv_min', 'dv_max', 'inclination_max',
  'tisserand_min', 'tisserand_max',
  'diameter_min', 'diameter_max',
]);

function readFiltersFromUrl(): Filters {
  const params = new URLSearchParams(window.location.search);
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

function writeFiltersToUrl(filters: Filters): void {
  const url = new URL(window.location.href);
  for (const k of URL_FILTER_KEYS) url.searchParams.delete(k);

  if (filters.neo) url.searchParams.set('neo', filters.neo);
  if (filters.composition_class) url.searchParams.set('composition_class', filters.composition_class);
  if (filters.orbit_class) url.searchParams.set('orbit_class', filters.orbit_class);
  if (filters.is_viable !== undefined) url.searchParams.set('viable', String(filters.is_viable));
  if (filters.sort !== DEFAULT_FILTERS.sort) url.searchParams.set('sort', filters.sort);
  if (filters.order !== DEFAULT_FILTERS.order) url.searchParams.set('order', filters.order);
  for (const k of NUMERIC_KEYS) {
    const v = (filters as unknown as Record<string, unknown>)[k];
    if (typeof v === 'number') url.searchParams.set(k, String(v));
  }

  window.history.replaceState(null, '', url.toString());
}

function readPermalink(): number | null {
  const raw = new URLSearchParams(window.location.search).get(PERMALINK_PARAM);
  const n = raw ? Number(raw) : NaN;
  return Number.isFinite(n) && n > 0 ? n : null;
}

function writePermalink(spkid: number | null) {
  const url = new URL(window.location.href);
  if (spkid == null) url.searchParams.delete(PERMALINK_PARAM);
  else url.searchParams.set(PERMALINK_PARAM, String(spkid));
  window.history.replaceState(null, '', url.toString());
}

export function useAsteroids() {
  const [filters, setFilters] = useState<Filters>(() => readFiltersFromUrl());
  const [response, setResponse] = useState<AsteroidListResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<Asteroid | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [hasLoadedOnce, setHasLoadedOnce] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    for (let attempt = 0; attempt < 5; attempt++) {
      try {
        const data = await getAsteroids(filters);
        setResponse(data);
        setLoading(false);
        setHasLoadedOnce(true);
        return;
      } catch (err) {
        if (attempt === 4) console.error('Failed to fetch asteroids:', err);
        else await new Promise((r) => setTimeout(r, 2000));
      }
    }
    setLoading(false);
  }, [filters]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  useEffect(() => {
    writeFiltersToUrl(filters);
  }, [filters]);

  useEffect(() => {
    const spkid = readPermalink();
    if (spkid != null) {
      getAsteroid(spkid)
        .then(setSelected)
        .catch(() => {
          setNotice(`Asteroid ${spkid} not found.`);
          writePermalink(null);
        });
    }
  }, []);

  useEffect(() => {
    writePermalink(selected?.spkid ?? null);
  }, [selected?.spkid]);

  useEffect(() => {
    if (!notice) return;
    const t = setTimeout(() => setNotice(null), 5000);
    return () => clearTimeout(t);
  }, [notice]);

  const updateFilters = useCallback((patch: Partial<Filters>) => {
    setFilters((prev) => ({ ...prev, offset: 0, ...patch }));
  }, []);

  const clearFilters = useCallback(() => {
    setFilters({
      sort: DEFAULT_FILTERS.sort,
      order: DEFAULT_FILTERS.order,
      limit: DEFAULT_FILTERS.limit,
      offset: 0,
    });
  }, []);

  const nextPage = useCallback(() => {
    setFilters((prev) => ({ ...prev, offset: prev.offset + prev.limit }));
  }, []);

  const prevPage = useCallback(() => {
    setFilters((prev) => ({ ...prev, offset: Math.max(0, prev.offset - prev.limit) }));
  }, []);

  const toggleSort = useCallback((column: string) => {
    setFilters((prev) => ({
      ...prev,
      sort: column,
      order: prev.sort === column && prev.order === 'asc' ? 'desc' : 'asc',
      offset: 0,
    }));
  }, []);

  return {
    asteroids: response?.data ?? [],
    total: response?.total ?? 0,
    filters,
    loading,
    hasLoadedOnce,
    selected,
    setSelected,
    updateFilters,
    clearFilters,
    nextPage,
    prevPage,
    toggleSort,
    notice,
    dismissNotice: useCallback(() => setNotice(null), []),
  };
}
