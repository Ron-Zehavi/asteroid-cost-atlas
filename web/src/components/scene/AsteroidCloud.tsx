import { useCallback, useMemo, useRef } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import { useTexture } from '@react-three/drei';
import * as THREE from 'three';
import type { Asteroid } from '../../types/asteroid';
import { keplerToCartesian, propagateMeanAnomaly } from '../../utils/kepler';
import { DISTANCE_SCALE } from '../../utils/sceneConstants';

type CompositionClass = 'C' | 'S' | 'M' | 'V' | 'U';

const KM_PER_AU = 149_597_870.7;
/** Minimum on-screen pixel diameter so distant asteroids stay visible/clickable. */
const MIN_PIXEL_DIAMETER = 6;

/** Subtle emissive tint per class — texture stays the dominant visual cue. */
const CLASS_TINT: Record<CompositionClass, string> = {
  C: '#5577aa',
  S: '#aa9955',
  M: '#888899',
  V: '#aa5544',
  U: '#666666',
};

const CLASS_TEXTURE_PATHS: Record<CompositionClass, string> = {
  C: '/textures/2k_ceres.jpg',
  S: '/textures/2k_eris.jpg',
  M: '/textures/2k_haumea.jpg',
  V: '/textures/2k_makemake.jpg',
  U: '/textures/2k_moon.jpg',
};

const ALL_TEXTURE_PATHS = [
  CLASS_TEXTURE_PATHS.C,
  CLASS_TEXTURE_PATHS.S,
  CLASS_TEXTURE_PATHS.M,
  CLASS_TEXTURE_PATHS.V,
  CLASS_TEXTURE_PATHS.U,
];

function classOf(a: Asteroid): CompositionClass {
  const c = a.composition_class;
  if (c === 'C' || c === 'S' || c === 'M' || c === 'V') return c;
  return 'U';
}

interface Props {
  asteroids: Asteroid[];
  colorBy: 'composition' | 'delta_v' | 'viable' | 'confidence';
  dayOffset?: number;
  onClickIndex?: (index: number) => void;
  /** Asteroid spkid to highlight (e.g. selected target during arrival window). */
  highlightedSpkid?: number | null;
  /** Emissive color override for the highlighted asteroid. */
  highlightTint?: string | null;
}

/** Per-class instanced mesh group: one InstancedMesh per composition class so
 *  all asteroids of that class share geometry/material/texture and one draw call.
 *  Positions and per-instance scales are updated in a single useFrame at the cloud level. */
const CLASS_ORDER: CompositionClass[] = ['C', 'S', 'M', 'V', 'U'];

