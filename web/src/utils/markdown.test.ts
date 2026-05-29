import { describe, expect, test } from 'vitest';
import { extractToc, nodeText, slugify } from './markdown';

describe('slugify', () => {
  test('lowercases and replaces non-alphanumerics with hyphens', () => {
    expect(slugify('Hello World')).toBe('hello-world');
    expect(slugify('Δv & Tisserand')).toBe('v-tisserand');
    expect(slugify('1.1 Data Sources')).toBe('1-1-data-sources');
  });

  test('strips leading and trailing hyphens', () => {
    expect(slugify('  spaces  ')).toBe('spaces');
    expect(slugify('--dashes--')).toBe('dashes');
  });

  test('collapses runs of separators', () => {
    expect(slugify('a   b___c')).toBe('a-b-c');
  });

  test('empty input', () => {
    expect(slugify('')).toBe('');
    expect(slugify('!!!')).toBe('');
  });
});

describe('extractToc', () => {
  test('returns empty array for markdown with no h2/h3', () => {
    expect(extractToc('# Just an h1\n\nbody')).toEqual([]);
  });

  test('captures h2 and h3 with correct level + slug', () => {
    const md = [
      '# Title',
      '## First Section',
      'body 1',
      '### Subsection A',
      'body 2',
      '### Subsection B',
      '## Second Section',
      'body 3',
    ].join('\n');
    const toc = extractToc(md);
    expect(toc).toEqual([
      { level: 2, text: 'First Section', id: 'first-section' },
      { level: 3, text: 'Subsection A', id: 'subsection-a' },
      { level: 3, text: 'Subsection B', id: 'subsection-b' },
      { level: 2, text: 'Second Section', id: 'second-section' },
    ]);
  });

  test('ignores h4 and deeper', () => {
    const md = '#### Too Deep\n##### Way Too Deep';
    expect(extractToc(md)).toEqual([]);
  });

  test('does not match indented or inline ##', () => {
    const md = '   ## Not a heading\nlorem ## inline\n## Real Heading';
    expect(extractToc(md)).toEqual([
      { level: 2, text: 'Real Heading', id: 'real-heading' },
    ]);
  });

  test('trims trailing whitespace on headings', () => {
    expect(extractToc('## Padded   ')).toEqual([
      { level: 2, text: 'Padded', id: 'padded' },
    ]);
  });
});

describe('nodeText', () => {
  test('returns string node as-is', () => {
    expect(nodeText('hello')).toBe('hello');
  });

  test('coerces numeric nodes', () => {
    expect(nodeText(42)).toBe('42');
  });

  test('joins array children', () => {
    expect(nodeText(['a', ' ', 'b'])).toBe('a b');
  });

  test('recurses through React element-shaped objects', () => {
    const fakeNode = { props: { children: ['Section ', { props: { children: '1.1' } }] } };
    expect(nodeText(fakeNode)).toBe('Section 1.1');
  });

  test('returns empty string for unknown input', () => {
    expect(nodeText(null)).toBe('');
    expect(nodeText(undefined)).toBe('');
    expect(nodeText({ random: true })).toBe('');
  });
});
