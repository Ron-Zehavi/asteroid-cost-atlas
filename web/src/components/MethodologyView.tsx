import { useEffect, useMemo, useState } from 'react';
import ReactMarkdown from 'react-markdown';

interface Props {
  onClose: () => void;
}

interface TocEntry {
  level: number;
  text: string;
  id: string;
}

function slugify(s: string): string {
  return s
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '');
}

function nodeText(node: unknown): string {
  if (typeof node === 'string') return node;
  if (typeof node === 'number') return String(node);
  if (Array.isArray(node)) return node.map(nodeText).join('');
  if (node && typeof node === 'object' && 'props' in node) {
    const props = (node as { props?: { children?: unknown } }).props;
    return nodeText(props?.children);
  }
  return '';
}

function extractToc(md: string): TocEntry[] {
  const out: TocEntry[] = [];
  for (const line of md.split('\n')) {
    const m2 = line.match(/^## (.+?)\s*$/);
    if (m2) { out.push({ level: 2, text: m2[1], id: slugify(m2[1]) }); continue; }
    const m3 = line.match(/^### (.+?)\s*$/);
    if (m3) out.push({ level: 3, text: m3[1], id: slugify(m3[1]) });
  }
  return out;
}

export function MethodologyView({ onClose }: Props) {
  const [markdown, setMarkdown] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const prev = document.title;
    document.title = 'Methodology — Asteroid Atlas';
    return () => { document.title = prev; };
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetch('/api/docs/methodology', { cache: 'force-cache' })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.text();
      })
      .then((text) => { if (!cancelled) setMarkdown(text); })
      .catch((e) => { if (!cancelled) setError(String(e)); });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const toc = useMemo(() => (markdown ? extractToc(markdown) : []), [markdown]);

  return (
    <div className="methodology-view">
      <header className="methodology-header">
        <button className="back-btn" onClick={onClose}>← Back to atlas</button>
        <h2>Methodology</h2>
      </header>
      <div className="methodology-body">
        {toc.length > 0 && (
          <nav className="methodology-toc" aria-label="Table of contents">
            <h3>Contents</h3>
            <ol>
              {toc.map((t, i) => (
                <li key={i} className={`toc-level-${t.level}`}>
                  <a href={`#m-${t.id}`}>{t.text}</a>
                </li>
              ))}
            </ol>
          </nav>
        )}
        <article className="methodology-content">
          {error && <p className="methodology-error">Could not load methodology: {error}</p>}
          {!markdown && !error && <p className="methodology-loading">Loading…</p>}
          {markdown && (
            <ReactMarkdown
              components={{
                h2: ({ children }) => <h2 id={`m-${slugify(nodeText(children))}`}>{children}</h2>,
                h3: ({ children }) => <h3 id={`m-${slugify(nodeText(children))}`}>{children}</h3>,
                a: ({ href, children }) => {
                  const external = href?.startsWith('http');
                  return external ? (
                    <a href={href} target="_blank" rel="noopener noreferrer" className="external-link">
                      {children}
                    </a>
                  ) : (
                    <a href={href}>{children}</a>
                  );
                },
              }}
            >
              {markdown}
            </ReactMarkdown>
          )}
        </article>
      </div>
    </div>
  );
}
