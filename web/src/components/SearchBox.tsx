import { useCallback, useEffect, useRef, useState } from 'react';
import { searchAsteroids } from '../api/client';
import type { Asteroid } from '../types/asteroid';

interface Props {
  onSelect: (asteroid: Asteroid) => void;
}

export function SearchBox({ onSelect }: Props) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Asteroid[]>([]);
  const [open, setOpen] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);

  const search = useCallback(async (q: string) => {
    if (q.length < 2) { setResults([]); return; }
    try {
      const data = await searchAsteroids(q);
      setResults(data);
      setOpen(true);
    } catch { setResults([]); }
  }, []);

  useEffect(() => {
    clearTimeout(timer.current);
    timer.current = setTimeout(() => search(query), 300);
    return () => clearTimeout(timer.current);
  }, [query, search]);

  return (
    <div className="search-box">
      <input
        type="text"
        placeholder="Search asteroids..."
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onFocus={() => results.length > 0 && setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 200)}
      />
      {open && results.length > 0 && (
        <ul className="search-results">
          {results.map((a) => (
            <li
              key={a.spkid}
              onMouseDown={() => { onSelect(a); setOpen(false); setQuery(a.name); }}
            >
              <span className="search-name">{a.name}</span>
              <span className="search-meta">
                {a.composition_class} | Dv {a.delta_v_km_s?.toFixed(1)} km/s
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
