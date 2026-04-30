export default function Dashboard({ stats, recentDocs, onNavigate }) {
  return (
    <div className="flex-1 overflow-y-auto p-10 space-y-10">
      <div className="max-w-6xl mx-auto space-y-10">
        <header>
          <h2 className="text-3xl font-bold tracking-tight text-zen-text-main mb-2">Workspace Overview</h2>
          <p className="text-zen-text-dim">Manage your CATIA automation workflows and bill of materials.</p>
        </header>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
          {[
            { label: 'Total Items Scanned', value: stats?.totalItems || 0, color: 'zen-info', bg: 'bg-zen-info' },
            { label: 'Pending Reviews', value: stats?.pendingReviews || 0, color: 'zen-warning', bg: 'bg-zen-warning' },
            { label: 'Ready for Export', value: stats?.readyForExport || 0, color: 'zen-success', bg: 'bg-zen-success' },
            { label: 'Active Drafts', value: stats?.activeDrafts || 0, color: 'zen-primary', bg: 'bg-zen-primary' },
          ].map((stat, i) => (
            <div key={i} className="zen-card p-6">
              <p className="zen-label mb-4">{stat.label}</p>
              <p className="text-3xl font-bold text-zen-text-main tracking-tighter">{stat.value}</p>
              <div className={`mt-4 h-1 w-8 rounded-full ${stat.bg}`}></div>
            </div>
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
            <h3 className="zen-label">System Logs</h3>
            <div className="zen-card p-5 h-[300px] overflow-y-auto font-mono text-[10px] space-y-2">
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
