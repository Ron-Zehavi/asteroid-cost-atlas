import { useMemo } from 'react';
import * as THREE from 'three';
import { Html } from '@react-three/drei';
import type { Asteroid } from '../../types/asteroid';
import { keplerToCartesian, orbitPoints } from '../../utils/kepler';
import { DISTANCE_SCALE } from '../../utils/sceneConstants';
import { orbitCircumferenceKm, formatKm, orbitalPeriod } from '../../utils/orbitUtils';

interface Props {
  asteroid: Asteroid;
}

export function OrbitLine({ asteroid }: Props) {
  const { lineObj, labelPos, circumKm, period } = useMemo(() => {
    const a = asteroid;
    if (!a.a_au || a.eccentricity == null || a.inclination_deg == null) {
      return { lineObj: null, labelPos: null, circumKm: 0, period: '' };
    }

    const el = {
      a: a.a_au * DISTANCE_SCALE,
      e: a.eccentricity,
      i: a.inclination_deg,
      om: a.long_asc_node_deg ?? 0,
      w: a.arg_perihelion_deg ?? 0,
      ma: 0,
    };

    const pts = orbitPoints(el, 256);
    const vectors = pts.map((p) => new THREE.Vector3(p.x, p.z, p.y));
    const geometry = new THREE.BufferGeometry().setFromPoints(vectors);
    const material = new THREE.LineBasicMaterial({
      color: '#4fc3f7',
      opacity: 0.7,
      transparent: true,
    });
    const line = new THREE.Line(geometry, material);

    // Label at top of orbit (90 degrees)
    const lp = keplerToCartesian({ ...el, ma: 90 });
    const labelPosition = new THREE.Vector3(lp.x, lp.z, lp.y);

    return {
      lineObj: line,
      labelPos: labelPosition,
      circumKm: orbitCircumferenceKm(a.a_au, a.eccentricity),
      period: orbitalPeriod(a.a_au).label,
    };
  }, [asteroid]);

  if (!lineObj) return null;

  return (
    <group>
      <primitive object={lineObj} />
      {labelPos && (
        <Html position={labelPos} center style={{ pointerEvents: 'none' }}>
          <div style={{
            color: '#4fc3f7',
            fontSize: '10px',
            opacity: 0.7,
            whiteSpace: 'nowrap',
            textShadow: '0 0 4px rgba(0,0,0,0.9)',
            userSelect: 'none',
          }}>
            {formatKm(circumKm)} | {period}
          </div>
        </Html>
      )}
    </group>
  );
}
