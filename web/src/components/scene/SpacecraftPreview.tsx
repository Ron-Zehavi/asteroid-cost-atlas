import { useRef, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, useGLTF } from '@react-three/drei';
import * as THREE from 'three';
import { Planets } from './Planets';
import { SunGlow } from './SunGlow';
import { OrbitZones } from './OrbitZones';
import { DISTANCE_SCALE, SPACECRAFT_SCALE_PREVIEW } from '../../utils/sceneConstants';

/** Reusable cargo spaceship loaded from GLB */
export function CargoSpaceship({ scale = 0.005 }: { scale?: number }) {
  const { scene } = useGLTF('/cargo_spaceship.glb');
  const cloned = useMemo(() => scene.clone(), [scene]);
  return <primitive object={cloned} scale={scale} />;
}

/** Spacecraft flying a Hohmann-like arc from Earth (~1 AU) to a target (~1.5 AU) */
function TransferArcDemo() {
  const groupRef = useRef<THREE.Group>(null);

  const curve = useMemo(() => {
    const earthR = 1.0 * DISTANCE_SCALE;
    const marsR = 1.5 * DISTANCE_SCALE;
    return new THREE.EllipseCurve(0, 0, (earthR + marsR) / 2, earthR, 0, Math.PI, false, 0);
  }, []);

  const arcLine = useMemo(() => {
    const pts = curve.getPoints(100).map((p) => new THREE.Vector3(p.x, 0, p.y));
    const geo = new THREE.BufferGeometry().setFromPoints(pts);
    const mat = new THREE.LineDashedMaterial({
      color: '#ffaa33', dashSize: 0.005, gapSize: 0.003,
      opacity: 0.7, transparent: true,
    });
    const line = new THREE.Line(geo, mat);
    line.computeLineDistances();
    return line;
  }, [curve]);

  useFrame(({ clock }) => {
    if (!groupRef.current) return;
    const t = (clock.getElapsedTime() * 0.04) % 1;
    const p = curve.getPoint(t);
    groupRef.current.position.set(p.x, 0, p.y);

    const behind = curve.getPoint(Math.max(t - 0.01, 0));
    groupRef.current.lookAt(behind.x, 0, behind.y);
  });

  return (
    <group>
      <primitive object={arcLine} />
      <group ref={groupRef}>
        <CargoSpaceship scale={SPACECRAFT_SCALE_PREVIEW} />
      </group>
    </group>
  );
}

export function SpacecraftPreview() {
  return (
    <div style={{ width: '100%', height: '100%', background: '#020208' }}>
      <Canvas
        camera={{ position: [0, 0.3, 0.5], fov: 55, near: 0.0001, far: 500 }}
        style={{ background: '#020208' }}
      >
        <ambientLight intensity={0.08} />
        <OrbitZones />
        <SunGlow />
        <Planets dayOffset={0} />
        <TransferArcDemo />
        <OrbitControls
          enablePan
          enableZoom
          enableRotate
          minDistance={0.001}
          maxDistance={200}
        />
      </Canvas>
    </div>
  );
}
