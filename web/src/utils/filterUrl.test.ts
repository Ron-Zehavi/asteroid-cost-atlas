import { describe, expect, test } from 'vitest';
import { applyFiltersToSearch, DEFAULT_FILTERS, parseFiltersFromSearch } from './filterUrl';

describe('parseFiltersFromSearch', () => {
  test('returns DEFAULT_FILTERS when search is empty (no URL params)', () => {
    expect(parseFiltersFromSearch('')).toEqual(DEFAULT_FILTERS);
  });

  test('returns DEFAULT_FILTERS when only non-filter params are present', () => {
    expect(parseFiltersFromSearch('?asteroid=20175706')).toEqual(DEFAULT_FILTERS);
  });

  test('does NOT inherit dv_max=3 default when any filter param is present', () => {
    const f = parseFiltersFromSearch('?neo=Y');
    expect(f.neo).toBe('Y');
    expect(f.dv_max).toBeUndefined();
  });

  test('parses composition_class, neo, orbit_class', () => {
    const f = parseFiltersFromSearch('?composition_class=C&neo=Y&orbit_class=APO');
    expect(f.composition_class).toBe('C');
    expect(f.neo).toBe('Y');
    expect(f.orbit_class).toBe('APO');
  });

  test('parses viable=true and viable=false', () => {
    expect(parseFiltersFromSearch('?viable=true').is_viable).toBe(true);
    expect(parseFiltersFromSearch('?viable=false').is_viable).toBe(false);
    expect(parseFiltersFromSearch('?viable=garbage').is_viable).toBeUndefined();
  });

  test('parses numeric range filters', () => {
    const f = parseFiltersFromSearch(
      '?dv_min=1&dv_max=5&inclination_max=15&tisserand_min=2&tisserand_max=4&diameter_min=0.5&diameter_max=10',
    );
    expect(f.dv_min).toBe(1);
    expect(f.dv_max).toBe(5);
    expect(f.inclination_max).toBe(15);
    expect(f.tisserand_min).toBe(2);
    expect(f.tisserand_max).toBe(4);
    expect(f.diameter_min).toBe(0.5);
    expect(f.diameter_max).toBe(10);
  });

  test('ignores empty-string numeric params', () => {
    const f = parseFiltersFromSearch('?dv_max=');
    expect(f.dv_max).toBeUndefined();
  });

  test('ignores non-finite numeric params', () => {
    const f = parseFiltersFromSearch('?dv_max=NotANumber&neo=Y');
    expect(f.dv_max).toBeUndefined();
    expect(f.neo).toBe('Y');
  });

  test('parses sort and order', () => {
    const f = parseFiltersFromSearch('?sort=delta_v_km_s&order=desc');
    expect(f.sort).toBe('delta_v_km_s');
    expect(f.order).toBe('desc');
  });

  test('rejects invalid order', () => {
    const f = parseFiltersFromSearch('?sort=delta_v_km_s&order=sideways');
    expect(f.order).toBe('asc'); // default
  });
});

describe('applyFiltersToSearch', () => {
  test('writes non-default values, omits defaults', () => {
    const params = applyFiltersToSearch(
      new URLSearchParams(),
      { ...DEFAULT_FILTERS, neo: 'Y' },
    );
    expect(params.get('neo')).toBe('Y');
    // sort + order at defaults → not written
    expect(params.has('sort')).toBe(false);
    expect(params.has('order')).toBe(false);
  });

  test('preserves non-filter params (e.g. asteroid permalink)', () => {
    const existing = new URLSearchParams('asteroid=20175706');
    const params = applyFiltersToSearch(existing, { ...DEFAULT_FILTERS, neo: 'Y' });
    expect(params.get('asteroid')).toBe('20175706');
    expect(params.get('neo')).toBe('Y');
  });

  test('removes stale filter params when filters change', () => {
    const existing = new URLSearchParams('neo=Y&dv_max=5');
    // Simulate "Clear filters": only structural fields (sort/order/limit/offset).
    const params = applyFiltersToSearch(existing, {
      sort: DEFAULT_FILTERS.sort,
      order: DEFAULT_FILTERS.order,
      limit: 200,
      offset: 0,
    });
    expect(params.has('neo')).toBe(false);
    expect(params.has('dv_max')).toBe(false);
  });

  test('writes dv_max even at default value (3) when present in state', () => {
    const params = applyFiltersToSearch(new URLSearchParams(), { ...DEFAULT_FILTERS });
    expect(params.get('dv_max')).toBe('3');
  });

  test('writes is_viable as "viable=true" / "viable=false"', () => {
    const onTrue = applyFiltersToSearch(new URLSearchParams(), {
      ...DEFAULT_FILTERS, is_viable: true,
    });
    expect(onTrue.get('viable')).toBe('true');
    const onFalse = applyFiltersToSearch(new URLSearchParams(), {
      ...DEFAULT_FILTERS, is_viable: false,
    });
    expect(onFalse.get('viable')).toBe('false');
  });

  test('writes numeric ranges as strings', () => {
    const params = applyFiltersToSearch(new URLSearchParams(), {
      ...DEFAULT_FILTERS,
      inclination_max: 15,
      tisserand_min: 2.5,
      diameter_max: 10,
    });
    expect(params.get('inclination_max')).toBe('15');
    expect(params.get('tisserand_min')).toBe('2.5');
    expect(params.get('diameter_max')).toBe('10');
  });
});

describe('parseFiltersFromSearch ⇄ applyFiltersToSearch round-trip', () => {
  test('non-trivial filter set survives a round-trip', () => {
    const original = {
      ...DEFAULT_FILTERS,
      neo: 'Y',
      composition_class: 'C',
      is_viable: true,
      dv_max: 4,
      inclination_max: 10,
      sort: 'delta_v_km_s',
      order: 'desc' as const,
    };
    const params = applyFiltersToSearch(new URLSearchParams(), original);
    const parsed = parseFiltersFromSearch('?' + params.toString());
    expect(parsed.neo).toBe(original.neo);
    expect(parsed.composition_class).toBe(original.composition_class);
    expect(parsed.is_viable).toBe(original.is_viable);
    expect(parsed.dv_max).toBe(original.dv_max);
    expect(parsed.inclination_max).toBe(original.inclination_max);
    expect(parsed.sort).toBe(original.sort);
    expect(parsed.order).toBe(original.order);
  });
});
