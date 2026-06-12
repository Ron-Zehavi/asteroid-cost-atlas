import { useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import { Html, useTexture } from '@react-three/drei';
import * as THREE from 'three';
import type { Asteroid } from '../../types/asteroid';
import { CLASS_TEXTURE_PATHS, CLASS_TINT, classOf } from './classVisuals';
import { KM_PER_AU, sizeComparison, spotlightFlight } from '../../utils/spotlight';

/** Deterministic PRNG so every asteroid always grows the same rock shape. */
function mulberry32(seed: number) {
  let a = seed >>> 0;
  return () => {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Irregular rock: icosphere displaced by seeded plane waves. Displacement is
 *  a pure function of vertex direction, so duplicated seam vertices deform
 *  identically and the surface stays watertight. */
function makeRockGeometry(spkid: number): THREE.BufferGeometry {
  const geo = new THREE.IcosahedronGeometry(1, 4);
  const rand = mulberry32(spkid);
  const waves = Array.from({ length: 6 }, () => ({
    dir: new THREE.Vector3(rand() - 0.5, rand() - 0.5, rand() - 0.5).normalize(),
    freq: 1.5 + rand() * 6,
    phase: rand() * Math.PI * 2,
    amp: 0.5 + rand() * 0.5,
  }));
  const pos = geo.getAttribute('position') as THREE.BufferAttribute;
  const v = new THREE.Vector3();
  for (let i = 0; i < pos.count; i++) {
    v.fromBufferAttribute(pos, i).normalize();
    let n = 0;
    let ampSum = 0;
    for (const w of waves) {
      n += w.amp * Math.sin(w.freq * v.dot(w.dir) + w.phase);
      ampSum += w.amp;
    }
    const bump = 1 + 0.26 * (n / ampSum);
    pos.setXYZ(i, v.x * bump, v.y * bump, v.z * bump);
  }
  geo.computeVertexNormals();
  return geo;
}

interface Props {
  asteroid: Asteroid;
  position: THREE.Vector3;
  /** Rendered radius in world units (enlarged; labeled honestly below the rock). */
  radius: number;
  /** Optional emissive override (e.g. arrival-window green). */
  tint?: string | null;
}

export function SpotlightAsteroid({ asteroid, position, radius, tint }: Props) {
  const cls = classOf(asteroid);
  const texture = useTexture(CLASS_TEXTURE_PATHS[cls]);
  const meshRef = useRef<THREE.Mesh>(null);

  const geometry = useMemo(() => makeRockGeometry(asteroid.spkid), [asteroid.spkid]);

  const { spinAxis, spinRate } = useMemo(() => {
    const rand = mulberry32(asteroid.spkid + 1);
    const axis = new THREE.Vector3(rand() - 0.5, 0.5 + rand() * 0.5, rand() - 0.5).normalize();
    // Real periods are hours; compress to a contemplative on-screen tumble,
    // still proportional to the measured rotation when we have one.
    const periodSec = asteroid.rotation_hours
      ? Math.min(120, Math.max(12, asteroid.rotation_hours * 6))
      : 45;
    return { spinAxis: axis, spinRate: (2 * Math.PI) / periodSec };
  }, [asteroid.spkid, asteroid.rotation_hours]);

  useFrame((_, delta) => {
    const mesh = meshRef.current;
    if (!mesh) return;
    mesh.rotateOnAxis(spinAxis, spinRate * delta);
    // Grow in over the back half of the camera flight so the rock "resolves"
    // out of the dot as we arrive.
    const p = spotlightFlight.progress;
    const grow = p < 0.5 ? 0 : (p - 0.5) / 0.5;
    mesh.scale.setScalar(radius * Math.max(0.0001, grow * grow * (3 - 2 * grow)));
  });

  // Key light placed sunward of the rock; intensity scaled to its distance
  // (physical lights decay ~1/d²) so only the rock's neighborhood is lit.
  const lightDist = radius * 8;
  const lightPos = useMemo(() => {
    const toSun = position.clone().multiplyScalar(-1).normalize();
    return position.clone().add(toSun.multiplyScalar(lightDist));
  }, [position, lightDist]);

  const realDiamKm = asteroid.diameter_estimated_km;
  const exaggeration = realDiamKm
    ? (radius * 2) / (realDiamKm / KM_PER_AU)
    : null;
  const comparison = sizeComparison(realDiamKm);

  return (
    <group>
      <pointLight position={lightPos} intensity={lightDist * lightDist * 6} decay={2} color="#fff4e0" />
      <mesh ref={meshRef} position={position} geometry={geometry}>
        <meshStandardMaterial
          map={texture}
          roughness={0.95}
          metalness={cls === 'M' ? 0.55 : 0.05}
          emissive={tint ?? CLASS_TINT[cls]}
          emissiveIntensity={tint ? 0.5 : 0.06}
        />
      </mesh>
      <Html
        position={[position.x, position.y - radius * 1.7, position.z]}
        center
        style={{ pointerEvents: 'none' }}
      >
        <div key={asteroid.spkid} className="spotlight-rock-caption">
          {realDiamKm
            ? <>true diameter {realDiamKm < 1 ? realDiamKm.toFixed(2) : realDiamKm.toFixed(1)} km — {comparison}</>
            : <>diameter unknown</>}
          {exaggeration && exaggeration > 2 && (
            <span className="spotlight-rock-exagg">
              {' '}· shown ~{Math.round(exaggeration).toLocaleString()}× enlarged
            </span>
          )}
        </div>
      </Html>
    </group>
  );
}
