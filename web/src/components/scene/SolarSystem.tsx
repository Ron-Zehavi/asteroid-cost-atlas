import { useCallback, useEffect, useMemo, useRef } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { OrbitControls, Html, useTexture } from '@react-three/drei';
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib';
import * as THREE from 'three';
import { Planets, PLANET_ELEMENTS } from './Planets';
import { AsteroidCloud } from './AsteroidCloud';
import { OrbitLine } from './OrbitLine';
import { SunGlow } from './SunGlow';
import {
  computeHohmannTransfer,
  estimateLaunchWindows,
  getMissionPhase,
  getSpacecraftPosition,
  transferArcPoints,
} from '../../utils/transfer';

import { OrbitZones } from './OrbitZones';
import { TransferArc } from './TransferArc';
import type { Asteroid } from '../../types/asteroid';
import { keplerToCartesian, propagateMeanAnomaly } from '../../utils/kepler';
import { DISTANCE_SCALE } from '../../utils/sceneConstants';

interface Props {
  asteroids: Asteroid[];
  selected: Asteroid | null;
  colorBy: 'composition' | 'delta_v' | 'viable' | 'confidence';
  dayOffset: number;
  speed: number; // days per second (0 = paused)
  onDayOffsetChange: (d: number) => void;
  onSelectAsteroid?: (asteroid: Asteroid) => void;
}

function asteroidPosition(a: Asteroid, dayOffset: number): THREE.Vector3 | null {
  if (!a.a_au || a.eccentricity == null || a.inclination_deg == null) return null;
  const epochDays = a.epoch_mjd ? a.epoch_mjd - 51544.5 : 0;
  const ma = propagateMeanAnomaly(a.mean_anomaly_deg ?? 0, a.a_au, dayOffset - epochDays);
  const pos = keplerToCartesian({
    a: a.a_au * DISTANCE_SCALE, e: a.eccentricity, i: a.inclination_deg,
    om: a.long_asc_node_deg ?? 0, w: a.arg_perihelion_deg ?? 0, ma,
  });
  return new THREE.Vector3(pos.x, pos.z, pos.y);
}

/** Smooth continuous time advancement using useFrame. */
function TimeAdvancer({ speed, dayOffset, onChange }: {
  speed: number;
  dayOffset: number;
  onChange: (d: number) => void;
}) {
  const dayRef = useRef(dayOffset);
  dayRef.current = dayOffset;

  useFrame((_, delta) => {
    if (speed === 0) return;
    // delta is seconds since last frame (~0.016 at 60fps)
    // Advance by speed * delta days for smooth interpolation
    const newDay = dayRef.current + speed * delta;
    onChange(newDay);
  });

  return null;
}

function Starfield() {
  const tex = useTexture('/textures/2k_stars.jpg');
  return (
    <mesh>
      <sphereGeometry args={[300, 64, 32]} />
      <meshBasicMaterial map={tex} side={THREE.BackSide} depthWrite={false} />
    </mesh>
  );
}

/** Tracks a selected object: jumps camera on first select, then only updates
 *  the orbit‑controls pivot so zoom / rotate keep working. */
/** Focus override: null = track selected asteroid, 'static' = don't track, string = planet name to follow */
type FocusOverride = null | 'static' | string;

const EARTH_ELEMENTS = { a: 1.0, e: 0.017, i: 0.0, om: -11.26, w: 102.95, ma0: 357.52 };

