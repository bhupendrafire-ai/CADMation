import React, { useState, useEffect } from 'react';

export default function SessionsPage({ onSelectSession, user }) {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchSessions = async () => {
      try {
        const query = user?.role === 'SUPER_ADMIN' ? `?role=SUPER_ADMIN&all=true` : `?user_id=${user?.id}`;
        const res = await fetch(`/api/chat/sessions${query}`);
        const data = await res.json();
        setSessions(Array.isArray(data) ? data : []);
      } catch (err) {
        console.error('Failed to fetch sessions', err);
      } finally {
        setLoading(false);
      }
    };
    fetchSessions();
  }, [user]);

  return (
    <div className="flex-1 overflow-y-auto p-10 bg-zen-bg">
      <div className="max-w-6xl mx-auto">
        <header className="mb-10">
          <h2 className="text-3xl font-bold text-zen-text-main mb-2">Active Drafts</h2>
          <p className="text-zen-text-dim">Restore previous chat sessions and design drafts.</p>
        </header>

        {loading ? (
          <div className="text-center py-20 text-zen-text-dim">Loading sessions...</div>
        ) : sessions.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {sessions.map((session) => (
              <button
                key={session.id}
                onClick={() => onSelectSession(session.id)}
                className="zen-card p-6 text-left hover:border-zen-primary/30 transition-all group"
              >
                <div className="flex justify-between items-start mb-4">
                  <div className="w-10 h-10 rounded-lg bg-zen-primary/10 flex items-center justify-center text-zen-primary group-hover:scale-110 transition-transform">
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"></path></svg>
                  </div>
                  <span className="text-[10px] text-zen-text-muted font-mono uppercase">
                    {new Date(session.updated_at).toLocaleDateString()}
                  </span>
                </div>
                <h3 className="font-bold text-zen-text-main mb-1 truncate">{session.name}</h3>
                <p className="text-xs text-zen-text-dim mb-4 truncate font-mono">DOC: {session.last_doc || 'Unknown'}</p>
                {user?.role === 'SUPER_ADMIN' && session.user_name && (
                  <div className="flex items-center gap-2 mb-3">
                    <div className="w-4 h-4 rounded-full bg-zen-surface-alt flex items-center justify-center">
                      <svg className="w-2.5 h-2.5 text-zen-text-muted" fill="currentColor" viewBox="0 0 24 24"><path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67-0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/></svg>
                    </div>
                    <span className="text-[10px] text-zen-text-muted italic">{session.user_name}</span>
                  </div>
                )}
                <div className="text-[10px] text-zen-primary font-bold uppercase tracking-widest group-hover:translate-x-1 transition-transform">Restore Draft &rarr;</div>
              </button>
            ))}
          </div>
        ) : (
          <div className="zen-card p-20 text-center text-zen-text-dim">
            No active drafts found on this workstation.
          </div>
        )}
      </div>
    </div>
  );
}
