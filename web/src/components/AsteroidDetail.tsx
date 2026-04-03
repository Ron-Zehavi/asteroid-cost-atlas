import type { Asteroid } from '../types/asteroid';
import { extractionInventory, missionScenario } from '../utils/mining';

function fmt(n: number | null | undefined, d = 2): string {
  if (n == null || !isFinite(n)) return '—';
  return n.toLocaleString(undefined, { maximumFractionDigits: d });
}

function fmtUsd(n: number | null | undefined): string {
  if (n == null || !isFinite(n)) return '—';
  const abs = Math.abs(n);
  const sign = n < 0 ? '-' : '';
  if (abs >= 1e12) return `${sign}$${(abs / 1e12).toFixed(2)}T`;
  if (abs >= 1e9) return `${sign}$${(abs / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${sign}$${(abs / 1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `${sign}$${(abs / 1e3).toFixed(0)}K`;
  return `${sign}$${abs.toFixed(0)}`;
}

function fmtKg(kg: number): string {
  if (!isFinite(kg) || kg === 0) return '—';
  if (kg >= 1e9) return `${(kg / 1e9).toFixed(1)} Mt`;
  if (kg >= 1e6) return `${(kg / 1e6).toFixed(1)} kt`;
  if (kg >= 1e3) return `${(kg / 1e3).toFixed(1)} t`;
  return `${kg.toFixed(1)} kg`;
}

function fmtMass(kg: number | null | undefined): string {
  if (kg == null || !isFinite(kg)) return '—';
  if (kg >= 1e18) return `${(kg / 1e18).toFixed(1)} Et`;
  if (kg >= 1e15) return `${(kg / 1e15).toFixed(1)} Pt`;
  if (kg >= 1e12) return `${(kg / 1e12).toFixed(1)} Tt`;
  if (kg >= 1e9) return `${(kg / 1e9).toFixed(1)} Gt`;
  if (kg >= 1e6) return `${(kg / 1e6).toFixed(1)} Mt`;
  return `${(kg / 1e3).toFixed(1)} t`;
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="detail-row">
      <span className="detail-label">{label}</span>
      <span className="detail-value">{value}</span>
    </div>
  );
}

interface Props {
  asteroid: Asteroid | null;
  onClose: () => void;
  onPin?: () => void;
  isPinned?: boolean;
}

export function AsteroidDetail({ asteroid, onClose, onPin, isPinned }: Props) {
  if (!asteroid) return null;
  const a = asteroid;
  const inv = extractionInventory(a);
  const s1 = missionScenario(a, 1_000);
  const s10 = missionScenario(a, 10_000);
  const s100 = missionScenario(a, 100_000);

  return (
    <div className="detail-drawer">
      <div className="detail-header">
        <h2>{a.name}</h2>
        <div className="detail-actions">
          {onPin && (
            <button onClick={onPin} className="pin-btn">
              {isPinned ? 'Unpin' : 'Pin'}
            </button>
          )}
          <button onClick={onClose} className="close-btn">x</button>
        </div>
      </div>

      <div className="detail-section">
        <h3>Identification</h3>
        <Row label="SPK-ID" value={String(a.spkid)} />
        <Row label="Orbit Class" value={a.orbit_class ?? '—'} />
        <Row label="NEO" value={a.neo ?? '—'} />
        <Row label="PHA" value={a.pha ?? '—'} />
        <Row label="Rank" value={fmt(a.economic_priority_rank, 0)} />
      </div>

      <div className="detail-section">
        <h3>Orbital Elements</h3>
        <Row label="Semi-major axis" value={`${fmt(a.a_au, 4)} AU`} />
        <Row label="Eccentricity" value={fmt(a.eccentricity, 4)} />
        <Row label="Inclination" value={`${fmt(a.inclination_deg, 2)} deg`} />
        <Row label="Delta-v" value={`${fmt(a.delta_v_km_s, 2)} km/s`} />
        <Row label="Tisserand (J)" value={fmt(a.tisserand_jupiter, 3)} />
        <Row label="MOID" value={`${fmt(a.moid_au, 4)} AU`} />
        <Row label="Precision" value={a.orbital_precision_source ?? '—'} />
      </div>

      <div className="detail-section">
        <h3>Physical</h3>
        <Row label="Diameter" value={`${fmt(a.diameter_estimated_km, 3)} km (${a.diameter_source ?? '?'})`} />
        <Row label="Total Mass" value={fmtMass(a.estimated_mass_kg)} />
        <Row label="Gravity" value={`${fmt(a.surface_gravity_m_s2, 4)} m/s²`} />
        <Row label="Rotation" value={a.rotation_hours ? `${fmt(a.rotation_hours, 2)} h` : '—'} />
        <Row label="Rot. Feasibility" value={a.rotation_feasibility != null ? fmt(a.rotation_feasibility) : '—'} />
        <Row label="Regolith" value={a.regolith_likelihood != null ? fmt(a.regolith_likelihood) : '—'} />
        <Row label="Albedo" value={fmt(a.albedo, 3)} />
      </div>

      <div className="detail-section">
        <h3>Composition ({a.composition_class ?? 'U'})</h3>
        <Row label="Source" value={a.composition_source ?? '—'} />
        <Row label="Resource Value" value={`${fmtUsd(a.resource_value_usd_per_kg)}/kg`} />
      </div>

      <div className="detail-section">
        <h3>Extractable Resources</h3>
        <Row label="Water" value={inv.waterKg > 0 ? `${fmtKg(inv.waterKg)} (${fmtUsd(inv.waterUsd)})` : '—'} />
        <Row label="Bulk Metals" value={inv.metalKg > 0 ? `${fmtKg(inv.metalKg)} (${fmtUsd(inv.metalUsd)})` : '—'} />
        {inv.perMetal.filter((m) => m.kg > 0.01).map((m) => (
          <Row
            key={m.name}
            label={m.name.charAt(0).toUpperCase() + m.name.slice(1)}
            value={`${fmtKg(m.kg)} (${fmtUsd(m.usd)})`}
          />
        ))}
        <Row label="Total PGM" value={`${fmtKg(inv.preciousKg)} (${fmtUsd(inv.preciousUsd)})`} />
      </div>

      <div className="detail-section">
        <h3>Mission Scenarios</h3>
        <table className="scenario-table">
          <thead>
            <tr>
              <th></th>
              <th>1 ton</th>
              <th>10 ton</th>
              <th>100 ton</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td className="detail-label">Payload</td>
              <td>{fmtKg(s1.payloadKg)}</td>
              <td>{fmtKg(s10.payloadKg)}</td>
              <td>{fmtKg(s100.payloadKg)}</td>
            </tr>
            <tr>
              <td className="detail-label">Revenue</td>
              <td>{fmtUsd(s1.revenue)}</td>
              <td>{fmtUsd(s10.revenue)}</td>
              <td>{fmtUsd(s100.revenue)}</td>
            </tr>
            <tr>
              <td className="detail-label">Cost</td>
              <td>{fmtUsd(s1.totalCost)}</td>
              <td>{fmtUsd(s10.totalCost)}</td>
              <td>{fmtUsd(s100.totalCost)}</td>
            </tr>
            <tr className={s1.feasible ? 'profit-positive' : 'profit-negative'}>
              <td className="detail-label">Profit</td>
              <td className={s1.feasible ? 'profit-positive' : 'profit-negative'}>{fmtUsd(s1.profit)}</td>
              <td className={s10.feasible ? 'profit-positive' : 'profit-negative'}>{fmtUsd(s10.profit)}</td>
              <td className={s100.feasible ? 'profit-positive' : 'profit-negative'}>{fmtUsd(s100.profit)}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div className="detail-section">
        <h3>Break-even</h3>
        <Row label="Total" value={a.break_even_kg ? fmtKg(a.break_even_kg) : '—'} />
        <Row label="Viable" value={a.is_viable ? 'Yes' : 'No'} />
      </div>
    </div>
  );
}
