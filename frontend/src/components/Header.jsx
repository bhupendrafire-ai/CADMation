import StatusIndicator from './StatusIndicator'

export default function Header({ isConnected, activeDoc }) {
  return (
    <header className="h-16 border-b border-white/5 bg-[#09090b]/80 backdrop-blur-md flex items-center px-8 justify-between shrink-0 z-40">
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-3">
          <div className="w-2 h-2 rounded-full bg-blue-500 animate-pulse shadow-[0_0_8px_rgba(59,130,246,0.5)]"></div>
          <span className="text-[10px] font-bold text-white/40 uppercase tracking-[0.2em]">Active Session</span>
        </div>
        
        <div className="h-4 w-px bg-white/10"></div>
        
        <div className="flex items-center gap-3">
          <svg className="w-4 h-4 text-white/20" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
          <span className="text-sm font-bold text-white/80">{activeDoc || 'No document loaded'}</span>
          <span className="text-[10px] px-2 py-0.5 rounded bg-white/5 border border-white/10 text-white/30 font-mono">.CATProduct</span>
        </div>
      </div>

      <div className="flex items-center gap-6">
        <div className="flex items-center gap-4 bg-white/5 px-4 py-2 rounded-xl border border-white/5">
          <div className="flex flex-col items-end">
            <span className="text-[9px] uppercase font-bold text-white/30 tracking-widest">CATIA V5 Connection</span>
            <StatusIndicator isConnected={isConnected} />
          </div>
        </div>
        
        <button className="p-2.5 rounded-xl bg-white text-black hover:bg-neutral-200 transition-all shadow-lg active:scale-95">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"></path></svg>
        </button>
      </div>
    </header>
  )
}
