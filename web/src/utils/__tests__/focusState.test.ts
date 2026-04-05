import { describe, it, expect } from 'vitest';
import { resolveFocusTarget, focusTargetToOverride, type FocusAction } from '../focusState';
import { PLANET_ELEMENTS } from '../../components/scene/Planets';

describe('resolveFocusTarget', () => {
  it('selectAsteroid returns asteroid target', () => {
    expect(resolveFocusTarget({ action: 'selectAsteroid' })).toEqual({ type: 'asteroid' });
  });

  it('selectPlanet returns planet target with name', () => {
    expect(resolveFocusTarget({ action: 'selectPlanet', name: 'Earth' })).toEqual({
      type: 'planet', name: 'Earth',
    });
  });

  it('selectSun returns sun target', () => {
    expect(resolveFocusTarget({ action: 'selectSun' })).toEqual({ type: 'sun' });
  });

  it('selectSpacecraft returns spacecraft target', () => {
    expect(resolveFocusTarget({ action: 'selectSpacecraft' })).toEqual({ type: 'spacecraft' });
  });
});

describe('focusTargetToOverride — produces values FocusTracker expects', () => {
  it('asteroid → null (FocusTracker asteroid branch: !override && selected)', () => {
    expect(focusTargetToOverride({ type: 'asteroid' })).toBeNull();
  });

  it('planet → planet name string (FocusTracker planet branch: override && override !== "spacecraft")', () => {
    const override = focusTargetToOverride({ type: 'planet', name: 'Mars' });
    expect(override).toBe('Mars');
    expect(override).not.toBeNull();
    expect(override).not.toBe('spacecraft');
    expect(override).not.toBe('Sun');
  });

  it('sun → "Sun" (FocusTracker Sun early-return: override === "Sun")', () => {
    expect(focusTargetToOverride({ type: 'sun' })).toBe('Sun');
  });

  it('spacecraft → "spacecraft" (FocusTracker spacecraft branch: override === "spacecraft")', () => {
    expect(focusTargetToOverride({ type: 'spacecraft' })).toBe('spacecraft');
  });
});

describe('planet names match PLANET_ELEMENTS', () => {
  const planetNames = PLANET_ELEMENTS.map((p) => p.name);

  for (const name of planetNames) {
    it(`"${name}" is found in PLANET_ELEMENTS`, () => {
      const override = focusTargetToOverride({ type: 'planet', name });
      expect(override).toBe(name);
      expect(PLANET_ELEMENTS.find((p) => p.name === override)).toBeDefined();
    });
  }

  it('"Sun" is NOT in PLANET_ELEMENTS (handled separately)', () => {
    const override = focusTargetToOverride({ type: 'sun' });
    expect(PLANET_ELEMENTS.find((p) => p.name === override)).toBeUndefined();
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
      it(`${prev.action} → ${next.action}: new override is independent of previous`, () => {
        // Simulate: set override from first action, then replace with second
        let override = focusTargetToOverride(resolveFocusTarget(prev));
        override = focusTargetToOverride(resolveFocusTarget(next));

        // Verify the override matches only the second action
        if (next.action === 'selectAsteroid') expect(override).toBeNull();
        else if (next.action === 'selectPlanet') expect(override).toBe('Earth');
        else if (next.action === 'selectSun') expect(override).toBe('Sun');
        else expect(override).toBe('spacecraft');
      });
    }
  }
});
