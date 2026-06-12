import type { Asteroid } from '../../types/asteroid';

export type CompositionClass = 'C' | 'S' | 'M' | 'V' | 'U';

/** Subtle emissive tint per class — texture stays the dominant visual cue. */
export const CLASS_TINT: Record<CompositionClass, string> = {
  C: '#5577aa',
  S: '#aa9955',
  M: '#888899',
  V: '#aa5544',
  U: '#666666',
};

export const CLASS_TEXTURE_PATHS: Record<CompositionClass, string> = {
  C: '/textures/2k_ceres.jpg',
  S: '/textures/2k_eris.jpg',
  M: '/textures/2k_haumea.jpg',
  V: '/textures/2k_makemake.jpg',
  U: '/textures/2k_moon.jpg',
};

export const ALL_TEXTURE_PATHS = [
  CLASS_TEXTURE_PATHS.C,
  CLASS_TEXTURE_PATHS.S,
  CLASS_TEXTURE_PATHS.M,
  CLASS_TEXTURE_PATHS.V,
  CLASS_TEXTURE_PATHS.U,
];

export function classOf(a: Asteroid): CompositionClass {
  const c = a.composition_class;
  if (c === 'C' || c === 'S' || c === 'M' || c === 'V') return c;
  return 'U';
}
