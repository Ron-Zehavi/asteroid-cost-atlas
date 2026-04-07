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

function Row({ label, value, tooltip }: { label: string; value: string; tooltip?: string }) {
  return (
    <div className="detail-row">
      <span className="detail-label" title={tooltip}>{label}</span>
      <span className="detail-value">{value}</span>
    </div>
  );
}

const METAL_TOOLTIPS: Record<string, string> = {
  platinum: '30% assumed yield. Spot $63,300/kg (Kitco Apr 2026). M: ~15 ppm, C: ~0.9 ppm (meteorite-analog estimates, Cannon et al. 2023). Same yield/source assumptions apply to all metals below.',
  palladium: '30% assumed yield. Spot $47,870/kg. M: ~8 ppm, C: ~0.56 ppm. Catalytic and electronics demand.',
  rhodium: '30% assumed yield. Spot $299,000/kg. M: ~2 ppm, C: ~0.13 ppm. Highest value PGM per kg \u2014 often the largest contributor to specimen-return revenue.',
  iridium: '30% assumed yield. Spot $254,000/kg. M: ~5 ppm, C: ~0.46 ppm. High-temperature alloys.',
  osmium: '30% assumed yield. ~$12,860/kg (order-of-magnitude industrial estimate). M: ~5 ppm, C: ~0.49 ppm.',
  ruthenium: '30% assumed yield. Spot $56,260/kg. M: ~6 ppm, C: ~0.68 ppm. Electronics and chemical catalysis.',
  gold: '30% assumed yield. Spot $150,740/kg. M: ~1 ppm, C: ~0.15 ppm. Consistent with iron-meteorite analog measurements (Cannon et al., 2023).',
};

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
        <Row label="SPK-ID" value={String(a.spkid)}
          tooltip="JPL Small-Body Parameter Key ID. Unique numeric identifier in NASA's SBDB. 20000001 = (1) Ceres." />
        <Row label="Orbit Class" value={a.orbit_class ?? '—'}
          tooltip="Orbital classification. AMO = Amor (Mars-crossing), APO = Apollo (Earth-crossing, a > 1 AU), ATE = Aten (Earth-crossing, a < 1 AU), MBA = Main Belt, TJN = Jupiter Trojan." />
        <Row label="NEO" value={a.neo ?? '—'}
          tooltip="Near-Earth Object (perihelion < 1.3 AU). Often lower-transfer-energy targets than main-belt asteroids (typically dv < ~7 km/s)." />
        <Row label="PHA" value={a.pha ?? '—'}
          tooltip="Potentially Hazardous Asteroid (MOID < 0.05 AU and H < 22). Indicates close Earth approaches relevant for planetary-defense monitoring." />
        <Row label="Rank" value={fmt(a.economic_priority_rank, 0)}
          tooltip="Economic priority rank among 1,521,843 scored objects (1 = highest mission-priority candidate). Ordered by precious_value \u00d7 accessibility." />
      </div>

      <div className="detail-section">
        <h3>Orbital Elements</h3>
        <Row label="Semi-major axis" value={`${fmt(a.a_au, 4)} AU`}
          tooltip="Average Sun distance (AU). Determines orbital period and transfer energy. Main belt: 2.1-3.3 AU, NEAs: < 1.3 AU. 1 AU = 149.6M km." />
        <Row label="Eccentricity" value={fmt(a.eccentricity, 4)}
          tooltip="Orbit shape: 0 = circular, ~1 = highly elliptical. Higher eccentricity increases dv variance across launch windows." />
        <Row label="Inclination" value={`${fmt(a.inclination_deg, 2)} deg`}
          tooltip="Orbit plane angle vs ecliptic (deg). Higher inclination increases plane-change energy cost nonlinearly. Most accessible targets: < 10 deg." />
        <Row label="Delta-v" value={`${fmt(a.delta_v_km_s, 2)} km/s`}
          tooltip="Two-impulse Earth-departure transfer proxy (km/s), not trajectory-optimized. Lower values reduce transport cost exponentially. < 4 km/s: high-accessibility targets." />
        <Row label="Tisserand (J)" value={fmt(a.tisserand_jupiter, 3)}
          tooltip="Tisserand parameter relative to Jupiter (dimensionless). Used to distinguish dynamical populations (main belt vs comet-like orbits)." />
        <Row label="MOID" value={`${fmt(a.moid_au, 4)} AU`}
          tooltip="Minimum Orbit Intersection Distance with Earth (AU). Measures geometric proximity of orbital paths; used for hazard classification, not mission cost estimation." />
        <Row label="Precision" value={a.orbital_precision_source ?? '—'}
          tooltip='Orbital element source. "horizons" = higher-precision perturbed elements including planetary interactions from JPL Horizons (NEAs only). "sbdb" = two-body osculating elements.' />
      </div>

      <div className="detail-section">
        <h3>Physical</h3>
        <Row label="Diameter" value={`${fmt(a.diameter_estimated_km, 3)} km (${a.diameter_source ?? '?'})`}
          tooltip='Estimated diameter (km). "measured" = direct observation (~10% uncertainty), "neowise" = thermal IR (~10%), "estimated" = from H magnitude (~30%).' />
        <Row label="Total Mass" value={fmtMass(a.estimated_mass_kg)}
          tooltip="Mass (kg) estimated from diameter and class-dependent density assumptions. Typical uncertainty \u2248\u00b150%." />
        <Row label="Gravity" value={`${fmt(a.surface_gravity_m_s2, 4)} m/s\u00b2`}
          tooltip="Surface gravity (m/s\u00b2), spherical-body approximation. Constrains anchoring stability and likelihood of regolith retention." />
        <Row label="Rotation" value={a.rotation_hours ? `${fmt(a.rotation_hours, 2)} h` : '—'}
          tooltip="Rotation period (hours). Very fast rotators (< 2h) approach structural spin limits; very slow rotators (> 100h) experience large thermal gradients. Optimal mining range: 2-24h." />
        <Row label="Rot. Feasibility" value={a.rotation_feasibility != null ? fmt(a.rotation_feasibility) : '—'}
          tooltip="Rotation feasibility score [0-1]. 1.0 = ideal (2-24h range). Penalizes spin-barrier (< 2h) and very slow rotators (> 100h). Only available when rotation period is known." />
        <Row label="Regolith" value={a.regolith_likelihood != null ? fmt(a.regolith_likelihood) : '—'}
          tooltip="Regolith likelihood score [0-1]. Empirical proxy derived from diameter and rotation; higher values indicate greater probability of loose surface material." />
        <Row label="Albedo" value={fmt(a.albedo, 3)}
          tooltip="Surface reflectivity [0-1]. Constrains composition: C ~0.06, S ~0.25, M ~0.14, V ~0.35. Used as compositional prior when spectral data is unavailable." />
      </div>

      <div className="detail-section">
        <h3>Composition ({a.composition_class ?? 'U'})</h3>
        <Row label="Confidence" value={a.composition_confidence != null ? `${(a.composition_confidence * 100).toFixed(0)}%` : '—'}
          tooltip="Classification confidence [0-100%]. Higher confidence reduces uncertainty in inferred resource composition and value estimates." />
        <Row label="Source" value={a.composition_source ?? '—'}
          tooltip="Classification method (highest-confidence source available): taxonomy > spectral type > SDSS colors > MOVIS NIR > albedo > uniform prior." />
        <Row label="Resource Value" value={`${fmtUsd(a.resource_value_usd_per_kg)}/kg`}
          tooltip="Estimated total value (USD/kg raw material). Class-average prior combining water, bulk metals, and precious metals; object-specific metal estimates shown below." />
      </div>

      <div className="detail-section">
        <h3>Extractable Resources</h3>
        <Row label="Water" value={inv.waterKg > 0 ? `${fmtKg(inv.waterKg)} (${fmtUsd(inv.waterUsd)})` : '—'}
          tooltip="Extractable H2O (kg/USD). Typical C-type prior (~15 wt%; meteorite-analog estimate), 60% assumed yield. Valued at $500/kg as cislunar propellant." />
        <Row label="Bulk Metals" value={inv.metalKg > 0 ? `${fmtKg(inv.metalKg)} (${fmtUsd(inv.metalUsd)})` : '—'}
          tooltip="Extractable Fe/Ni/Co (kg/USD). M-type: 98.6 wt%, S-type: ~20 wt%. 50% assumed yield. $50/kg in-orbit construction value. Source: Lodders et al. (2025)." />
        {inv.perMetal.filter((m) => m.kg > 0.01).map((m) => (
          <Row
            key={m.name}
            label={m.name.charAt(0).toUpperCase() + m.name.slice(1)}
            value={`${fmtKg(m.kg)} (${fmtUsd(m.usd)})`}
            tooltip={METAL_TOOLTIPS[m.name]}
          />
        ))}
        <Row label="Total PGM" value={`${fmtKg(inv.preciousKg)} (${fmtUsd(inv.preciousUsd)})`}
          tooltip="Sum of 7 extractable precious metals (kg/USD). Principal revenue component in specimen-return mission scenarios." />
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
              <td className="detail-label" title="Return payload mass per mission scenario. Refined material returned to Earth/cislunar orbit.">Payload</td>
              <td>{fmtKg(s1.payloadKg)}</td>
              <td>{fmtKg(s10.payloadKg)}</td>
              <td>{fmtKg(s100.payloadKg)}</td>
            </tr>
            <tr>
              <td className="detail-label" title="Gross revenue (USD) from extracted specimen at spot prices. Weighted across 7 metals by composition concentrations.">Revenue</td>
              <td>{fmtUsd(s1.revenue)}</td>
              <td>{fmtUsd(s10.revenue)}</td>
              <td>{fmtUsd(s100.revenue)}</td>
            </tr>
            <tr>
              <td className="detail-label" title="Total mission cost (USD): $300M fixed + transport ($2,700/kg \u00d7 exp(2 \u00d7 dv / 3.14)) + extraction ($5,000/kg). Transport dominates at higher \u0394v.">Cost</td>
              <td>{fmtUsd(s1.totalCost)}</td>
              <td>{fmtUsd(s10.totalCost)}</td>
              <td>{fmtUsd(s100.totalCost)}</td>
            </tr>
            <tr>
              <td className="detail-label" title="Revenue \u2212 total cost (USD). Green/red indicates sign. Strongly sensitive to transport \u0394v and metal concentration.">Profit</td>
              <td className={s1.feasible ? 'profit-positive' : 'profit-negative'}>{fmtUsd(s1.profit)}</td>
              <td className={s10.feasible ? 'profit-positive' : 'profit-negative'}>{fmtUsd(s10.profit)}</td>
              <td className={s100.feasible ? 'profit-positive' : 'profit-negative'}>{fmtUsd(s100.profit)}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div className="detail-section">
        <h3>Break-even</h3>
        <Row label="Total" value={a.break_even_kg ? fmtKg(a.break_even_kg) : '—'}
          tooltip="Minimum refined precious-metal mass required to cover fixed mission cost and transport under current scenario assumptions." />
        <Row label="Viable" value={a.is_viable ? 'Yes' : 'No'}
          tooltip="Indicates whether estimated extractable precious metals exceed break-even threshold under current mission assumptions (609 of 1,521,843 objects)." />
      </div>
    </div>
  );
}
