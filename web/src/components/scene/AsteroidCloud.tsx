import { useCallback, useMemo, useRef } from 'react';
import { useThree } from '@react-three/fiber';
import * as THREE from 'three';
import type { Asteroid } from '../../types/asteroid';
import { keplerToCartesian, propagateMeanAnomaly } from '../../utils/kepler';
import { DISTANCE_SCALE } from '../../utils/sceneConstants';

const CLASS_COLORS: Record<string, [number, number, number]> = {
  C: [0.3, 0.5, 0.9],
  S: [0.9, 0.8, 0.3],
  M: [0.7, 0.7, 0.8],
  V: [0.9, 0.3, 0.3],
  U: [0.5, 0.5, 0.5],
};

// Custom shader: min 1px, round points (circle discard), soft glow
const vertexShader = `
  attribute float aSize;
  varying vec3 vColor;
  void main() {
    vColor = color;
    vec4 mvPos = modelViewMatrix * vec4(position, 1.0);
    gl_Position = projectionMatrix * mvPos;
    // aSize = diameter in AU. Scale to screen pixels with distance attenuation.
    float trueSize = aSize * (800.0 / -mvPos.z);
    // Minimum 4px so asteroids are always visible even fully zoomed out.
    gl_PointSize = max(4.0, trueSize);
  }
`;

const fragmentShader = `
  varying vec3 vColor;
  void main() {
    vec2 c = gl_PointCoord - 0.5;
    float dist = length(c);
    if (dist > 0.5) discard;
    // Round shape: solid core + soft glow edge
    float core = 1.0 - smoothstep(0.0, 0.3, dist);
    float glow = 1.0 - smoothstep(0.15, 0.5, dist);
    float alpha = core * 1.0 + glow * 0.7;
    // Brighten center for glow effect
    vec3 col = vColor + core * 0.6;
    gl_FragColor = vec4(col, alpha);
  }
`;

interface Props {
  asteroids: Asteroid[];
  colorBy: 'composition' | 'delta_v' | 'viable' | 'confidence';
  dayOffset?: number;
  onClickIndex?: (index: number) => void;
}

export function AsteroidCloud({ asteroids, colorBy, dayOffset = 0, onClickIndex }: Props) {
  const pointsRef = useRef<THREE.Points>(null);
  const { camera, raycaster, pointer } = useThree();

  const { positions, colors, sizes } = useMemo(() => {
    const pos = new Float32Array(asteroids.length * 3);
    const col = new Float32Array(asteroids.length * 3);
    const sz = new Float32Array(asteroids.length);

    for (let i = 0; i < asteroids.length; i++) {
      const a = asteroids[i];

      if (a.a_au && a.eccentricity != null && a.inclination_deg != null) {
        const baseMa = a.mean_anomaly_deg ?? 0;
        const epochDays = a.epoch_mjd ? a.epoch_mjd - 51544.5 : 0;
        const ma = propagateMeanAnomaly(baseMa, a.a_au, dayOffset - epochDays);
        const el = {
          a: a.a_au * DISTANCE_SCALE, e: a.eccentricity, i: a.inclination_deg,
          om: a.long_asc_node_deg ?? 0, w: a.arg_perihelion_deg ?? 0, ma,
        };
        const p = keplerToCartesian(el);
        pos[i * 3] = p.x;
        pos[i * 3 + 1] = p.z;
        pos[i * 3 + 2] = p.y;
      }

      // Size = actual diameter in AU (1 AU = 149,597,870.7 km)
      const diamKm = a.diameter_estimated_km ?? 0.01;
      sz[i] = diamKm / 149_597_870.7;

      // Color — default white, optional tinting by mode
      let r = 0.85, g = 0.85, b = 0.9;
      if (colorBy === 'composition') {
        const cc = CLASS_COLORS[a.composition_class ?? 'U'] ?? CLASS_COLORS.U;
        // Blend class color with white (70% white, 30% class)
        r = 0.7 + cc[0] * 0.3;
        g = 0.7 + cc[1] * 0.3;
        b = 0.7 + cc[2] * 0.3;
      } else if (colorBy === 'delta_v' && a.delta_v_km_s != null) {
        const t = Math.min(a.delta_v_km_s / 15, 1);
        r = 0.5 + t * 0.5; g = 0.5 + (1 - t) * 0.5; b = 0.5;
      } else if (colorBy === 'viable') {
        if (a.is_viable) { r = 0.5; g = 1.0; b = 0.5; }
        else { r = 0.7; g = 0.7; b = 0.75; }
      } else if (colorBy === 'confidence') {
        const conf = a.composition_confidence ?? 0;
        // Red (low confidence) → Yellow (medium) → Green (high)
        if (conf < 0.3) { r = 0.9; g = 0.3; b = 0.2; }
        else if (conf < 0.7) { r = 0.9; g = 0.8; b = 0.2; }
        else { r = 0.2; g = 0.9; b = 0.3; }
      }
      col[i * 3] = r;
      col[i * 3 + 1] = g;
      col[i * 3 + 2] = b;
    }

    return { positions: pos, colors: col, sizes: sz };
  }, [asteroids, colorBy, dayOffset]);

  const handleClick = useCallback(() => {
    if (!pointsRef.current || !onClickIndex) return;
    raycaster.setFromCamera(pointer, camera);
    raycaster.params.Points = { threshold: 0.15 };
    const hits = raycaster.intersectObject(pointsRef.current);
    if (hits.length > 0 && hits[0].index != null) {
      onClickIndex(hits[0].index);
    }
  }, [camera, pointer, raycaster, onClickIndex]);

  const material = useMemo(() => new THREE.ShaderMaterial({
    vertexShader,
    fragmentShader,
    vertexColors: true,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  }), []);

  if (asteroids.length === 0) return null;

  return (
    <points ref={pointsRef} onClick={handleClick} material={material}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
        <bufferAttribute attach="attributes-color" args={[colors, 3]} />
        <bufferAttribute attach="attributes-aSize" args={[sizes, 1]} />
      </bufferGeometry>
    </points>
  );
}
