/**
 * Focus tracking state machine for the solar system camera.
 *
 * Behaviors (approved spec):
 *  1. Click asteroid  → stop any tracking, follow asteroid
 *  2. Click planet    → stop any tracking, follow planet
 *  3. Click Sun       → stop any tracking, center on Sun
 *  4. Click spacecraft label → stop any tracking, follow spacecraft
 *
 * Invariants:
 *  A. Camera never snaps back to a previously tracked object
 *  B. User can always zoom/rotate freely while tracking
 *  C. No visible vibration/jitter on any tracked object
 */

export type FocusTarget =
  | { type: 'asteroid' }
  | { type: 'planet'; name: string }
  | { type: 'sun' }
  | { type: 'spacecraft' };

export type FocusAction =
  | { action: 'selectAsteroid' }
  | { action: 'selectPlanet'; name: string }
  | { action: 'selectSun' }
  | { action: 'selectSpacecraft' };

/**
 * Given any focus action, returns the new focus target.
 * Any previous tracking is implicitly stopped by replacing the target.
 */
export function resolveFocusTarget(fa: FocusAction): FocusTarget {
  switch (fa.action) {
    case 'selectAsteroid':
      return { type: 'asteroid' };
    case 'selectPlanet':
      return { type: 'planet', name: fa.name };
    case 'selectSun':
      return { type: 'sun' };
    case 'selectSpacecraft':
      return { type: 'spacecraft' };
  }
}

/**
 * Convert a FocusTarget to the string value stored in focusOverrideRef.
 *   null       = track selected asteroid
 *   'Sun'      = track sun (static)
 *   'spacecraft' = track spacecraft
 *   other string = planet name
 */
export function focusTargetToOverride(target: FocusTarget): string | null {
  switch (target.type) {
    case 'asteroid':
      return null;
    case 'planet':
      return target.name;
    case 'sun':
      return 'Sun';
    case 'spacecraft':
      return 'spacecraft';
  }
}
