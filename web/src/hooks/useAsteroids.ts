import { useCallback, useEffect, useState } from 'react';
import { getAsteroid, getAsteroids } from '../api/client';
import type { Asteroid, AsteroidListResponse, Filters } from '../types/asteroid';

const PERMALINK_PARAM = 'asteroid';

function readPermalink(): number | null {
  const raw = new URLSearchParams(window.location.search).get(PERMALINK_PARAM);
  const n = raw ? Number(raw) : NaN;
  return Number.isFinite(n) ? n : null;
}

function writePermalink(spkid: number | null) {
  const url = new URL(window.location.href);
  if (spkid == null) url.searchParams.delete(PERMALINK_PARAM);
  else url.searchParams.set(PERMALINK_PARAM, String(spkid));
  window.history.replaceState(null, '', url.toString());
}

const DEFAULT_FILTERS: Filters = {
  sort: 'economic_priority_rank',
  order: 'asc',
  limit: 200,
  offset: 0,
  dv_max: 3,
};

export function useAsteroids() {
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [response, setResponse] = useState<AsteroidListResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<Asteroid | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    for (let attempt = 0; attempt < 5; attempt++) {
      try {
        const data = await getAsteroids(filters);
        setResponse(data);
        setLoading(false);
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
    const spkid = readPermalink();
    if (spkid != null) {
      getAsteroid(spkid).then(setSelected).catch(() => {});
    }
  }, []);

  useEffect(() => {
    writePermalink(selected?.spkid ?? null);
  }, [selected?.spkid]);

  const updateFilters = useCallback((patch: Partial<Filters>) => {
    setFilters((prev) => ({ ...prev, offset: 0, ...patch }));
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
    selected,
    setSelected,
    updateFilters,
    nextPage,
    prevPage,
    toggleSort,
  };
}
