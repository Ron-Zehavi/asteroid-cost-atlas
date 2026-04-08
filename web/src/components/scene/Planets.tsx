import { useMemo } from 'react';
import * as THREE from 'three';
import { Html, useTexture } from '@react-three/drei';
import { keplerToCartesian, propagateMeanAnomaly } from '../../utils/kepler';
import { DISTANCE_SCALE } from '../../utils/sceneConstants';
import { orbitCircumferenceKm, formatKm, orbitalPeriod } from '../../utils/orbitUtils';

interface PlanetDef {
  name: string;
  a: number; e: number; i: number; om: number; w: number; ma0: number;
  color: string;
  size: number;
  texture: string;
}

export const PLANET_ELEMENTS: PlanetDef[] = [
  // Sizes: true radius in AU (radius_km / 149,597,870.7) | Distances: real AU
  { name: 'Mercury', a: 0.387, e: 0.206, i: 7.00, om: 48.33, w: 29.12, ma0: 174.80, color: '#a0826d', size: 0.0000163, texture: '/textures/2k_mercury.jpg' },
  { name: 'Venus',   a: 0.723, e: 0.007, i: 3.39, om: 76.68, w: 54.88, ma0: 50.42,  color: '#e8cda0', size: 0.0000404, texture: '/textures/2k_venus_surface.jpg' },
  { name: 'Earth',   a: 1.000, e: 0.017, i: 0.00, om: -11.26, w: 102.95, ma0: 357.52, color: '#4488ff', size: 0.0000426, texture: '/textures/2k_earth_daymap.jpg' },
  { name: 'Mars',    a: 1.524, e: 0.093, i: 1.85, om: 49.56, w: 286.50, ma0: 19.37,  color: '#cc5533', size: 0.0000227, texture: '/textures/2k_mars.jpg' },
  { name: 'Jupiter', a: 5.203, e: 0.049, i: 1.30, om: 100.46, w: 14.33, ma0: 20.02,  color: '#d4a574', size: 0.000467, texture: '/textures/2k_jupiter.jpg' },
  { name: 'Saturn',  a: 9.537, e: 0.054, i: 2.49, om: 113.64, w: 92.43, ma0: 317.02, color: '#e8d5a0', size: 0.000389, texture: '/textures/2k_saturn.jpg' },
  { name: 'Uranus',  a: 19.19, e: 0.047, i: 0.77, om: 74.01, w: 170.96, ma0: 142.24, color: '#88ccdd', size: 0.000170, texture: '/textures/2k_uranus.jpg' },
  { name: 'Neptune', a: 30.07, e: 0.009, i: 1.77, om: 131.78, w: 44.97, ma0: 256.23, color: '#4466cc', size: 0.000165, texture: '/textures/2k_neptune.jpg' },
];


function OrbitRing({ planet, onClick }: { planet: PlanetDef; onClick: () => void }) {
  const { lineObj, labelPos, circumKm, period } = useMemo(() => {
    const points: THREE.Vector3[] = [];
    const va = planet.a * DISTANCE_SCALE;
    const ve = planet.e;
    for (let j = 0; j <= 256; j++) {
      const ma = (360 * j) / 256;
      const pos = keplerToCartesian({ a: va, e: ve, i: planet.i, om: planet.om, w: planet.w, ma });
      points.push(new THREE.Vector3(pos.x, pos.z, pos.y));
    }
    const geometry = new THREE.BufferGeometry().setFromPoints(points);
    const material = new THREE.LineBasicMaterial({
      color: planet.color,
      opacity: 0.6,
      transparent: true,
    });
    const line = new THREE.Line(geometry, material);
    const labelPt = keplerToCartesian({ a: va, e: ve, i: planet.i, om: planet.om, w: planet.w, ma: 90 });
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

function TexturedPlanet({ planet, position, onClick, tintColor, tintIntensity }: {
  planet: PlanetDef & { x: number; y: number; z: number };
  position: [number, number, number];
  onClick: () => void;
  tintColor?: string;
  tintIntensity?: number;
}) {
  const tex = useTexture(planet.texture);
  const emissive = tintColor ?? planet.color;
  const emissiveIntensity = tintColor ? (tintIntensity ?? 0.5) : 0.05;

  return (
    <mesh position={position} onClick={onClick}>
      <sphereGeometry args={[planet.size, 32, 32]} />
      <meshStandardMaterial map={tex} emissive={emissive} emissiveIntensity={emissiveIntensity} />
    </mesh>
  );
}

interface Props {
  dayOffset: number;
  onSelectPlanet?: (name: string, position: THREE.Vector3) => void;
  /** Optional emissive tint for Earth (e.g. green during a launch window). */
  earthTint?: string | null;
}

export function Planets({ dayOffset, onSelectPlanet, earthTint }: Props) {
  const positions = useMemo(() => {
    return PLANET_ELEMENTS.map((p) => {
      const ma = propagateMeanAnomaly(p.ma0, p.a, dayOffset);
      const pos = keplerToCartesian({
        a: p.a * DISTANCE_SCALE, e: p.e, i: p.i,
        om: p.om, w: p.w, ma,
      });
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
          <TexturedPlanet
            planet={p}
            position={[p.x, p.y, p.z]}
            onClick={() => onSelectPlanet?.(p.name, new THREE.Vector3(p.x, p.y, p.z))}
            tintColor={p.name === 'Earth' ? earthTint ?? undefined : undefined}
          />
          {/* Planet name label — clickable to center camera */}
          <Html position={[p.x, p.y + p.size + 0.03, p.z]} center>
            <div
              onClick={(e) => { e.stopPropagation(); onSelectPlanet?.(p.name, new THREE.Vector3(p.x, p.y, p.z)); }}
              style={{
                color: p.color,
                fontSize: '10px',
                fontWeight: 600,
                textShadow: '0 0 4px rgba(0,0,0,0.9)',
                cursor: 'pointer',
              }}>
              {p.name}
            </div>
          </Html>
        </group>
      ))}
    </group>
  );
}
