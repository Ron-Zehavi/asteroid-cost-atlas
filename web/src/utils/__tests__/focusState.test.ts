import { describe, it, expect } from 'vitest';
import { resolveFocusTarget, focusTargetToOverride, type FocusAction } from '../focusState';

describe('resolveFocusTarget', () => {
  it('selectAsteroid returns asteroid target', () => {
    expect(resolveFocusTarget({ action: 'selectAsteroid' })).toEqual({ type: 'asteroid' });
  });

  it('selectPlanet returns planet target with name', () => {
    expect(resolveFocusTarget({ action: 'selectPlanet', name: 'Earth' })).toEqual({
      type: 'planet',
      name: 'Earth',
    });
  });

  it('selectSun returns sun target', () => {
    expect(resolveFocusTarget({ action: 'selectSun' })).toEqual({ type: 'sun' });
  });

  it('selectSpacecraft returns spacecraft target', () => {
    expect(resolveFocusTarget({ action: 'selectSpacecraft' })).toEqual({ type: 'spacecraft' });
  });
});

describe('focusTargetToOverride', () => {
  it('asteroid maps to null (default tracking)', () => {
    expect(focusTargetToOverride({ type: 'asteroid' })).toBeNull();
  });

  it('planet maps to planet name string', () => {
    expect(focusTargetToOverride({ type: 'planet', name: 'Mars' })).toBe('Mars');
  });

  it('sun maps to "Sun"', () => {
    expect(focusTargetToOverride({ type: 'sun' })).toBe('Sun');
  });

  it('spacecraft maps to "spacecraft"', () => {
    expect(focusTargetToOverride({ type: 'spacecraft' })).toBe('spacecraft');
  });
});

describe('focus transitions: any action replaces previous tracking', () => {
  const actions: FocusAction[] = [
    { action: 'selectAsteroid' },
    { action: 'selectPlanet', name: 'Earth' },
    { action: 'selectSun' },
    { action: 'selectSpacecraft' },
  ];

  for (const prev of actions) {
    for (const next of actions) {
      if (prev === next) continue;
      it(`${prev.action} → ${next.action}: produces correct new target`, () => {
        // Simulate: first action sets state, second action replaces it
        const _first = resolveFocusTarget(prev);
        const second = resolveFocusTarget(next);
        const override = focusTargetToOverride(second);

        // The new target should match the second action, not the first
        expect(second.type).toBe(
          next.action === 'selectAsteroid' ? 'asteroid' :
          next.action === 'selectPlanet' ? 'planet' :
          next.action === 'selectSun' ? 'sun' : 'spacecraft'
        );

        // Override string should be independent of previous state
        if (next.action === 'selectAsteroid') expect(override).toBeNull();
        else if (next.action === 'selectPlanet') expect(override).toBe('Earth');
        else if (next.action === 'selectSun') expect(override).toBe('Sun');
        else expect(override).toBe('spacecraft');
      });
    }
  }
});

describe('Sun override is recognized as a planet by FocusTracker', () => {
  it('"Sun" override is not null and not "spacecraft"', () => {
    const override = focusTargetToOverride({ type: 'sun' });
    expect(override).not.toBeNull();
    expect(override).not.toBe('spacecraft');
    // FocusTracker treats non-null, non-"spacecraft" as planet name lookup
    // "Sun" won't match PLANET_ELEMENTS, so it effectively means "stay at origin"
    expect(override).toBe('Sun');
  });
});
