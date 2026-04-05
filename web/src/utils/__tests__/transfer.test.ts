import { describe, it, expect } from 'vitest';
import { getSpacecraftPosition, transferArcPoints } from '../transfer';

describe('getSpacecraftPosition', () => {
  const arcPoints = [
    { x: 0, y: 0, z: 0 },
    { x: 1, y: 0, z: 0 },
    { x: 2, y: 1, z: 0 },
    { x: 3, y: 1, z: 0 },
    { x: 4, y: 0, z: 0 },
  ];

  it('returns first point at 0% progress', () => {
    const pos = getSpacecraftPosition(arcPoints, 0);
    expect(pos).toEqual({ x: 0, y: 0, z: 0 });
  });

  it('returns last point at 100% progress', () => {
    const pos = getSpacecraftPosition(arcPoints, 1);
    expect(pos).toEqual({ x: 4, y: 0, z: 0 });
  });

  it('clamps progress below 0', () => {
    const pos = getSpacecraftPosition(arcPoints, -0.5);
    expect(pos).toEqual({ x: 0, y: 0, z: 0 });
  });

  it('clamps progress above 1', () => {
    const pos = getSpacecraftPosition(arcPoints, 1.5);
    expect(pos).toEqual({ x: 4, y: 0, z: 0 });
  });

  it('interpolates between points at 50%', () => {
    // 50% of 4 segments = index 2.0 → exact point
    const pos = getSpacecraftPosition(arcPoints, 0.5);
    expect(pos.x).toBeCloseTo(2, 5);
    expect(pos.y).toBeCloseTo(1, 5);
  });

  it('interpolates between points (not snapping to nearest)', () => {
    // 12.5% of 4 segments = index 0.5 → halfway between point 0 and 1
    const pos = getSpacecraftPosition(arcPoints, 0.125);
    expect(pos.x).toBeCloseTo(0.5, 5);
    expect(pos.y).toBeCloseTo(0, 5);
    expect(pos.z).toBeCloseTo(0, 5);
  });

  it('interpolates smoothly at arbitrary progress', () => {
    // 37.5% of 4 segments = index 1.5 → halfway between point 1 and 2
    const pos = getSpacecraftPosition(arcPoints, 0.375);
    expect(pos.x).toBeCloseTo(1.5, 5);
    expect(pos.y).toBeCloseTo(0.5, 5);
  });
});

describe('transferArcPoints', () => {
  const departure = { x: 1, y: 0, z: 0 };
  const arrival = { x: -1, y: 0, z: 0 };

  it('returns 257 points with default segments (256)', () => {
    const pts = transferArcPoints(departure, arrival);
    expect(pts.length).toBe(257);
  });

  it('starts at departure position', () => {
    const pts = transferArcPoints(departure, arrival);
    expect(pts[0].x).toBeCloseTo(departure.x, 3);
    expect(pts[0].z).toBeCloseTo(departure.z, 3);
  });

  it('ends at arrival position', () => {
    const pts = transferArcPoints(departure, arrival);
    const last = pts[pts.length - 1];
    expect(last.x).toBeCloseTo(arrival.x, 3);
    expect(last.z).toBeCloseTo(arrival.z, 3);
  });

  it('arc stays in the ecliptic plane (y = 0)', () => {
    const pts = transferArcPoints(departure, arrival);
    for (const p of pts) {
      expect(p.y).toBeCloseTo(0, 10);
    }
  });

  it('respects custom segment count', () => {
    const pts = transferArcPoints(departure, arrival, 10);
    expect(pts.length).toBe(11);
  });
});
