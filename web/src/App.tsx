import { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AsteroidTable } from './components/AsteroidTable';
import { AsteroidDetail } from './components/AsteroidDetail';
import { FilterBar } from './components/FilterBar';
import { SearchBox } from './components/SearchBox';
import { StatsCards } from './components/StatsCards';
import { AboutModal } from './components/AboutModal';
import { TimelineSlider, todayOffset, type PlaySpeed } from './components/TimelineSlider';
import { SolarSystem } from './components/scene/SolarSystem';
import { useAsteroids } from './hooks/useAsteroids';
import { useStats } from './hooks/useStats';
import { computeHohmannTransfer, estimateLaunchWindows } from './utils/transfer';

const MethodologyView = lazy(() =>
  import('./components/MethodologyView').then((m) => ({ default: m.MethodologyView })),
);

import './App.css';

type ColorBy = 'composition' | 'delta_v' | 'viable' | 'confidence' | 'campaign_profit';

export default function App() {
  const {
    asteroids, total, filters, loading, hasLoadedOnce,
    selected, setSelected,
    updateFilters, clearFilters, nextPage, prevPage, toggleSort,
    notice, dismissNotice,
  } = useAsteroids();

  // Show scene loading overlay on initial load; debounce subsequent refetches
  // by 300ms so brief flickers from filter typing don't show a spinner.
  const [showSceneLoading, setShowSceneLoading] = useState(false);
  useEffect(() => {
    if (!loading) { setShowSceneLoading(false); return; }
    if (!hasLoadedOnce) { setShowSceneLoading(true); return; }
    const t = setTimeout(() => setShowSceneLoading(true), 300);
    return () => clearTimeout(t);
  }, [loading, hasLoadedOnce]);
  const stats = useStats(filters);
  const [colorBy, setColorBy] = useState<ColorBy>('composition');
  const [dayOffset, setDayOffset] = useState(todayOffset);
  const [speed, setSpeed] = useState<PlaySpeed>(10);
  const [showAbout, setShowAbout] = useState(false);
  const isMethodologyHash = (h: string) => h === '#methodology' || h.startsWith('#m-');
  const [showMethodology, setShowMethodology] = useState(() =>
    typeof window !== 'undefined' && isMethodologyHash(window.location.hash),
  );
  const [panelWidth, setPanelWidth] = useState(40); // table panel width %

  useEffect(() => {
    // Keep methodology open while the hash is `#methodology` or any TOC anchor (`#m-…`).
    // Otherwise TOC clicks would close the view via the hashchange.
    const onHash = () => setShowMethodology(isMethodologyHash(window.location.hash));
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  const openMethodology = useCallback(() => {
    window.location.hash = '#methodology';
    setShowMethodology(true);
  }, []);
  const closeMethodology = useCallback(() => {
    // Clear both `#methodology` and any in-doc TOC anchor (#m-…) so the URL is clean.
    const h = window.location.hash;
    if (h === '#methodology' || h.startsWith('#m-')) {
      history.replaceState(null, '', window.location.pathname + window.location.search);
    }
    setShowMethodology(false);
  }, []);
  const dragging = useRef(false);
  const mainRef = useRef<HTMLDivElement>(null);

  const onResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    dragging.current = true;
    const onMove = (ev: MouseEvent) => {
      if (!dragging.current || !mainRef.current) return;
      const rect = mainRef.current.getBoundingClientRect();
      const pct = ((ev.clientX - rect.left) / rect.width) * 100;
      setPanelWidth(Math.min(70, Math.max(20, pct)));
    };
    const onUp = () => { dragging.current = false; window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp); };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }, []);

  // Compute launch windows across full timeline for selected asteroid
  const selectedWindows = useMemo(() => {
    if (!selected?.a_au || !selected?.inclination_deg) return undefined;
    const transfer = computeHohmannTransfer(selected.a_au, selected.inclination_deg);
    // Cover the full timeline (0 to 18262 days)
    const count = Math.ceil(18262 / transfer.synodic_days) + 2;
    return estimateLaunchWindows(transfer.synodic_days, transfer.transfer_days, 0, count);
  }, [selected?.a_au, selected?.inclination_deg, selected?.spkid]);  // eslint-disable-line

  return (
    <div className="app">
      <header className="app-header">
        <h1>Asteroid Atlas</h1>
        {stats?.last_updated && (
          <span className="data-freshness" title="Date of the latest atlas snapshot">
            Data {stats.last_updated}
          </span>
        )}
        <SearchBox onSelect={setSelected} />
        <select
          className="color-select"
          value={colorBy}
          onChange={(e) => setColorBy(e.target.value as ColorBy)}
        >
          <option value="composition">Color: Composition</option>
          <option value="delta_v">Color: Delta-v</option>
          <option value="viable">Color: Viability (greedy + extraction-limit)</option>
          <option value="confidence">Color: Confidence</option>
          <option value="campaign_profit">Color: Campaign Profit</option>
        </select>
        <button className="about-btn" onClick={openMethodology}>Methodology</button>
        <button className="about-btn" onClick={() => setShowAbout(true)}>About</button>
      </header>

      {notice && (
        <div className="notice-banner" role="alert">
          <span>{notice}</span>
          <button onClick={dismissNotice} aria-label="Dismiss">×</button>
        </div>
      )}

      <StatsCards stats={stats} />
      <FilterBar filters={filters} onUpdate={updateFilters} onClear={clearFilters} />

      <div className="main-content" ref={mainRef}>
        <div className={`table-panel${selected ? ' table-panel--detail' : ''}`} style={{ width: `${panelWidth}%` }}>
          {selected ? (
            <>
              <div className="selected-header">
                <table className="asteroid-table">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Class</th>
                      <th>D (km)</th>
                      <th>Dv</th>
                      <th>Viable</th>
                      <th>
                        <button className="back-btn" onClick={() => setSelected(null)}>
                          Back to table
                        </button>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr className="selected-row">
                      <td>{selected.name}</td>
                      <td>{selected.composition_class ?? '—'}</td>
                      <td>{selected.diameter_estimated_km?.toFixed(3) ?? '—'}</td>
                      <td>{selected.delta_v_km_s?.toFixed(2) ?? '—'}</td>
                      <td>{selected.is_viable ? 'Yes' : 'No'}</td>
                      <td />
                    </tr>
                  </tbody>
                </table>
              </div>
              <AsteroidDetail asteroid={selected} onClose={() => setSelected(null)} />
            </>
          ) : (
            <AsteroidTable
              asteroids={asteroids}
              total={total}
              loading={loading}
              sort={filters.sort}
              order={filters.order}
              offset={filters.offset}
              limit={filters.limit}
              onSort={toggleSort}
              onNext={nextPage}
              onPrev={prevPage}
              onSelect={setSelected}
            />
          )}
        </div>

        <div className="panel-resizer" onMouseDown={onResizeStart} />

        <div className="scene-panel">
          <SolarSystem
            asteroids={asteroids}
            selected={selected}
            colorBy={colorBy}
            dayOffset={dayOffset}
            speed={speed}
            onDayOffsetChange={setDayOffset}
            onSelectAsteroid={setSelected}
          />
          {showSceneLoading && (
            <div className="scene-loading" role="status" aria-live="polite">
              <div className="scene-loading-spinner" />
              <span>Loading asteroids…</span>
            </div>
          )}
        </div>
      </div>

      <div className="bottom-bar">
        <TimelineSlider
          dayOffset={dayOffset}
          onChange={setDayOffset}
          speed={speed}
          onSetSpeed={setSpeed}
          windows={selectedWindows}
        />
      </div>

      {showAbout && <AboutModal onClose={() => setShowAbout(false)} />}
      {showMethodology && (
        <Suspense fallback={<div className="methodology-view"><p className="methodology-loading">Loading methodology…</p></div>}>
          <MethodologyView onClose={closeMethodology} />
        </Suspense>
      )}
    </div>
  );
}