export function AsteroidCloud({
  asteroids,
  colorBy,
  dayOffset = 0,
  onClickIndex,
  highlightedSpkid,
  highlightTint,
}: Props) {
  const textures = useTexture(ALL_TEXTURE_PATHS) as THREE.Texture[];
  const classToTexture: Record<CompositionClass, THREE.Texture> = useMemo(
    () => ({
      C: textures[0],
      S: textures[1],
      M: textures[2],
      V: textures[3],
      U: textures[4],
    }),
    [textures],
  );

  // Group asteroid indices by class so each InstancedMesh knows which asteroids to draw.
  const indicesByClass = useMemo(() => {
    const map: Record<CompositionClass, number[]> = { C: [], S: [], M: [], V: [], U: [] };
    asteroids.forEach((a, i) => {
      map[classOf(a)].push(i);
    });
    return map;
  }, [asteroids]);

  // Refs to each class's InstancedMesh
  const meshRefs = useRef<Record<CompositionClass, THREE.InstancedMesh | null>>({
    C: null, S: null, M: null, V: null, U: null,
  });

  const tintFor = useCallback((a: Asteroid): string => {
    if (colorBy === 'composition') return CLASS_TINT[classOf(a)];
    if (colorBy === 'delta_v' && a.delta_v_km_s != null) {
      const t = Math.min(a.delta_v_km_s / 15, 1);
      const r = Math.round((0.5 + t * 0.5) * 255);
      const g = Math.round((0.5 + (1 - t) * 0.5) * 255);
      return `rgb(${r},${g},80)`;
    }
    if (colorBy === 'viable') return a.is_viable ? '#44dd66' : '#888899';
    if (colorBy === 'confidence') {
      const conf = a.composition_confidence ?? 0;
      if (conf < 0.3) return '#dd5533';
      if (conf < 0.7) return '#ddcc33';
      return '#33dd55';
    }
    return CLASS_TINT[classOf(a)];
  }, [colorBy]);

  // Per-instance true radius (cached; only changes when asteroid list changes).
  const trueRadii = useMemo(() => {
    return asteroids.map((a) => {
      const diamKm = a.diameter_estimated_km ?? 0.02;
      return (diamKm / KM_PER_AU) / 2;
    });
  }, [asteroids]);

  // Cache positions: only recompute when asteroids list or dayOffset changes,
  // not every frame. Stored as a flat Float32Array for cache locality.
  const positionsCache = useMemo(() => {
    const pos = new Float32Array(asteroids.length * 3);
    for (let i = 0; i < asteroids.length; i++) {
      const a = asteroids[i];
      if (!a.a_au || a.eccentricity == null || a.inclination_deg == null) {
        pos[i * 3] = NaN;
        continue;
      }
      const epochDays = a.epoch_mjd ? a.epoch_mjd - 51544.5 : 0;
      const ma = propagateMeanAnomaly(a.mean_anomaly_deg ?? 0, a.a_au, dayOffset - epochDays);
      const p = keplerToCartesian({
        a: a.a_au * DISTANCE_SCALE,
        e: a.eccentricity,
        i: a.inclination_deg,
        om: a.long_asc_node_deg ?? 0,
        w: a.arg_perihelion_deg ?? 0,
        ma,
      });
      pos[i * 3] = p.x;
      pos[i * 3 + 1] = p.z;
      pos[i * 3 + 2] = p.y;
    }
    return pos;
  }, [asteroids, dayOffset]);

  const { camera, size } = useThree();
  const tmpMat = useMemo(() => new THREE.Matrix4(), []);
  const tmpScale = useMemo(() => new THREE.Vector3(), []);
  const tmpPos = useMemo(() => new THREE.Vector3(), []);
  const tmpQuat = useMemo(() => new THREE.Quaternion(), []);

  useFrame(() => {
    const persp = camera as THREE.PerspectiveCamera;
    const vFov = (persp.fov * Math.PI) / 180;
    const tanHalfFov = Math.tan(vFov / 2);
    const screenH = size.height;
    const camX = camera.position.x;
    const camY = camera.position.y;
    const camZ = camera.position.z;

    for (const cls of CLASS_ORDER) {
      const mesh = meshRefs.current[cls];
      const indices = indicesByClass[cls];
      if (!mesh || indices.length === 0) continue;

      for (let slot = 0; slot < indices.length; slot++) {
        const i = indices[slot];
        const px = positionsCache[i * 3];
        if (Number.isNaN(px)) {
          tmpMat.makeScale(0, 0, 0);
          mesh.setMatrixAt(slot, tmpMat);
          continue;
        }
        const py = positionsCache[i * 3 + 1];
        const pz = positionsCache[i * 3 + 2];

        const dx = px - camX;
        const dy = py - camY;
        const dz = pz - camZ;
        const distanceToCam = Math.sqrt(dx * dx + dy * dy + dz * dz);
        const worldPerPx = (2 * tanHalfFov * distanceToCam) / screenH;
        const minRadius = (MIN_PIXEL_DIAMETER / 2) * worldPerPx;
        const r = trueRadii[i] > minRadius ? trueRadii[i] : minRadius;

        tmpPos.set(px, py, pz);
        tmpScale.set(r, r, r);
        tmpQuat.identity();
        tmpMat.compose(tmpPos, tmpQuat, tmpScale);
        mesh.setMatrixAt(slot, tmpMat);
      }
      mesh.instanceMatrix.needsUpdate = true;
    }
  });

  const handleClick = useCallback(
    (cls: CompositionClass, instanceId: number | undefined) => {
      if (instanceId == null || !onClickIndex) return;
      const asteroidIdx = indicesByClass[cls][instanceId];
      if (asteroidIdx != null) onClickIndex(asteroidIdx);
    },
    [indicesByClass, onClickIndex],
  );

  if (asteroids.length === 0) return null;

  return (
    <group>
      {CLASS_ORDER.map((cls) => {
        const count = indicesByClass[cls].length;
        if (count === 0) return null;
        const baseEmissive = (() => {
          if (colorBy === 'composition') return CLASS_TINT[cls];
          const firstIdx = indicesByClass[cls][0];
          return tintFor(asteroids[firstIdx]);
        })();
        return (
          <instancedMesh
            key={cls}
            ref={(m) => {
              meshRefs.current[cls] = m;
            }}
            args={[undefined, undefined, count]}
            onClick={(e) => {
              e.stopPropagation();
              handleClick(cls, e.instanceId);
            }}
          >
            <sphereGeometry args={[1, 6, 6]} />
            <meshStandardMaterial
              map={classToTexture[cls]}
              emissive={baseEmissive}
              emissiveIntensity={0.15}
            />
          </instancedMesh>
        );
      })}
      {/* Single highlighted asteroid (e.g. arrival window): rendered as an
          extra textured sphere on top of the instanced cloud, so only ONE
          asteroid is tinted instead of every member of its class. */}
      {highlightedSpkid != null && highlightTint && (
        <HighlightedAsteroid
          asteroids={asteroids}
          spkid={highlightedSpkid}
          tint={highlightTint}
          texture={(() => {
            const a = asteroids.find((x) => x.spkid === highlightedSpkid);
            return a ? classToTexture[classOf(a)] : classToTexture.U;
          })()}
          dayOffset={dayOffset}
        />
      )}
    </group>
  );
}

