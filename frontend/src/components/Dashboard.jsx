import React, { useState, useEffect } from 'react';

export default function Dashboard({ stats, recentDocs, onNavigate, user }) {
  const [projects, setProjects] = useState([]);
  const [loadingProjects, setLoadingProjects] = useState(true);

  useEffect(() => {
    const fetchProjects = async () => {
      try {
        const res = await fetch('/api/projects/assigned');
        const data = await res.json();
        if (data.projects) {
          setProjects(data.projects);
        }
      } catch (err) {
        console.error('Failed to fetch assigned projects', err);
      } finally {
        setLoadingProjects(false);
      }
    };
    fetchProjects();
  }, []);

  const statCards = [
    { label: 'Total Items Scanned', value: stats?.totalItems || 0, color: 'zen-info', bg: 'bg-zen-info', view: 'leaderboard', description: 'Gamified scan history' },
    { label: 'Pending Reviews', value: stats?.pendingReviews || 0, color: 'zen-warning', bg: 'bg-zen-warning', view: 'reviews', description: 'Sent to Design Lead' },
    { label: 'Ready for Export', value: stats?.readyForExport || 0, color: 'zen-success', bg: 'bg-zen-success', view: 'final-boms', description: 'Validated BOM docs' },
    { label: 'Active Drafts', value: stats?.activeDrafts || 0, color: 'zen-primary', bg: 'bg-zen-primary', view: 'sessions', description: 'Saved chat sessions' },
  ];

  return (
    <div className="flex-1 overflow-y-auto p-10 space-y-10">
      <div className="max-w-6xl mx-auto space-y-10">
        <header>
          <h2 className="text-3xl font-bold tracking-tight text-zen-text-main mb-2">
            Welcome, <span className="text-zen-primary">{user?.name || 'Engineer'}</span>
          </h2>
          <p className="text-zen-text-dim">Your industrial design workspace is ready. Manage CATIA workflows and BOMs.</p>
        </header>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
          {statCards.map((stat, i) => (
            <button 
              key={i} 
              onClick={() => onNavigate(stat.view)}
              className="zen-card p-6 text-left hover:border-zen-primary/30 transition-all group relative overflow-hidden"
            >
              <div className={`absolute top-0 right-0 w-24 h-24 ${stat.bg}/5 -mr-8 -mt-8 rounded-full blur-2xl group-hover:scale-150 transition-transform`} />
              <div className="relative z-10">
                <div className="flex justify-between items-start mb-4">
                  <p className="zen-label">{stat.label}</p>
                  <div className="text-[10px] text-zen-primary font-bold uppercase tracking-widest opacity-0 group-hover:opacity-100 transition-opacity">View &rarr;</div>
                </div>
                <p className="text-3xl font-bold text-zen-text-main tracking-tighter group-hover:scale-110 transition-transform origin-left">{stat.value}</p>
                <div className={`mt-4 h-1 w-8 rounded-full ${stat.bg} group-hover:w-full transition-all duration-500`}></div>
                <p className="mt-2 text-[10px] text-zen-text-muted uppercase tracking-widest opacity-0 group-hover:opacity-100 transition-opacity">{stat.description}</p>
              </div>
            </button>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2 space-y-6">
            <div className="flex items-center justify-between">
              <h3 className="zen-label">Quick Actions</h3>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
              <button 
                onClick={() => onNavigate('tree')}
                className="group zen-card p-6 text-left border border-transparent hover:border-zen-info/20"
              >
                <div className="w-12 h-12 rounded-xl bg-zen-info/10 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform duration-300">
                  <svg className="w-6 h-6 text-zen-info" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
                </div>
                <h4 className="font-bold text-zen-text-main mb-1">Scan CATIA Assembly</h4>
                <p className="text-xs text-zen-text-dim">Extract structural data and prepare for BOM generation.</p>
              </button>
              
              <button 
                onClick={() => onNavigate('bom')}
                className="group zen-card p-6 text-left border border-transparent hover:border-zen-success/20"
              >
                <div className="w-12 h-12 rounded-xl bg-zen-success/10 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform duration-300">
                  <svg className="w-6 h-6 text-zen-success" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
                </div>
                <h4 className="font-bold text-zen-text-main mb-1">BOM Commander</h4>
                <p className="text-xs text-zen-text-dim">Review, measure, and export bills of materials to Excel.</p>
              </button>
            </div>
          </div>

          <div className="space-y-6">
            <h3 className="zen-label">Assigned Projects</h3>
            <div className="zen-card p-5 h-[300px] overflow-y-auto space-y-3">
              {loadingProjects ? (
                <div className="text-center text-zen-text-dim text-sm py-4">Loading projects...</div>
              ) : projects.length > 0 ? (
                projects.map((proj, idx) => (
                  <div key={idx} className="bg-zen-surface-alt rounded-lg p-3 border border-zen-border">
                    <div className="flex justify-between items-start mb-1">
                      <h4 className="text-sm font-bold text-zen-primary">{proj.name}</h4>
                      <span className="text-[10px] bg-zen-primary/10 text-zen-primary px-2 py-0.5 rounded-full uppercase font-bold tracking-widest">{proj.status}</span>
                    </div>
                    {proj.customer && <p className="text-xs text-zen-text-muted mb-1 font-mono">CLIENT: {proj.customer}</p>}
                    <p className="text-[11px] text-zen-text-dim line-clamp-2">{proj.description}</p>
                  </div>
                ))
              ) : (
                <div className="text-center text-zen-text-dim text-sm py-4">No projects assigned</div>
              )}
            </div>
            <h3 className="zen-label mt-6">System Logs</h3>
            <div className="zen-card p-5 h-[200px] overflow-y-auto font-mono text-[10px] space-y-2">
              <div className="text-zen-success leading-relaxed"><span className="text-zen-text-muted">[{new Date().toLocaleTimeString()}]</span> API connected successfully.</div>
              <div className="text-zen-text-dim leading-relaxed"><span className="text-zen-text-muted">[{new Date().toLocaleTimeString()}]</span> Waiting for CATIA document...</div>
              <div className="text-zen-info leading-relaxed"><span className="text-zen-text-muted">[{new Date().toLocaleTimeString()}]</span> Session initialized: Enterprise_V2</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
