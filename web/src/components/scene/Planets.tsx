import { useMemo } from 'react';
import * as THREE from 'three';
import { Html } from '@react-three/drei';
import { keplerToCartesian, propagateMeanAnomaly } from '../../utils/kepler';

const AU_KM = 149_597_870.7; // 1 AU in km

interface PlanetDef {
  name: string;
  a: number; e: number; i: number; om: number; w: number; ma0: number;
  color: string;
  size: number; // visual size in AU (exaggerated)
}

const PLANET_ELEMENTS: PlanetDef[] = [
  { name: 'Mercury', a: 0.387, e: 0.206, i: 7.00, om: 48.33, w: 29.12, ma0: 174.80, color: '#a0826d', size: 0.015 },
  { name: 'Venus',   a: 0.723, e: 0.007, i: 3.39, om: 76.68, w: 54.88, ma0: 50.42,  color: '#e8cda0', size: 0.03 },
  { name: 'Earth',   a: 1.000, e: 0.017, i: 0.00, om: -11.26, w: 102.95, ma0: 357.52, color: '#4488ff', size: 0.03 },
  { name: 'Mars',    a: 1.524, e: 0.093, i: 1.85, om: 49.56, w: 286.50, ma0: 19.37,  color: '#cc5533', size: 0.02 },
  { name: 'Jupiter', a: 5.203, e: 0.049, i: 1.30, om: 100.46, w: 14.33, ma0: 20.02,  color: '#d4a574', size: 0.10 },
  { name: 'Saturn',  a: 9.537, e: 0.054, i: 2.49, om: 113.64, w: 92.43, ma0: 317.02, color: '#e8d5a0', size: 0.08 },
  { name: 'Uranus',  a: 19.19, e: 0.047, i: 0.77, om: 74.01, w: 170.96, ma0: 142.24, color: '#88ccdd', size: 0.06 },
  { name: 'Neptune', a: 30.07, e: 0.009, i: 1.77, om: 131.78, w: 44.97, ma0: 256.23, color: '#4466cc', size: 0.06 },
];

/** Approximate orbit circumference via Ramanujan's formula for ellipse. */
function orbitCircumferenceKm(a: number, e: number): number {
  const b = a * Math.sqrt(1 - e * e);
  const h = ((a - b) / (a + b)) ** 2;
  const circumAU = Math.PI * (a + b) * (1 + (3 * h) / (10 + Math.sqrt(4 - 3 * h)));
  return circumAU * AU_KM;
}

/** Orbital period from Kepler's third law. */
function orbitalPeriod(a: number): { years: number; days: number; label: string } {
  const years = Math.pow(a, 1.5);
  const days = years * 365.25;
  if (years >= 1) return { years, days, label: `${years.toFixed(1)} yr` };
  return { years, days, label: `${days.toFixed(0)} d` };
}

function formatKm(km: number): string {
  if (km >= 1e9) return `${(km / 1e9).toFixed(1)}B km`;
  if (km >= 1e6) return `${(km / 1e6).toFixed(0)}M km`;
  return `${(km / 1e3).toFixed(0)}K km`;
}

function OrbitRing({ planet, onClick }: { planet: PlanetDef; onClick: () => void }) {
  const { lineObj, labelPos, circumKm, period } = useMemo(() => {
    const points: THREE.Vector3[] = [];
    for (let j = 0; j <= 256; j++) {
      const ma = (360 * j) / 256;
      const pos = keplerToCartesian({ a: planet.a, e: planet.e, i: planet.i, om: planet.om, w: planet.w, ma });
      points.push(new THREE.Vector3(pos.x, pos.z, pos.y));
    }
    const geometry = new THREE.BufferGeometry().setFromPoints(points);
    const material = new THREE.LineBasicMaterial({
      color: planet.color,
      opacity: 0.6,
      transparent: true,
    });
    const line = new THREE.Line(geometry, material);
    // Label position: top of orbit (90 degrees)
    const labelPt = keplerToCartesian({ a: planet.a, e: planet.e, i: planet.i, om: planet.om, w: planet.w, ma: 90 });
    return {
      lineObj: line,
      labelPos: new THREE.Vector3(labelPt.x, labelPt.z, labelPt.y),
      circumKm: orbitCircumferenceKm(planet.a, planet.e),
      period: orbitalPeriod(planet.a),
    };
  }, [planet]);

  return (
    <group>
      <primitive object={lineObj} onClick={onClick} />
      <Html position={labelPos} center style={{ pointerEvents: 'none' }}>
        <div style={{
          color: planet.color,
          fontSize: '9px',
          opacity: 0.5,
          whiteSpace: 'nowrap',
          textShadow: '0 0 3px rgba(0,0,0,0.8)',
          userSelect: 'none',
        }}>
          {formatKm(circumKm)} | {period.label}
        </div>
      </Html>
    </group>
  );
}

interface Props {
  dayOffset: number;
  onSelectPlanet?: (name: string, position: THREE.Vector3) => void;
}

export function Planets({ dayOffset, onSelectPlanet }: Props) {
  const positions = useMemo(() => {
    return PLANET_ELEMENTS.map((p) => {
      const ma = propagateMeanAnomaly(p.ma0, p.a, dayOffset);
      const pos = keplerToCartesian({ a: p.a, e: p.e, i: p.i, om: p.om, w: p.w, ma });
      return { ...p, x: pos.x, y: pos.z, z: pos.y };
    });
  }, [dayOffset]);

  return (
    <group>
      {positions.map((p) => (
        <group key={p.name}>
          <OrbitRing
            planet={p}
            onClick={() => onSelectPlanet?.(p.name, new THREE.Vector3(p.x, p.y, p.z))}
          />
          <mesh
            position={[p.x, p.y, p.z]}
            onClick={() => onSelectPlanet?.(p.name, new THREE.Vector3(p.x, p.y, p.z))}
          >
            <sphereGeometry args={[p.size, 16, 16]} />
            <meshStandardMaterial color={p.color} emissive={p.color} emissiveIntensity={0.15} />
          </mesh>
          {/* Planet name label */}
          <Html position={[p.x, p.y + p.size + 0.03, p.z]} center style={{ pointerEvents: 'none' }}>
            <div style={{
              color: p.color,
              fontSize: '10px',
              fontWeight: 600,
              textShadow: '0 0 4px rgba(0,0,0,0.9)',
              userSelect: 'none',
            }}>
              {p.name}
            </div>
          </Html>
        </group>
      ))}
    </group>
  );
}
