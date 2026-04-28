export default function Dashboard({ stats, recentDocs, onNavigate }) {
  return (
    <div className="flex-1 overflow-y-auto p-10 space-y-10">
      <div className="max-w-6xl mx-auto space-y-10">
        <header>
          <h2 className="text-3xl font-bold tracking-tight text-white mb-2">Workspace Overview</h2>
          <p className="text-white/40">Manage your CATIA automation workflows and bill of materials.</p>
        </header>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { label: 'Total Items Scanned', value: stats?.totalItems || 0, color: 'blue' },
            { label: 'Pending Reviews', value: stats?.pendingReviews || 0, color: 'amber' },
            { label: 'Ready for Export', value: stats?.readyForExport || 0, color: 'emerald' },
            { label: 'Active Drafts', value: stats?.activeDrafts || 0, color: 'purple' },
          ].map((stat, i) => (
            <div key={i} className="bg-[#18181b] border border-white/5 rounded-2xl p-6 shadow-sm">
              <p className="text-[10px] font-bold text-white/30 uppercase tracking-widest mb-4">{stat.label}</p>
              <p className="text-3xl font-bold text-white tracking-tighter">{stat.value}</p>
              <div className={`mt-4 h-1 w-8 rounded-full bg-${stat.color}-500 shadow-[0_0_8px_rgba(var(--${stat.color}-500),0.4)]`}></div>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2 space-y-6">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold uppercase tracking-widest text-white/60">Quick Actions</h3>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <button 
                onClick={() => onNavigate('tree')}
                className="group p-6 bg-blue-600/5 hover:bg-blue-600/10 border border-blue-600/10 rounded-2xl transition-all text-left"
              >
                <div className="w-12 h-12 rounded-xl bg-blue-600/20 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                  <svg className="w-6 h-6 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
                </div>
                <h4 className="font-bold text-white mb-1">Scan CATIA Assembly</h4>
                <p className="text-xs text-white/30">Extract structural data and prepare for BOM generation.</p>
              </button>
              
              <button 
                onClick={() => onNavigate('bom')}
                className="group p-6 bg-emerald-600/5 hover:bg-emerald-600/10 border border-emerald-600/10 rounded-2xl transition-all text-left"
              >
                <div className="w-12 h-12 rounded-xl bg-emerald-600/20 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                  <svg className="w-6 h-6 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
                </div>
                <h4 className="font-bold text-white mb-1">BOM Commander</h4>
                <p className="text-xs text-white/30">Review, measure, and export bills of materials to Excel.</p>
              </button>
            </div>
          </div>

          <div className="space-y-6">
            <h3 className="text-sm font-bold uppercase tracking-widest text-white/60">System Logs</h3>
            <div className="bg-black/20 border border-white/5 rounded-2xl p-6 h-[300px] overflow-y-auto font-mono text-[10px] space-y-2 no-scrollbar">
              <div className="text-emerald-400/60 leading-relaxed"><span className="opacity-30">[{new Date().toLocaleTimeString()}]</span> API connected successfully.</div>
              <div className="text-white/40 leading-relaxed"><span className="opacity-30">[{new Date().toLocaleTimeString()}]</span> Waiting for CATIA document...</div>
              <div className="text-blue-400/60 leading-relaxed"><span className="opacity-30">[{new Date().toLocaleTimeString()}]</span> Session initialized: Enterprise_V2</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
