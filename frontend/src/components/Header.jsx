import StatusIndicator from './StatusIndicator'

export default function Header({ isConnected, activeDoc }) {
  return (
    <header className="h-16 border-b border-zen-border bg-zen-surface/80 backdrop-blur-xl flex items-center px-8 justify-between shrink-0 z-40">
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-3">
          <div className="w-2 h-2 rounded-full bg-zen-info animate-pulse shadow-[0_0_8px_rgba(47,97,124,0.4)]"></div>
          <span className="zen-label">Active Session</span>
        </div>
        
        <div className="h-4 w-px bg-zen-border"></div>
        
        <div className="flex items-center gap-3">
          <svg className="w-4 h-4 text-zen-text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
          <span className="text-sm font-bold text-zen-text-main">{activeDoc || 'No document loaded'}</span>
          <span className="text-[10px] px-2 py-0.5 rounded-md bg-zen-surface-alt border border-zen-border text-zen-text-muted font-mono">.CATProduct</span>
        </div>
      </div>

      <div className="flex items-center gap-6">
        <div className="flex items-center gap-4 bg-zen-surface-alt px-4 py-2 rounded-xl border border-zen-border">
          <div className="flex flex-col items-end">
            <span className="text-[9px] uppercase font-bold text-zen-text-muted tracking-widest">CATIA V5 Connection</span>
            <StatusIndicator isConnected={isConnected} />
          </div>
        </div>
        
        <button className="p-2.5 rounded-full bg-zen-primary text-white hover:scale-105 transition-all shadow-md active:scale-95">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"></path></svg>
        </button>
      </div>
    </header>
  )
}
