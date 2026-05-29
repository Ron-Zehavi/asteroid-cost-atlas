/** Lightweight helpers for the Methodology page. Kept pure so they're testable. */

export interface TocEntry {
  level: number;
  text: string;
  id: string;
}

export function slugify(s: string): string {
  return s
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '');
}

export function nodeText(node: unknown): string {
  if (typeof node === 'string') return node;
  if (typeof node === 'number') return String(node);
  if (Array.isArray(node)) return node.map(nodeText).join('');
  if (node && typeof node === 'object' && 'props' in node) {
    const props = (node as { props?: { children?: unknown } }).props;
    return nodeText(props?.children);
  }
  return '';
}

export function extractToc(md: string): TocEntry[] {
  const out: TocEntry[] = [];
  for (const line of md.split('\n')) {
    const m2 = line.match(/^## (.+?)\s*$/);
    if (m2) { out.push({ level: 2, text: m2[1], id: slugify(m2[1]) }); continue; }
    const m3 = line.match(/^### (.+?)\s*$/);
    if (m3) out.push({ level: 3, text: m3[1], id: slugify(m3[1]) });
  }
  return out;
}
