import React, { useState, useEffect } from 'react';

export default function FinalBOMsPage({ onSelectSession }) {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchFinalSessions = async () => {
      try {
        const res = await fetch('/api/chat/sessions/final');
        const data = await res.json();
        setSessions(Array.isArray(data) ? data : []);
      } catch (err) {
        console.error('Failed to fetch final sessions', err);
      } finally {
        setLoading(false);
      }
    };
    fetchFinalSessions();
  }, []);

  return (
    <div className="flex-1 overflow-y-auto p-10 bg-zen-bg">
      <div className="max-w-6xl mx-auto">
        <header className="mb-10">
          <h2 className="text-3xl font-bold text-zen-text-main mb-2">Ready for Export</h2>
          <p className="text-zen-text-dim">Quick access to sessions that have reached the Final Document stage.</p>
        </header>

        {loading ? (
          <div className="text-center py-20 text-zen-text-dim">Scanning for final BOMs...</div>
        ) : sessions.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {sessions.map((session) => (
              <button
                key={session.id}
                onClick={() => onSelectSession(session.id)}
                className="zen-card p-6 text-left border-l-4 border-l-zen-success hover:border-zen-success/30 transition-all group"
              >
                <div className="flex justify-between items-start mb-4">
                  <div className="w-10 h-10 rounded-lg bg-zen-success/10 flex items-center justify-center text-zen-success group-hover:scale-110 transition-transform">
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                  </div>
                  <span className="text-[10px] text-zen-text-muted font-mono uppercase">
                    {new Date(session.updated_at).toLocaleDateString()}
                  </span>
                </div>
                <h3 className="font-bold text-zen-text-main mb-1 truncate">{session.name}</h3>
                <p className="text-xs text-zen-text-dim mb-4 truncate font-mono">PROJECT: {session.last_doc || 'Unnamed'}</p>
                <div className="flex items-center gap-2 mb-4">
                   <span className="text-[9px] bg-zen-success/10 text-zen-success px-2 py-0.5 rounded-full font-bold tracking-widest uppercase">Validated</span>
                   {session.user_name && <span className="text-[10px] text-zen-text-muted italic">by {session.user_name}</span>}
                </div>
                <div className="text-[10px] text-zen-success font-bold uppercase tracking-widest group-hover:translate-x-1 transition-transform">Open Final BOM &rarr;</div>
              </button>
            ))}
          </div>
        ) : (
          <div className="zen-card p-20 text-center text-zen-text-dim">
            No sessions found in the Final Document stage.
          </div>
        )}
      </div>
    </div>
  );
}
