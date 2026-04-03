import { useEffect, useState } from 'react';
import type { Filters, Stats } from '../types/asteroid';

export function useStats(filters?: Filters) {
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      // Build query params from filters
      const params = new URLSearchParams();
      if (filters?.neo) params.set('neo', filters.neo);
      if (filters?.is_viable !== undefined) params.set('is_viable', String(filters.is_viable));
      if (filters?.composition_class) params.set('composition_class', filters.composition_class);
      if (filters?.dv_max !== undefined) params.set('dv_max', String(filters.dv_max));
      const qs = params.toString();
      const url = `/api/stats${qs ? `?${qs}` : ''}`;

      for (let attempt = 0; attempt < 15; attempt++) {
        try {
          const resp = await fetch(url);
          if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
          const data = await resp.json();
          if (!cancelled && data && data.total_objects != null) {
            setStats(data as Stats);
            return;
          }
        } catch (err) {
          console.warn(`Stats fetch attempt ${attempt + 1} failed:`, err);
        }
        await new Promise((r) => setTimeout(r, 1500));
      }
    };

    load();
    return () => { cancelled = true; };
  }, [
    filters?.neo,
    filters?.is_viable,
    filters?.composition_class,
    filters?.dv_max,
  ]);

  return stats;
}
