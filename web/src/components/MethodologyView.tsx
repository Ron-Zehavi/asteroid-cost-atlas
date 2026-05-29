import { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';

interface Props {
  onClose: () => void;
}

export function MethodologyView({ onClose }: Props) {
  const [markdown, setMarkdown] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch('/api/docs/methodology')
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

  return (
    <div className="methodology-view">
      <header className="methodology-header">
        <button className="back-btn" onClick={onClose}>← Back to atlas</button>
        <h2>Methodology</h2>
      </header>
      <div className="methodology-content">
        {error && <p className="methodology-error">Could not load methodology: {error}</p>}
        {!markdown && !error && <p className="methodology-loading">Loading…</p>}
        {markdown && (
          <ReactMarkdown
            components={{
              a: ({ href, children }) => (
                <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>
              ),
            }}
          >
            {markdown}
          </ReactMarkdown>
        )}
      </div>
    </div>
  );
}
