import { useMemo } from 'react';
import * as THREE from 'three';
import { Billboard, useTexture } from '@react-three/drei';

/**
 * Asterank-style glowing sun: solid core sphere + additive-blended glow sprite.
 */
export function SunGlow() {
  const sunTex = useTexture('/textures/2k_sun.jpg');
  const glowTexture = useMemo(() => {
    const size = 256;
    const canvas = document.createElement('canvas');
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext('2d')!;
    const gradient = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
    gradient.addColorStop(0, 'rgba(255, 240, 180, 1.0)');
    gradient.addColorStop(0.15, 'rgba(255, 220, 100, 0.8)');
    gradient.addColorStop(0.35, 'rgba(255, 180, 50, 0.3)');
    gradient.addColorStop(0.6, 'rgba(255, 120, 20, 0.08)');
    gradient.addColorStop(1, 'rgba(255, 80, 0, 0)');
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, size, size);
    const tex = new THREE.CanvasTexture(canvas);
    return tex;
  }, []);

  return (
    <group>
      {/* Solid core — true radius: 0.00465 AU */}
      <mesh>
        <sphereGeometry args={[0.00465, 64, 64]} />
        <meshBasicMaterial map={sunTex} toneMapped={false} />
      </mesh>

      {/* Inner glow sprite */}
      <Billboard>
        <mesh>
          <planeGeometry args={[0.06, 0.06]} />
          <meshBasicMaterial
            map={glowTexture}
            transparent
            blending={THREE.AdditiveBlending}
            depthWrite={false}
            depthTest={false}
            opacity={1.0}
          />
        </mesh>
      </Billboard>

      {/* Outer glow (larger, more transparent) */}
      <Billboard>
        <mesh>
          <planeGeometry args={[0.15, 0.15]} />
          <meshBasicMaterial
            map={glowTexture}
            transparent
            blending={THREE.AdditiveBlending}
            depthWrite={false}
            depthTest={false}
            opacity={0.3}
          />
        </mesh>
      </Billboard>

      {/* Light source */}
      <pointLight color="#ffeecc" intensity={3} distance={200} decay={1} />
    </group>
  );
}
