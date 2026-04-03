import { useMemo } from 'react';
import * as THREE from 'three';

/**
 * Procedural milky way skybox.
 * Creates a large sphere with a canvas texture that has:
 * - Dense star field
 * - A bright galactic band tilted ~60 degrees (matching real ecliptic-to-galactic angle)
 */
export function MilkyWay() {
  const texture = useMemo(() => {
    const w = 2048;
    const h = 1024;
    const canvas = document.createElement('canvas');
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext('2d')!;

    // Black background
    ctx.fillStyle = '#000005';
    ctx.fillRect(0, 0, w, h);

    // Galactic band — a bright diffuse stripe tilted across the sphere
    // In equirectangular, the galactic plane is a sinusoidal curve
    const bandWidth = h * 0.18;
    for (let x = 0; x < w; x++) {
      // Galactic center offset: sinusoidal band tilted ~60 deg from equator
      const theta = (x / w) * Math.PI * 2;
      const centerY = h / 2 + Math.sin(theta + 1.0) * h * 0.28;

      for (let y = 0; y < h; y++) {
        const distFromBand = Math.abs(y - centerY);
        if (distFromBand < bandWidth) {
          const intensity = Math.pow(1 - distFromBand / bandWidth, 2.5);
          const r = Math.floor(20 + intensity * 35);
          const g = Math.floor(18 + intensity * 30);
          const b = Math.floor(25 + intensity * 40);
          const a = intensity * 0.6;
          ctx.fillStyle = `rgba(${r},${g},${b},${a})`;
          ctx.fillRect(x, y, 1, 1);
        }
      }

      // Denser stars near galactic center
      const galacticDensity = Math.exp(-Math.pow((x / w - 0.5) * 3, 2));
      for (let s = 0; s < 3 + galacticDensity * 8; s++) {
        const sy = centerY + (Math.random() - 0.5) * bandWidth * 2;
        if (sy >= 0 && sy < h) {
          const bright = 100 + Math.random() * 155;
          const size = Math.random() < 0.05 ? 2 : 1;
          ctx.fillStyle = `rgba(${bright},${bright},${bright + 20},${0.5 + Math.random() * 0.5})`;
          ctx.fillRect(x, sy, size, size);
        }
      }
    }

    // Scattered field stars everywhere
    for (let i = 0; i < 12000; i++) {
      const x = Math.random() * w;
      const y = Math.random() * h;
      const bright = 80 + Math.random() * 175;
      const size = Math.random() < 0.03 ? 2 : 1;
      // Slight color variation: some warm, some cool
      const temp = Math.random();
      const r = bright + (temp > 0.7 ? 30 : 0);
      const g = bright;
      const b = bright + (temp < 0.3 ? 30 : 0);
      ctx.fillStyle = `rgba(${Math.min(255, r)},${Math.min(255, g)},${Math.min(255, b)},${0.4 + Math.random() * 0.6})`;
      ctx.fillRect(x, y, size, size);
    }

    const tex = new THREE.CanvasTexture(canvas);
    tex.mapping = THREE.EquirectangularReflectionMapping;
    return tex;
  }, []);

  return (
    <mesh>
      <sphereGeometry args={[300, 64, 32]} />
      <meshBasicMaterial
        map={texture}
        side={THREE.BackSide}
        depthWrite={false}
      />
    </mesh>
  );
}