/** Single textured sphere drawn on top of the instanced cloud to highlight one asteroid. */
function HighlightedAsteroid({
  asteroids,
  spkid,
  tint,
  texture,
  dayOffset,
}: {
  asteroids: Asteroid[];
  spkid: number;
  tint: string;
  texture: THREE.Texture;
  dayOffset: number;
}) {
  const meshRef = useRef<THREE.Mesh>(null);
  const { camera, size } = useThree();
  const tmpVec = useMemo(() => new THREE.Vector3(), []);

  const asteroid = useMemo(() => asteroids.find((a) => a.spkid === spkid) ?? null, [asteroids, spkid]);

  const trueRadius = useMemo(() => {
    if (!asteroid) return 0;
    const diamKm = asteroid.diameter_estimated_km ?? 0.02;
    return (diamKm / KM_PER_AU) / 2;
  }, [asteroid]);

  useFrame(() => {
    const mesh = meshRef.current;
    if (!mesh || !asteroid) return;
    if (!asteroid.a_au || asteroid.eccentricity == null || asteroid.inclination_deg == null) {
      mesh.visible = false;
      return;
    }
    mesh.visible = true;
    const epochDays = asteroid.epoch_mjd ? asteroid.epoch_mjd - 51544.5 : 0;
    const ma = propagateMeanAnomaly(asteroid.mean_anomaly_deg ?? 0, asteroid.a_au, dayOffset - epochDays);
    const p = keplerToCartesian({
      a: asteroid.a_au * DISTANCE_SCALE,
      e: asteroid.eccentricity,
      i: asteroid.inclination_deg,
      om: asteroid.long_asc_node_deg ?? 0,
      w: asteroid.arg_perihelion_deg ?? 0,
      ma,
    });
    mesh.position.set(p.x, p.z, p.y);

    // Match the cloud's min-pixel-size scaling so the highlight stays visible.
    tmpVec.copy(mesh.position).sub(camera.position);
    const distanceToCam = tmpVec.length();
    const persp = camera as THREE.PerspectiveCamera;
    const vFov = (persp.fov * Math.PI) / 180;
    const worldPerPx = (2 * Math.tan(vFov / 2) * distanceToCam) / size.height;
    const minRadius = (MIN_PIXEL_DIAMETER / 2) * worldPerPx;
    // Slightly bigger than the cloud equivalent so it's clearly the highlight.
    const r = Math.max(trueRadius, minRadius) * 1.4;
    mesh.scale.setScalar(r);
  });

  if (!asteroid) return null;

  return (
    <mesh ref={meshRef}>
      <sphereGeometry args={[1, 12, 12]} />
      <meshStandardMaterial map={texture} emissive={tint} emissiveIntensity={0.7} />
    </mesh>
  );
}
