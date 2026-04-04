import { Html } from '@react-three/drei';
import * as THREE from 'three';

/**
 * Subtle orbital region bands in the ecliptic plane.
 * Helps orientation without overpowering asteroid visuals.
 */

interface Zone {
  name: string;
  innerAU: number;
  outerAU: number;
  color: string;
  opacity: number;
  labelAU: number;
}

const ZONES: Zone[] = [
  { name: 'NEO Region', innerAU: 0.98, outerAU: 1.3, color: '#44aa44', opacity: 0.04, labelAU: 1.14 },
  { name: 'Main Belt', innerAU: 2.1, outerAU: 3.3, color: '#6688aa', opacity: 0.035, labelAU: 2.7 },
  { name: 'Jupiter Trojans', innerAU: 5.0, outerAU: 5.4, color: '#aa8844', opacity: 0.025, labelAU: 5.2 },
];

export function OrbitZones() {
  return (
    <group>
      {ZONES.map((z) => (
        <group key={z.name}>
          <mesh rotation={[-Math.PI / 2, 0, 0]}>
            <ringGeometry args={[z.innerAU, z.outerAU, 128]} />
            <meshBasicMaterial
              color={z.color}
              transparent
              opacity={z.opacity}
              side={THREE.DoubleSide}
              depthWrite={false}
            />
          </mesh>
          <Html
            position={[0, 0.02, -z.labelAU]}
            center
            style={{ pointerEvents: 'none' }}
          >
            <div style={{
              color: z.color,
              fontSize: '9px',
              opacity: 0.4,
              whiteSpace: 'nowrap',
              textShadow: '0 0 4px rgba(0,0,0,0.9)',
              userSelect: 'none',
              letterSpacing: '1px',
              textTransform: 'uppercase',
            }}>
              {z.name}
            </div>
          </Html>
        </group>
      ))}
    </group>
  );
}
