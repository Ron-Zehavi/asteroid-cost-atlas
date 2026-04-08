import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
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
  getCurrentMissionPhase,
  getMissionPhase,
  getSpacecraftPosition,
  transferArcPoints,
} from '../../utils/transfer';

import { OrbitZones } from './OrbitZones';
import { TransferArc } from './TransferArc';
import { FocusRing } from './FocusRing';
import type { Asteroid } from '../../types/asteroid';
import { keplerToCartesian, propagateMeanAnomaly } from '../../utils/kepler';
import { DISTANCE_SCALE } from '../../utils/sceneConstants';
import { focusTargetToOverride } from '../../utils/focusState';

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

/** Module-level so it survives React StrictMode's double-mount in dev. */
const focusOverrideShared: { current: FocusOverride } = { current: null };
function setOverride(v: FocusOverride) {
  focusOverrideShared.current = v;
}

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

    // Sun = stay at origin (static, no tracking needed)
    if (override === 'Sun') return;

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

    // null = no continuous tracking. CameraFocus already does the one-time
    // jump when a new asteroid is selected; after that the user is in control.
  });
  return null;
}

const lastSelectedId = { current: null as number | null };

function CameraFocus({ target, selectedId, controls }: {
  target: THREE.Vector3 | null;
  selectedId: number | null;
  controls: React.RefObject<OrbitControlsImpl | null>;
}) {
  const { camera } = useThree();
  const lastId = lastSelectedId;

  // Jump camera on new asteroid selection. Only fires when selectedId actually
  // changes — never overwrites 'static' on subsequent re-renders.
  useEffect(() => {
    if (selectedId == null || selectedId === lastId.current) return;
    if (!target || !controls.current) return;
    lastId.current = selectedId;
    setOverride(null);
    const ctrl = controls.current;
    const dist = Math.max(0.005, target.length() * 0.05);
    const offset = new THREE.Vector3(0, dist * 0.6, dist).normalize().multiplyScalar(dist);
    camera.position.copy(target.clone().add(offset));
    ctrl.target.copy(target);
    ctrl.update();
  }, [selectedId]); // eslint-disable-line react-hooks/exhaustive-deps

  return null;
}

/** Runs once on mount: positions the camera so Mars's orbit fits the smaller viewport dimension. */
function InitialCameraFit() {
  const { camera, size, controls } = useThree() as unknown as {
    camera: THREE.PerspectiveCamera;
    size: { width: number; height: number };
    controls: OrbitControlsImpl | null;
  };
  const fitted = useRef(false);

  useEffect(() => {
    if (fitted.current) return;
    if (!size.width || !size.height) return;
    const mars = PLANET_ELEMENTS.find((p) => p.name === 'Mars');
    if (!mars) return;

    // Mars orbit radius in world units — keep DISTANCE_SCALE symbolic so future
    // changes to scale automatically rescale this initial framing.
    const radius = mars.a * DISTANCE_SCALE;

    const vFov = (camera.fov * Math.PI) / 180;
    const aspect = size.width / size.height;
    const hFov = 2 * Math.atan(Math.tan(vFov / 2) * aspect);
    // Smaller viewport dimension → tighter FOV constraint
    const fov = Math.min(vFov, hFov);
    const dist = (radius / Math.tan(fov / 2)) * 1.05; // 5% margin

    camera.position.set(0, dist * 0.4, dist);
    camera.lookAt(0, 0, 0);
    camera.updateProjectionMatrix();

    if (controls) {
      controls.target.set(0, 0, 0);
      controls.update();
    }
    fitted.current = true;
  }, [camera, size, controls]);

  return null;
}

/** Listens on the canvas DOM element for any user input (pointerdown/wheel) and
 *  flips the focus override to 'static' so FocusTracker stops snapping the camera. */
/** Tracks pointer movement between down/up so we can distinguish a true click
 *  from a drag. Exposed via module-level flag for the asteroid click handler. */
const dragState = { downX: 0, downY: 0, isDrag: false };
const DRAG_THRESHOLD_PX = 5;

function ControlsInteractionGuard() {
  const { gl } = useThree();
  useEffect(() => {
    const canvas = gl.domElement;
    const onPointerDown = (e: PointerEvent) => {
      if (e.target !== canvas) return;
      dragState.downX = e.clientX;
      dragState.downY = e.clientY;
      dragState.isDrag = false;
    };
    const onPointerMove = (e: PointerEvent) => {
      if (e.target !== canvas) return;
      const dx = e.clientX - dragState.downX;
      const dy = e.clientY - dragState.downY;
      if (dx * dx + dy * dy > DRAG_THRESHOLD_PX * DRAG_THRESHOLD_PX) {
        if (!dragState.isDrag) {
          dragState.isDrag = true;
          setOverride('static');
        }
      }
    };
    const onWheel = (e: WheelEvent) => {
      if (e.target === canvas) setOverride('static');
    };
    window.addEventListener('pointerdown', onPointerDown, true);
    window.addEventListener('pointermove', onPointerMove, true);
    window.addEventListener('wheel', onWheel, { capture: true, passive: true });
    return () => {
      window.removeEventListener('pointerdown', onPointerDown, true);
      window.removeEventListener('pointermove', onPointerMove, true);
      window.removeEventListener('wheel', onWheel, true);
    };
  }, [gl]);
  return null;
}

