import { useCallback, useEffect, useMemo, useRef } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib';
import * as THREE from 'three';
import { Planets } from './Planets';
import { AsteroidCloud } from './AsteroidCloud';
import { OrbitLine } from './OrbitLine';
import { SunGlow } from './SunGlow';
import { MilkyWay } from './MilkyWay';
import { OrbitZones } from './OrbitZones';
import { TransferArc } from './TransferArc';
import type { Asteroid } from '../../types/asteroid';
import { keplerToCartesian, propagateMeanAnomaly } from '../../utils/kepler';

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
    a: a.a_au, e: a.eccentricity, i: a.inclination_deg,
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

/** Tracks a selected object: jumps camera on first select, then only updates
 *  the orbit‑controls pivot so zoom / rotate keep working. */
function CameraFocus({ target, selectedId, controls }: {
  target: THREE.Vector3 | null;
  selectedId: number | null;      // spkid — changes when user picks a new asteroid
  controls: React.RefObject<OrbitControlsImpl | null>;
}) {
  const { camera } = useThree();
  const lastId = useRef<number | null>(null);

  useEffect(() => {
    if (!target || !controls.current) return;
    const ctrl = controls.current;
    const isNewSelection = selectedId !== lastId.current;

    if (isNewSelection) {
      // Jump camera once for the new selection
      const dist = Math.max(0.3, target.length() * 0.25);
      const offset = new THREE.Vector3(0, dist * 0.6, dist).normalize().multiplyScalar(dist);
      camera.position.copy(target.clone().add(offset));
      lastId.current = selectedId;
    }

    // Always keep the orbit pivot on the object so it stays centered
    // while the user zooms / rotates freely
    ctrl.target.copy(target);
    ctrl.update();
  }, [target, selectedId, camera, controls]);

  return null;
}

function Scene({ asteroids, selected, colorBy, dayOffset, speed, onDayOffsetChange, onSelectAsteroid }: Props) {
  const controlsRef = useRef<OrbitControlsImpl>(null);

  const selectedPos = useMemo(() => {
    if (!selected) return null;
    return asteroidPosition(selected, dayOffset);
  }, [selected, dayOffset]);

  const handleAsteroidClick = useCallback((index: number) => {
    if (index >= 0 && index < asteroids.length && onSelectAsteroid) {
      onSelectAsteroid(asteroids[index]);
    }
  }, [asteroids, onSelectAsteroid]);

  const handlePlanetSelect = useCallback((_name: string, position: THREE.Vector3) => {
    if (!controlsRef.current) return;
    const ctrl = controlsRef.current;
    const cam = ctrl.object as THREE.PerspectiveCamera;
    const dist = Math.max(0.3, position.length() * 0.15);
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
      <MilkyWay />
      <OrbitZones />

      <TimeAdvancer speed={speed} dayOffset={dayOffset} onChange={onDayOffsetChange} />

      <group onClick={handleSunClick}>
        <SunGlow />
      </group>

      <Planets dayOffset={dayOffset} onSelectPlanet={handlePlanetSelect} />
      <AsteroidCloud
        asteroids={asteroids}
        colorBy={colorBy}
        dayOffset={dayOffset}
        onClickIndex={handleAsteroidClick}
      />

      {selected && <OrbitLine asteroid={selected} />}
      {selected && <TransferArc asteroid={selected} dayOffset={dayOffset} />}
      <CameraFocus target={selectedPos} selectedId={selected?.spkid ?? null} controls={controlsRef} />

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
