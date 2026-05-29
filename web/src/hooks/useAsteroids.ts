import { useCallback, useEffect, useState } from 'react';
import { getAsteroid, getAsteroids } from '../api/client';
import type { Asteroid, AsteroidListResponse, Filters } from '../types/asteroid';
import {
  applyFiltersToSearch,
  DEFAULT_FILTERS,
  parseFiltersFromSearch,
} from '../utils/filterUrl';

const PERMALINK_PARAM = 'asteroid';

function readFiltersFromUrl(): Filters {
  return parseFiltersFromSearch(window.location.search);
}

function writeFiltersToUrl(filters: Filters): void {
  const url = new URL(window.location.href);
  const next = applyFiltersToSearch(url.searchParams, filters);
  url.search = next.toString();
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