function Scene({ asteroids, selected, colorBy, dayOffset, speed, onDayOffsetChange, onSelectAsteroid }: Props) {
  const controlsRef = useRef<OrbitControlsImpl>(null);
  const focusOverrideRef = focusOverrideShared;
  const [focusedPlanet, setFocusedPlanet] = useState<string | null>(null);

  const selectedPos = useMemo(() => {
    if (!selected) return null;
    return asteroidPosition(selected, dayOffset);
  }, [selected, dayOffset]);

  // Current mission phase for the selected asteroid → drives Earth and target tints.
  const missionPhase = useMemo(() => {
    if (!selected) return null;
    return getCurrentMissionPhase(selected, dayOffset);
  }, [selected, dayOffset]);

  const earthTint = missionPhase?.phase === 'window_open' ? '#44ff44' : null;
  const highlightedSpkid = missionPhase?.phase === 'arrived' ? selected?.spkid ?? null : null;
  const highlightTint = missionPhase?.phase === 'arrived' ? '#44ff44' : null;

  const handleAsteroidClick = useCallback((index: number) => {
    // Suppress click if it was actually a drag — otherwise dragging the camera
    // over the cloud re-selects an asteroid and re-triggers CameraFocus jump.
    if (dragState.isDrag) return;
    if (index >= 0 && index < asteroids.length && onSelectAsteroid) {
      onSelectAsteroid(asteroids[index]);
    }
  }, [asteroids, onSelectAsteroid]);


  const handlePlanetSelect = useCallback((name: string, position: THREE.Vector3) => {
    if (!controlsRef.current) return;
    focusOverrideRef.current = focusTargetToOverride({ type: 'planet', name });
    setFocusedPlanet(name);
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
    focusOverrideRef.current = focusTargetToOverride({ type: 'sun' });
    setFocusedPlanet(null);
    controlsRef.current.target.set(0, 0, 0);
    controlsRef.current.update();
  }, []);

  const focusedPlanetDef = useMemo(
    () => (focusedPlanet ? PLANET_ELEMENTS.find((p) => p.name === focusedPlanet) ?? null : null),
    [focusedPlanet],
  );

  const getFocusedPlanetPos = useCallback((): THREE.Vector3 | null => {
    if (!focusedPlanetDef) return null;
    const p = focusedPlanetDef;
    const ma = propagateMeanAnomaly(p.ma0, p.a, dayOffset);
    const pos = keplerToCartesian({
      a: p.a * DISTANCE_SCALE, e: p.e, i: p.i,
      om: p.om, w: p.w, ma,
    });
    return new THREE.Vector3(pos.x, pos.z, pos.y);
  }, [focusedPlanetDef, dayOffset]);

  const getSelectedAsteroidPos = useCallback((): THREE.Vector3 | null => {
    if (!selected) return null;
    return asteroidPosition(selected, dayOffset);
  }, [selected, dayOffset]);

  return (
    <>
      <ambientLight intensity={0.08} />

      <Starfield />
      <OrbitZones />

      <TimeAdvancer speed={speed} dayOffset={dayOffset} onChange={onDayOffsetChange} />

      <group onClick={handleSunClick}>
        <SunGlow />
        <Html position={[0, 0.025, 0]} center>
          <div
            onClick={(e) => { e.stopPropagation(); handleSunClick(); }}
            style={{
              color: '#ffeeaa',
              fontSize: '16px',
              fontWeight: 600,
              textShadow: '0 0 4px rgba(0,0,0,0.9)',
              cursor: 'pointer',
            }}>
            Sun
          </div>
        </Html>
      </group>

      <Planets dayOffset={dayOffset} onSelectPlanet={handlePlanetSelect} earthTint={earthTint} />
      <AsteroidCloud
        asteroids={asteroids}
        colorBy={colorBy}
        dayOffset={dayOffset}
        onClickIndex={handleAsteroidClick}
        highlightedSpkid={highlightedSpkid}
        highlightTint={highlightTint}
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
        focusOverrideRef.current = 'static';
        const ctrl = controlsRef.current;
        const cam = ctrl.object as THREE.PerspectiveCamera;
        const dist = Math.max(0.005, pos.length() * 0.05);
        const offset = new THREE.Vector3(0, dist * 0.5, dist);
        ctrl.target.copy(pos);
        cam.position.copy(pos.clone().add(offset));
        ctrl.update();
      }} />}
      <CameraFocus target={selectedPos} selectedId={selected?.spkid ?? null} controls={controlsRef} />
      <FocusTracker focusOverrideRef={focusOverrideRef} controls={controlsRef} dayOffset={dayOffset} selected={selected} />
      <InitialCameraFit />

      {focusedPlanetDef && (
        <FocusRing
          getPosition={getFocusedPlanetPos}
          radius={focusedPlanetDef.size * 2.5}
          color={focusedPlanetDef.color}
        />
      )}
      {selected && (
        <FocusRing
          getPosition={getSelectedAsteroidPos}
          radius={0.002}
          color="#ffffff"
        />
      )}

      <OrbitControls
        ref={controlsRef}
        enablePan
        enableZoom
        enableRotate
        minDistance={0.001}
        maxDistance={200}
        makeDefault
      />
      <ControlsInteractionGuard />
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
