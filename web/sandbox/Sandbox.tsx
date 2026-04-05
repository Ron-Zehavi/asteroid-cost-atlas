import { useState } from 'react';

/**
 * Component sandbox — isolate and iterate on components here
 * before adding them to the main app.
 *
 * Import your work-in-progress component and render it below.
 * The main project is untouched until you're ready.
 */

import { SpacecraftPreview } from '../src/components/scene/SpacecraftPreview';

const COMPONENTS: Record<string, () => JSX.Element> = {
  'SpacecraftPreview': () => <SpacecraftPreview />,
};

export function Sandbox() {
  const names = Object.keys(COMPONENTS);
  const [active, setActive] = useState(names[0] ?? '');

  return (
    <div style={{ display: 'flex', height: '100vh' }}>
      {/* Sidebar */}
      <nav style={{
        width: 220,
        borderRight: '1px solid #333',
        padding: 16,
        flexShrink: 0,
        overflowY: 'auto',
      }}>
        <h2 style={{ fontSize: 14, color: '#888', marginBottom: 12 }}>
          Sandbox
        </h2>
        {names.length === 0 && (
          <p style={{ fontSize: 12, color: '#666' }}>
            No components registered yet. Edit <code>Sandbox.tsx</code> to add one.
          </p>
        )}
        {names.map((name) => (
          <button
            key={name}
            onClick={() => setActive(name)}
            style={{
              display: 'block',
              width: '100%',
              padding: '8px 12px',
              marginBottom: 4,
              background: name === active ? '#2a2a4a' : 'transparent',
              color: name === active ? '#fff' : '#aaa',
              border: '1px solid',
              borderColor: name === active ? '#555' : 'transparent',
              borderRadius: 4,
              cursor: 'pointer',
              textAlign: 'left',
              fontSize: 13,
            }}
          >
            {name}
          </button>
        ))}
      </nav>

      {/* Preview area */}
      <main style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
        {active && COMPONENTS[active] ? (
          COMPONENTS[active]()
        ) : (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100%',
            color: '#555',
            fontSize: 14,
          }}>
            Select a component from the sidebar
          </div>
        )}
      </main>
    </div>
  );
}