/** Follows the current focus target each frame: planet, asteroid, or spacecraft. */
function FocusTracker({ focusOverrideRef, controls, dayOffset, selected }: {
  focusOverrideRef: React.MutableRefObject<FocusOverride>;
  controls: React.RefObject<OrbitControlsImpl | null>;
  dayOffset: number;
  selected: Asteroid | null;
}) {
  // Cache the transfer arc so we only recompute when the asteroid changes
  const cachedArc = useMemo(() => {
    if (!selected?.a_au || selected.eccentricity == null || selected.inclination_deg == null) return null;
    if (!selected.delta_v_km_s || selected.delta_v_km_s <= 0) return null;
    const transfer = computeHohmannTransfer(selected.a_au, selected.inclination_deg);
    const eMa = propagateMeanAnomaly(EARTH_ELEMENTS.ma0, EARTH_ELEMENTS.a, 0);
    const ePos = keplerToCartesian({ ...EARTH_ELEMENTS, a: EARTH_ELEMENTS.a * DISTANCE_SCALE, ma: eMa });
    const epochDays = selected.epoch_mjd ? selected.epoch_mjd - 51544.5 : 0;
    return { transfer, epochDays, ePos, selected };
  }, [selected]);

  useFrame(() => {
    if (!controls.current) return;
    const override = focusOverrideRef.current;

    // Planet name = track that planet
    if (override && override !== 'spacecraft') {
      const planet = PLANET_ELEMENTS.find((p) => p.name === override);
      if (!planet) return;
      const ma = propagateMeanAnomaly(planet.ma0, planet.a, dayOffset);
      const pos = keplerToCartesian({
        a: planet.a * DISTANCE_SCALE, e: planet.e, i: planet.i,
        om: planet.om, w: planet.w, ma,
      });
      controls.current.target.set(pos.x, pos.z, pos.y);
      controls.current.update();
      return;
    }

    // Spacecraft = track spacecraft along transfer arc
    if (override === 'spacecraft' && selected && cachedArc) {
      const { transfer, epochDays } = cachedArc;
      const windows = estimateLaunchWindows(transfer.synodic_days, transfer.transfer_days, dayOffset);
      const mission = getMissionPhase(windows, dayOffset);
      if (mission.phase !== 'in_transit') return;
      const w = mission.window;
      const eMa = propagateMeanAnomaly(EARTH_ELEMENTS.ma0, EARTH_ELEMENTS.a, w.windowEnd);
      const ePos = keplerToCartesian({ ...EARTH_ELEMENTS, a: EARTH_ELEMENTS.a * DISTANCE_SCALE, ma: eMa });
      const aMa = propagateMeanAnomaly(selected.mean_anomaly_deg ?? 0, selected.a_au!, w.arrivalDay - epochDays);
      const aPos = keplerToCartesian({
        a: selected.a_au! * DISTANCE_SCALE, e: selected.eccentricity!, i: selected.inclination_deg!,
        om: selected.long_asc_node_deg ?? 0, w: selected.arg_perihelion_deg ?? 0, ma: aMa,
      });
      const arcPts = transferArcPoints(
        { x: ePos.x, y: ePos.z, z: ePos.y },
        { x: aPos.x, y: aPos.z, z: aPos.y },
      );
      const sp = getSpacecraftPosition(arcPts, mission.progress ?? 0);
      controls.current.target.set(sp.x, sp.y, sp.z);
      controls.current.update();
      return;
    }

    // null = track selected asteroid
    if (!override && selected) {
      const pos = asteroidPosition(selected, dayOffset);
      if (pos) {
        controls.current.target.copy(pos);
        controls.current.update();
      }
    }
  });
  return null;
}

function CameraFocus({ target, selectedId, controls, focusOverrideRef }: {
  target: THREE.Vector3 | null;
  selectedId: number | null;
  controls: React.RefObject<OrbitControlsImpl | null>;
  focusOverrideRef: React.MutableRefObject<FocusOverride>;
}) {
  const { camera } = useThree();
  const lastId = useRef<number | null>(null);

  // Jump camera on new asteroid selection
  useEffect(() => {
    if (!target || !controls.current || selectedId === lastId.current) return;
    focusOverrideRef.current = null;
    lastId.current = selectedId;
    const ctrl = controls.current;
    const dist = Math.max(0.005, target.length() * 0.05);
    const offset = new THREE.Vector3(0, dist * 0.6, dist).normalize().multiplyScalar(dist);
    camera.position.copy(target.clone().add(offset));
    ctrl.target.copy(target);
    ctrl.update();
  }, [selectedId, camera, controls, focusOverrideRef]); // eslint-disable-line react-hooks/exhaustive-deps

  return null;
}

