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
  const [activeIdx, setActiveIdx] = useState(-1);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const listRef = useRef<HTMLUListElement>(null);

  const search = useCallback(async (q: string) => {
    if (q.length < 2) { setResults([]); setActiveIdx(-1); return; }
    try {
      const data = await searchAsteroids(q);
      setResults(data);
      setActiveIdx(data.length > 0 ? 0 : -1);
      setOpen(true);
    } catch { setResults([]); setActiveIdx(-1); }
  }, []);

  useEffect(() => {
    clearTimeout(timer.current);
    timer.current = setTimeout(() => search(query), 300);
    return () => clearTimeout(timer.current);
  }, [query, search]);

  useEffect(() => {
    if (activeIdx < 0 || !listRef.current) return;
    const el = listRef.current.children[activeIdx] as HTMLElement | undefined;
    el?.scrollIntoView({ block: 'nearest' });
  }, [activeIdx]);

  const pick = useCallback((a: Asteroid) => {
    onSelect(a);
    setOpen(false);
    setQuery(a.name);
    setActiveIdx(-1);
  }, [onSelect]);

  const onKeyDown = useCallback((e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!open || results.length === 0) {
      if (e.key === 'Escape') setOpen(false);
      return;
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIdx((i) => (i + 1) % results.length);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIdx((i) => (i <= 0 ? results.length - 1 : i - 1));
    } else if (e.key === 'Enter') {
      const target = results[activeIdx >= 0 ? activeIdx : 0];
      if (target) {
        e.preventDefault();
        pick(target);
      }
    } else if (e.key === 'Escape') {
      setOpen(false);
    }
  }, [open, results, activeIdx, pick]);

  const listboxId = 'search-results-listbox';
  const optionId = (spkid: number) => `search-opt-${spkid}`;
  const activeId =
    open && activeIdx >= 0 && results[activeIdx]
      ? optionId(results[activeIdx].spkid)
      : undefined;

  return (
    <div className="search-box">
      <input
        type="text"
        placeholder="Search asteroids..."
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onFocus={() => results.length > 0 && setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 200)}
        onKeyDown={onKeyDown}
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={open && results.length > 0}
        aria-controls={listboxId}
        aria-activedescendant={activeId}
      />
      {open && results.length > 0 && (
        <ul
          className="search-results"
          ref={listRef}
          role="listbox"
          id={listboxId}
        >
          {results.map((a, idx) => (
            <li
              key={a.spkid}
              id={optionId(a.spkid)}
              role="option"
              aria-selected={idx === activeIdx}
              className={idx === activeIdx ? 'active' : ''}
              onMouseEnter={() => setActiveIdx(idx)}
              onMouseDown={() => pick(a)}
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
