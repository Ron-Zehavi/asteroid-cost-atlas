import { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

interface Props {
  /** Function returning the world-space position to follow each frame. */
  getPosition: () => THREE.Vector3 | null;
  /** Inner radius of the ring in world units (AU). */
  radius: number;
  /** Ring color. */
  color: string;
  /** Ring thickness as a fraction of radius. */
  thicknessRatio?: number;
}

/** A thin billboarded ring that follows a target each frame. */
export function FocusRing({ getPosition, radius, color, thicknessRatio = 0.04 }: Props) {
  const meshRef = useRef<THREE.Mesh>(null);
  const inner = radius;
  const outer = radius * (1 + thicknessRatio);

  useFrame(({ camera }) => {
    const mesh = meshRef.current;
    if (!mesh) return;
    const pos = getPosition();
    if (!pos) {
      mesh.visible = false;
      return;
    }
    mesh.visible = true;
    mesh.position.copy(pos);
    mesh.quaternion.copy(camera.quaternion);
  });

  return (
    <mesh ref={meshRef}>
      <ringGeometry args={[inner, outer, 64]} />
      <meshBasicMaterial
        color={color}
        side={THREE.DoubleSide}
        transparent
        opacity={0.9}
        depthWrite={false}
      />
    </mesh>
  );
}
