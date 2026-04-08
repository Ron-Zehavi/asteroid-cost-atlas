import { useCallback, useEffect, useState } from 'react';
import { getAsteroids } from '../api/client';
import type { Asteroid, AsteroidListResponse, Filters } from '../types/asteroid';

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
