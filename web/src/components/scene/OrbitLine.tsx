import { useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { Html } from '@react-three/drei';
import type { Asteroid } from '../../types/asteroid';
import { keplerToCartesian, orbitPoints } from '../../utils/kepler';
import { DISTANCE_SCALE } from '../../utils/sceneConstants';
import { orbitCircumferenceKm, formatKm, orbitalPeriod } from '../../utils/orbitUtils';
import { spotlightFlight } from '../../utils/spotlight';

interface Props {
  asteroid: Asteroid;
}

const SEGMENTS = 256;

export function OrbitLine({ asteroid }: Props) {
  const { group, geometry, labelPos, circumKm, period } = useMemo(() => {
    const a = asteroid;
    if (!a.a_au || a.eccentricity == null || a.inclination_deg == null) {
      return { group: null, geometry: null, labelPos: null, circumKm: 0, period: '' };
    }

    const el = {
      a: a.a_au * DISTANCE_SCALE,
      e: a.eccentricity,
      i: a.inclination_deg,
      om: a.long_asc_node_deg ?? 0,
      w: a.arg_perihelion_deg ?? 0,
      ma: 0,
    };

    const pts = orbitPoints(el, SEGMENTS);
    const vectors = pts.map((p) => new THREE.Vector3(p.x, p.z, p.y));
    const geo = new THREE.BufferGeometry().setFromPoints(vectors);
    const core = new THREE.Line(geo, new THREE.LineBasicMaterial({
      color: '#4fc3f7',
      opacity: 0.85,
      transparent: true,
    }));
    // Additive second pass over the same geometry so the lit orbit glows.
    const glow = new THREE.Line(geo, new THREE.LineBasicMaterial({
      color: '#9fdcff',
      opacity: 0.35,
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }));
    const g = new THREE.Group();
    g.add(core, glow);

    // Label at top of orbit (90 degrees)
    const lp = keplerToCartesian({ ...el, ma: 90 });
    const labelPosition = new THREE.Vector3(lp.x, lp.z, lp.y);

    return {
      group: g,
      geometry: geo,
      labelPos: labelPosition,
      circumKm: orbitCircumferenceKm(a.a_au, a.eccentricity),
      period: orbitalPeriod(a.a_au).label,
    };
  }, [asteroid]);

  // Light the orbit up progressively as the spotlight flight approaches:
  // the drawn path traces the ellipse in step with the camera.
  const drawnRef = useRef(-1);
  useFrame(() => {
    if (!geometry) return;
    const p = spotlightFlight.active ? spotlightFlight.progress : 1;
    const n = Math.max(2, Math.ceil(p * (SEGMENTS + 1)));
    if (n !== drawnRef.current) {
      geometry.setDrawRange(0, n);
      drawnRef.current = n;
    }
  });

  if (!group) return null;

  return (
    <group>
      <primitive object={group} />
      {labelPos && (
        <Html position={labelPos} center style={{ pointerEvents: 'none' }}>
          <div key={asteroid.spkid} className="orbit-line-label">
            {formatKm(circumKm)} | {period}
          </div>
        </Html>
      )}
    </group>
  );
}