function Scene({ asteroids, selected, colorBy, dayOffset, speed, onDayOffsetChange, onSelectAsteroid }: Props) {
  const controlsRef = useRef<OrbitControlsImpl>(null);
  const focusOverrideRef = useRef<FocusOverride>(null);

  const selectedPos = useMemo(() => {
    if (!selected) return null;
    return asteroidPosition(selected, dayOffset);
  }, [selected, dayOffset]);

  const handleAsteroidClick = useCallback((index: number) => {
    if (index >= 0 && index < asteroids.length && onSelectAsteroid) {
      onSelectAsteroid(asteroids[index]);
    }
  }, [asteroids, onSelectAsteroid]);

  const handlePlanetSelect = useCallback((name: string, position: THREE.Vector3) => {
    if (!controlsRef.current) return;
    focusOverrideRef.current = name; // track this planet
    const ctrl = controlsRef.current;
    const cam = ctrl.object as THREE.PerspectiveCamera;
    const dist = Math.max(0.005, position.length() * 0.05);
    const offset = new THREE.Vector3(0, dist * 0.5, dist);
    ctrl.target.copy(position);
    cam.position.copy(position.clone().add(offset));
    ctrl.update();
  }, []);

  const handleSunClick = useCallback(() => {
    if (!controlsRef.current) return;
    controlsRef.current.target.set(0, 0, 0);
    controlsRef.current.update();
  }, []);

  return (
    <>
      <ambientLight intensity={0.08} />

      <Starfield />
      <OrbitZones />

      <TimeAdvancer speed={speed} dayOffset={dayOffset} onChange={onDayOffsetChange} />

      <group onClick={handleSunClick}>
        <SunGlow />
        <Html position={[0, 0.05, 0]} center>
          <div
            onClick={handleSunClick}
            style={{
              color: '#ffeeaa',
              fontSize: '10px',
              fontWeight: 600,
              textShadow: '0 0 4px rgba(0,0,0,0.9)',
              cursor: 'pointer',
            }}>
            Sun
          </div>
        </Html>
      </group>

      <Planets dayOffset={dayOffset} onSelectPlanet={handlePlanetSelect} />
      <AsteroidCloud
        asteroids={asteroids}
        colorBy={colorBy}
        dayOffset={dayOffset}
        onClickIndex={handleAsteroidClick}
      />

      {selected && selectedPos && (
        <Html position={[selectedPos.x, selectedPos.y + 0.005, selectedPos.z]} center style={{ pointerEvents: 'none' }}>
          <div style={{
            color: '#4fc3f7',
            fontSize: '11px',
            fontWeight: 700,
            textShadow: '0 0 4px rgba(0,0,0,0.9)',
            whiteSpace: 'nowrap',
          }}>
            {selected.name}
          </div>
        </Html>
      )}
      {selected && <OrbitLine asteroid={selected} />}
      {selected && <TransferArc asteroid={selected} dayOffset={dayOffset} onClickLabel={(pos) => {
        if (!controlsRef.current) return;
        focusOverrideRef.current = 'spacecraft';
        const ctrl = controlsRef.current;
        const cam = ctrl.object as THREE.PerspectiveCamera;
        const dist = Math.max(0.005, pos.length() * 0.05);
        const offset = new THREE.Vector3(0, dist * 0.5, dist);
        ctrl.target.copy(pos);
        cam.position.copy(pos.clone().add(offset));
        ctrl.update();
      }} />}
      <CameraFocus target={selectedPos} selectedId={selected?.spkid ?? null} controls={controlsRef} focusOverrideRef={focusOverrideRef} />
      <FocusTracker focusOverrideRef={focusOverrideRef} controls={controlsRef} dayOffset={dayOffset} selected={selected} />

      <OrbitControls
        ref={controlsRef}
        enablePan
        enableZoom
        enableRotate
        minDistance={0.001}
        maxDistance={200}
        makeDefault
      />
    </>
  );
}

export function SolarSystem(props: Props) {
  return (
    <Canvas
      camera={{ position: [0, 6, 10], fov: 55, near: 0.001, far: 500 }}
      style={{ background: '#020208' }}
    >
      <Scene {...props} />
    </Canvas>
  );
}
