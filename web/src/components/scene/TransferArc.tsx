import { useMemo, useRef, useLayoutEffect } from 'react';
import * as THREE from 'three';
import { Html } from '@react-three/drei';
import { CargoSpaceship } from './SpacecraftPreview';
import type { Asteroid } from '../../types/asteroid';
import { keplerToCartesian, propagateMeanAnomaly } from '../../utils/kepler';
import { DISTANCE_SCALE, SPACECRAFT_SCALE_TRANSIT } from '../../utils/sceneConstants';
import {
  computeHohmannTransfer,
  dayOffsetToDate,
  estimateLaunchWindows,
  getMissionPhase,
  getSpacecraftPosition,
  transferArcPoints,
} from '../../utils/transfer';

const EARTH = { a: 1.0, e: 0.017, i: 0.0, om: -11.26, w: 102.95, ma0: 357.52 };

function earthPosAt(dayOffset: number) {
  const ma = propagateMeanAnomaly(EARTH.ma0, EARTH.a, dayOffset);
  const ecl = keplerToCartesian({ ...EARTH, a: EARTH.a * DISTANCE_SCALE, ma });
  return { x: ecl.x, y: ecl.z, z: ecl.y };
}

function asteroidPosAt(a: Asteroid, dayOffset: number) {
  const epochDays = a.epoch_mjd ? a.epoch_mjd - 51544.5 : 0;
  const ma = propagateMeanAnomaly(a.mean_anomaly_deg ?? 0, a.a_au!, dayOffset - epochDays);
  const ecl = keplerToCartesian({
    a: a.a_au! * DISTANCE_SCALE, e: a.eccentricity!, i: a.inclination_deg!,
    om: a.long_asc_node_deg ?? 0, w: a.arg_perihelion_deg ?? 0, ma,
  });
  return { x: ecl.x, y: ecl.z, z: ecl.y };
}

function OrientedSpacecraft({ position, lookAt }: { position: THREE.Vector3; lookAt: THREE.Vector3 }) {
  const groupRef = useRef<THREE.Group>(null);
  useLayoutEffect(() => {
    if (groupRef.current) {
      groupRef.current.lookAt(lookAt);
    }
  }, [lookAt]);
  return (
    <group ref={groupRef} position={position}>
      <CargoSpaceship scale={SPACECRAFT_SCALE_TRANSIT} />
    </group>
  );
}

interface Props {
  asteroid: Asteroid;
  dayOffset: number;
  onClickLabel?: (position: THREE.Vector3) => void;
}

export function TransferArc({ asteroid, dayOffset, onClickLabel }: Props) {
  const scene = useMemo(() => {
    const a = asteroid;
    if (!a.a_au || a.eccentricity == null || a.inclination_deg == null) return null;
    if (!a.delta_v_km_s || a.delta_v_km_s <= 0) return null;

    const transfer = computeHohmannTransfer(a.a_au, a.inclination_deg);
    const windows = estimateLaunchWindows(
      transfer.synodic_days, transfer.transfer_days, dayOffset,
    );
    const mission = getMissionPhase(windows, dayOffset);

    // Asteroid position (stable anchor for labels)
    const astNow = asteroidPosAt(a, dayOffset);
    const astLabel = new THREE.Vector3(astNow.x, astNow.y + 0.15, astNow.z);

    // --- WAITING: show countdown, no arc ---
    if (mission.phase === 'waiting') {
      return {
        phase: 'waiting' as const,
        labelPos: astLabel,
        daysUntil: mission.daysUntil ?? 0,
        nextDate: mission.window.date,
        dv: a.delta_v_km_s,
        transferDays: Math.round(transfer.transfer_days),
      };
    }

    // --- WINDOW OPEN: trajectory to future asteroid position ---
    if (mission.phase === 'window_open') {
      const earthNow = earthPosAt(dayOffset);
      // Where will the asteroid be when we arrive?
      const arrivalDay = dayOffset + transfer.transfer_days;
      const arrivalPos = asteroidPosAt(a, arrivalDay);

      const arcPts = transferArcPoints(earthNow, arrivalPos);
      const vectors = arcPts.map((p) => new THREE.Vector3(p.x, p.y, p.z));
      const geometry = new THREE.BufferGeometry().setFromPoints(vectors);
      const material = new THREE.LineDashedMaterial({
        color: '#ffaa33', dashSize: 0.05, gapSize: 0.03,
        opacity: 0.8, transparent: true,
      });
      const line = new THREE.Line(geometry, material);
      line.computeLineDistances();

      return {
        phase: 'window_open' as const,
        line,
        labelPos: astLabel,
        daysRemaining: mission.daysUntil ?? 0,
        dv: a.delta_v_km_s,
        transferDays: Math.round(transfer.transfer_days),
        arrivalDate: dayOffsetToDate(Math.round(arrivalDay)),
      };
    }

    // --- IN TRANSIT: frozen arc + spacecraft dot ---
    if (mission.phase === 'in_transit') {
      const w = mission.window;
      // Departure = Earth position at window close (launch day)
      const departurePos = earthPosAt(w.windowEnd);
      // Arrival = asteroid position at arrival day
      const arrivalPos = asteroidPosAt(a, w.arrivalDay);

      const arcPts = transferArcPoints(departurePos, arrivalPos);
      const vectors = arcPts.map((p) => new THREE.Vector3(p.x, p.y, p.z));
      const geometry = new THREE.BufferGeometry().setFromPoints(vectors);
      const material = new THREE.LineBasicMaterial({
        color: '#ffaa33', opacity: 0.6, transparent: true,
      });
      const line = new THREE.Line(geometry, material);

      const progress = mission.progress ?? 0;
      const shipPos = getSpacecraftPosition(arcPts, progress);
      const behindPos = getSpacecraftPosition(arcPts, Math.max(progress - 0.02, 0));
      const daysLeft = w.arrivalDay - dayOffset;

      return {
        phase: 'in_transit' as const,
        line,
        shipPos: new THREE.Vector3(shipPos.x, shipPos.y, shipPos.z),
        shipLookAt: new THREE.Vector3(behindPos.x, behindPos.y, behindPos.z),
        labelPos: new THREE.Vector3(shipPos.x, shipPos.y + 0.001, shipPos.z),
        progress: Math.round(progress * 100),
        daysLeft,
        dv: a.delta_v_km_s,
        arrivalDate: dayOffsetToDate(w.arrivalDay),
      };
    }

    // --- ARRIVED: flash at asteroid ---
    if (mission.phase === 'arrived') {
      const astNow = asteroidPosAt(a, dayOffset);
      return {
        phase: 'arrived' as const,
        pos: new THREE.Vector3(astNow.x, astNow.y, astNow.z),
      };
    }

    return null;
  }, [asteroid, dayOffset]);

  if (!scene) return null;

  // --- RENDER: WAITING ---
  if (scene.phase === 'waiting') {
    return (
      <Html position={scene.labelPos} center>
        <div style={{ ...labelStyle('#555566'), cursor: 'pointer' }} onClick={() => onClickLabel?.(scene.labelPos)}>
          <div style={{ fontSize: '10px', color: '#888899' }}>
            Next launch window in <b>{Math.round(scene.daysUntil)}</b> days
          </div>
          <div style={{ fontSize: '9px', color: '#666677' }}>
            {scene.nextDate} | Δv {scene.dv.toFixed(1)} km/s | {scene.transferDays}d travel
          </div>
        </div>
      </Html>
    );
  }

  // --- RENDER: WINDOW OPEN ---
  if (scene.phase === 'window_open') {
    return (
      <group>
        <primitive object={scene.line} />
        <Html position={scene.labelPos} center>
          <div style={{ ...labelStyle('#ffaa33'), cursor: 'pointer' }} onClick={() => onClickLabel?.(scene.labelPos)}>
            <div style={{ fontWeight: 700, color: '#ffcc44', fontSize: '12px' }}>
              🚀 Launch Window Open
            </div>
            <div>{Math.round(scene.daysRemaining)} days remaining</div>
            <div>Δv: {scene.dv.toFixed(1)} km/s</div>
            <div>Travel: {scene.transferDays} days</div>
            <div>Arrival: {scene.arrivalDate}</div>
          </div>
        </Html>
      </group>
    );
  }

  // --- RENDER: IN TRANSIT ---
  if (scene.phase === 'in_transit') {
    return (
      <group>
        <primitive object={scene.line} />
        <OrientedSpacecraft position={scene.shipPos} lookAt={scene.shipLookAt} />
        {/* Glow around spacecraft */}
        <mesh position={scene.shipPos}>
          <sphereGeometry args={[0.00003, 8, 8]} />
          <meshBasicMaterial
            color="#ffaa33"
            transparent
            opacity={0.5}
            blending={THREE.AdditiveBlending}
          />
        </mesh>
        <Html position={scene.labelPos} center>
          <div style={{ ...labelStyle('#ffaa33'), cursor: 'pointer' }} onClick={() => onClickLabel?.(scene.shipPos)}>
            <div style={{ fontWeight: 700, color: '#ffcc44' }}>
              🛰️ In Transit — {Math.round(scene.progress)}%
            </div>
            <div>{Math.round(scene.daysLeft)} days remaining</div>
            <div>Arrival: {scene.arrivalDate}</div>
          </div>
        </Html>
      </group>
    );
  }

  // --- RENDER: ARRIVED ---
  if (scene.phase === 'arrived') {
    return (
      <group>
        <mesh position={scene.pos}>
          <sphereGeometry args={[0.04, 16, 16]} />
          <meshBasicMaterial
            color="#44ff44"
            transparent
            opacity={0.6}
            blending={THREE.AdditiveBlending}
          />
        </mesh>
        <Html position={[scene.pos.x, scene.pos.y + 0.08, scene.pos.z]} center>
          <div style={{ ...labelStyle('#44ff44'), cursor: 'pointer' }} onClick={() => onClickLabel?.(scene.pos)}>
            <div style={{ fontWeight: 700, color: '#66ff66' }}>
              ✅ Arrived
            </div>
          </div>
        </Html>
      </group>
    );
  }

  return null;
}

function labelStyle(borderColor: string): React.CSSProperties {
  return {
    background: 'rgba(10, 10, 20, 0.88)',
    border: `1px solid ${borderColor}`,
    borderRadius: '6px',
    padding: '5px 9px',
    color: '#ddddee',
    fontSize: '10px',
    whiteSpace: 'nowrap',
    textShadow: '0 0 3px rgba(0,0,0,0.9)',
    userSelect: 'none',
    lineHeight: '1.5',
  };
}
